"""Workspace isolation holds for raw SQL even when the login role bypasses RLS (#112).

The local stack and Neon both log in with a role that ignores RLS. While a workspace is bound,
every transaction must run as mizan_app, so raw SQL only sees that workspace's rows.
"""
import os
import uuid

import pytest
from sqlalchemy import text

import main  # noqa: F401  (loads every model)
from app.platform.auth.security import hash_password
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from app.db.base import AsyncSessionLocal
from app.platform.tenancy.models import Tenant
from app.platform.auth.models.user import User

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


async def test_migrate_grants_mizan_app_on_tables_any_role_made():
    """Production's tables moved from Neon: default privileges named Neon's roles, so tables the new
    login role made (v74, v75) had no grants for mizan_app. Every migrate now grants them again."""
    from app.db.migrations import grant_app_role

    role, table = f"mz_owner_{uuid.uuid4().hex[:6]}", f"mz_t_{uuid.uuid4().hex[:6]}"
    can = text("SELECT has_table_privilege('mizan_app', :t, 'SELECT')")
    async with AsyncSessionLocal() as db:
        await db.execute(text(f"CREATE ROLE {role} NOLOGIN"))
        await db.execute(text(f"GRANT CREATE, USAGE ON SCHEMA public TO {role}"))
        await db.execute(text(f"SET ROLE {role}"))
        await db.execute(text(f"CREATE TABLE {table} (id int)"))
        await db.execute(text("RESET ROLE"))
        await db.commit()
        try:
            assert await db.scalar(can, {"t": f"public.{table}"}) is False
            await grant_app_role(db)
            assert await db.scalar(can, {"t": f"public.{table}"}) is True
            missing = (await db.execute(text(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT has_table_privilege('mizan_app', c.oid, 'SELECT')"))).scalars().all()
            assert missing == []
        finally:
            await db.execute(text(f"DROP TABLE IF EXISTS {table}"))
            await db.execute(text(f"REVOKE ALL ON SCHEMA public FROM {role}"))
            await db.execute(text(f"DROP OWNED BY {role}"))
            await db.execute(text(f"DROP ROLE IF EXISTS {role}"))
            await db.commit()
