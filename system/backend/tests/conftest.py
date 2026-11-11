"""Leave the database as we found it.

The tests create throwaway tenants (with users such as a cashier named "ammar").
Left behind, those make logins ambiguous for the e2e suite and anyone using the
same database. Deleting a tenant cascades to all of its data.
"""
import asyncio
import os
import warnings

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


async def _run(sql: str, **params):
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            result = await conn.execute(text(sql), params)
            return set(result.scalars().all()) if result.returns_rows else None
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def remove_tenants_created_by_tests():
    if not os.environ.get("DATABASE_URL"):
        yield
        return
    before = asyncio.run(_run("SELECT id FROM tenants"))
    yield
    created = asyncio.run(_run("SELECT id FROM tenants")) - before
    if created:
        try:
            asyncio.run(_run("DELETE FROM tenants WHERE id = ANY(:ids)", ids=list(created)))
        except Exception as exc:  # cleanup must never mask test results
            warnings.warn(f"could not remove {len(created)} test tenants: {exc}", stacklevel=1)


async def give_roles(session) -> None:
    """Users made directly in a test get roles as the v54 migration gives them: exactly the access
    their role name and permission list used to mean (ADR-006 phase 3)."""
    from sqlalchemy import text

    from app.platform.permissions.migrate import migrate_users

    await session.flush()
    await session.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    await migrate_users(session)
