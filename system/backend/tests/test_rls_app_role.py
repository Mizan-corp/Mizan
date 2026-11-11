"""Workspace isolation holds for raw SQL even when the login role bypasses RLS (#112).

The local stack and Neon both log in with a role that ignores RLS. While a workspace is bound,
every transaction must run as mizan_app, so raw SQL only sees that workspace's rows.
"""
import os
import uuid

import pytest
from sqlalchemy import text

import main  # noqa: F401  (loads every model)
from app.core.security import hash_password
from app.core.tenancy import bind_tenant, current_tenant_id
from app.db.base import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.user import User

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _two_workspaces():
    ids = []
    async with AsyncSessionLocal() as session:
        for n in (1, 2):
            tid = uuid.uuid4()
            session.add(Tenant(id=tid, name=f"RLS {n} {tid.hex[:6]}", slug=f"rls-{n}-{tid.hex[:6]}", status="active"))
            await session.flush()
            session.add(User(id=uuid.uuid4(), tenant_id=tid, username=f"rls_{tid.hex[:8]}", full_name="RLS user",
                             role="cashier", password_hash=hash_password("Pass123!"), permissions=["sales"]))
            ids.append(tid)
        await session.commit()
    return ids


async def test_raw_sql_sees_only_the_bound_workspace():
    t1, t2 = await _two_workspaces()
    async with AsyncSessionLocal() as session:
        await bind_tenant(session, t1)
        role = await session.scalar(text("SELECT current_user"))
        seen = set((await session.execute(text("SELECT DISTINCT tenant_id FROM users"))).scalars().all())
        assert role == "mizan_app"
        assert seen == {t1}

        # A commit starts a new transaction: still restricted.
        await session.commit()
        seen = set((await session.execute(text("SELECT DISTINCT tenant_id FROM users"))).scalars().all())
        assert seen == {t1}
        assert t2 not in seen


async def test_no_workspace_bound_keeps_the_login_role():
    async with AsyncSessionLocal() as session:
        role = await session.scalar(text("SELECT current_user"))
        assert role != "mizan_app"  # scripts and migrations still run DDL as the owner
