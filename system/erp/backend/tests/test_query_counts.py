"""Lists run a constant number of queries, however many rows they return (#20, #21)."""
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, event

from app.platform.auth.security import hash_password
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from app.db.base import AsyncSessionLocal, engine
from app.activities.general.modules.pos.models import Shift
from app.platform.tenancy.models import Tenant
from app.platform.auth.models.user import User

from main import app  # noqa: F401  (registers every model)
from tests.conftest import give_roles

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def fresh_engine():
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


@contextmanager
def count_queries():
    seen: list[str] = []

    def before(conn, cursor, statement, parameters, context, executemany):
        if not statement.lstrip().upper().startswith(("SELECT SET_CONFIG", "RESET")):
            seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", before)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", before)


async def _workspace(session) -> tuple[uuid.UUID, User]:
    tid = uuid.uuid4()
    session.add(Tenant(id=tid, name=f"Counts {tid.hex[:6]}", slug=f"counts-{tid.hex[:8]}", status="active"))
    await session.flush()
    user = User(id=uuid.uuid4(), tenant_id=tid, username=f"mgr_{tid.hex[:6]}", full_name="مديرة الوردية",
                role="admin", password_hash=hash_password("Pass123!"), permissions=["*"], is_active=True)
    session.add(user)
    await give_roles(session)
    await session.commit()
    return tid, user


async def _drop(tid: uuid.UUID) -> None:
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Tenant).where(Tenant.id == tid))
        await s.commit()


async def test_shift_list_query_count_is_constant():
    from app.activities.general.modules.pos.routes.shifts import list_shifts

    async with AsyncSessionLocal() as s:
        tid, user = await _workspace(s)
    try:
        async def add_shifts(n: int) -> None:
            async with AsyncSessionLocal() as s:
                await bind_tenant(s, tid)
                for _ in range(n):
                    s.add(Shift(tenant_id=tid, cashier_id=user.id, started_at=datetime.now(timezone.utc)))
                await s.commit()

        async def listed() -> tuple[int, list]:
            async with AsyncSessionLocal() as s:
                await bind_tenant(s, tid)
                with count_queries() as seen:
                    out = await list_shifts(limit=100, offset=0, warehouse_id=None, db=s, current_user=user)
                return len(seen), out

        await add_shifts(2)
        few, out = await listed()
        await add_shifts(8)
        many, out_many = await listed()
        assert len(out) == 2 and len(out_many) == 10
        assert many == few, f"{few} queries for 2 shifts, {many} for 10"
        assert {o.cashier_name for o in out_many} == {"مديرة الوردية"}
    finally:
        await _drop(tid)


async def test_drug_list_query_count_is_constant():
    """The formulary (products with drug fields, their sellable stock and nearest expiry) is one
    query however many drugs and batches there are (ADR-006 phase 4e)."""
    from datetime import date, timedelta

    from app.activities.general.modules.inventory.models.product import Product
    from app.activities.pharmacy.modules.batches.models import Lot
    from app.activities.pharmacy.modules.pharmacy.router import list_drugs
    from sqlalchemy import text as sqltext

    async with AsyncSessionLocal() as s:
        tid, user = await _workspace(s)
    try:
        async def listed() -> tuple[int, list]:
            async with AsyncSessionLocal() as s:
                await bind_tenant(s, tid)
                with count_queries() as seen:
                    out = await list_drugs(search=None, db=s, _=user)
                return len(seen), out

        few, out = await listed()
        async with AsyncSessionLocal() as s:
            await bind_tenant(s, tid)
            wh = await s.scalar(sqltext("INSERT INTO warehouses (id, tenant_id, code, name, is_active) VALUES (gen_random_uuid(), :t, 'QC', 'QC', true) RETURNING id"), {"t": tid})
            for i in range(6):
                product = Product(tenant_id=tid, name=f"دواء {i}", unit="عدد", retail_price=10, wholesale_price=10, cost_price=5,
                                  is_active=True, extra={"scientific_name": "Mizanolum", "requires_prescription": i % 2 == 0})
                s.add(product)
                await s.flush()
                for n, qty in enumerate((3, 4)):
                    s.add(Lot(tenant_id=tid, product_id=product.id, warehouse_id=wh, batch_number=f"B{i}{n}",
                              expiry_date=date.today() + timedelta(days=30 * (n + 1)), qty=qty))
            await s.commit()

        many, out_many = await listed()
        assert len(out_many) == len(out) + 6
        assert many == few, f"{few} queries for {len(out)} drugs, {many} for {len(out_many)}"
        ours = [d for d in out_many if d["scientific_name"] == "Mizanolum"]
        assert all(float(d["sellable_qty"]) == 7 for d in ours)
        assert all(d["nearest_expiry"] == date.today() + timedelta(days=30) for d in ours)
    finally:
        await _drop(tid)
