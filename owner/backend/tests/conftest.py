"""Leave the database as we found it: remove the owners and workspaces the tests create."""
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
def remove_rows_created_by_tests():
    if not os.environ.get("DATABASE_URL"):
        yield
        return
    tenants = asyncio.run(_run("SELECT id FROM tenants"))
    owners = asyncio.run(_run("SELECT id FROM owner_accounts"))
    payments = asyncio.run(_run("SELECT id FROM payment_transactions"))
    yield
    try:
        new_tenants = asyncio.run(_run("SELECT id FROM tenants")) - tenants
        new_owners = asyncio.run(_run("SELECT id FROM owner_accounts")) - owners
        if new_tenants:
            asyncio.run(_run("DELETE FROM tenants WHERE id = ANY(:ids)", ids=list(new_tenants)))
        new_payments = asyncio.run(_run("SELECT id FROM payment_transactions")) - payments
        if new_payments:
            asyncio.run(_run("DELETE FROM payment_transactions WHERE id = ANY(:ids)", ids=list(new_payments)))
        if new_owners:
            asyncio.run(_run("DELETE FROM owner_accounts WHERE id = ANY(:ids)", ids=list(new_owners)))
    except Exception as exc:  # cleanup must never mask test results
        warnings.warn(f"could not clean up test rows: {exc}", stacklevel=1)
