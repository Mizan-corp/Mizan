"""Lists run a constant number of queries, however many rows they return (#20, #21)."""
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, event

from app.core.security import hash_password
from app.core.tenancy import bind_tenant, current_tenant_id
from app.db.base import AsyncSessionLocal, engine
from app.models.shift import Shift
from app.models.tenant import Tenant
from app.models.user import User

from main import app  # noqa: F401  (registers every model)

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
    await session.commit()
    return tid, user


async def _drop(tid: uuid.UUID) -> None:
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Tenant).where(Tenant.id == tid))
        await s.commit()


async def test_shift_list_query_count_is_constant():
    from app.api.routers.shifts import list_shifts

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
    from app.modules.pharmacy.pharmacy.models import PharmacyBatch, PharmacyDrug
    from app.modules.pharmacy.pharmacy.router import list_drugs

    async with AsyncSessionLocal() as s:
        tid, user = await _workspace(s)
    try:
        async def listed() -> tuple[int, list]:
            async with AsyncSessionLocal() as s:
                await bind_tenant(s, tid)
                with count_queries() as seen:
                    out = await list_drugs(q=None, controlled_only=False, db=s, _user=user)
                return len(seen), out

        await listed()  # the module seeds its demo catalogue on first use
        few, out = await listed()

        async with AsyncSessionLocal() as s:
            await bind_tenant(s, tid)
            for i in range(6):
                drug = PharmacyDrug(tenant_id=tid, code=f"QC-{i}", trade_name=f"دواء {i}", scientific_name="Mizanolum",
                                    dosage_form="tab", strength="10mg", unit_price=10.0)
                s.add(drug)
                await s.flush()
                for qty in (3, 4):
                    s.add(PharmacyBatch(tenant_id=tid, drug_id=drug.id, batch_number=f"B{i}{qty}", expiry_date="2030-01-01",
                                        quantity_on_hand=qty))
            s.add(PharmacyDrug(tenant_id=tid, code="QC-ONE", trade_name="بلا بدائل", scientific_name="Unicum",
                               dosage_form="tab", strength="1", unit_price=1.0))
            await s.commit()

        many, out_many = await listed()
        assert len(out_many) == len(out) + 7
        assert many == few, f"{few} queries for {len(out)} drugs, {many} for {len(out_many)}"
        ours = {d["code"]: d for d in out_many if d["code"].startswith("QC-")}
        assert all(ours[f"QC-{i}"]["total_stock"] == 7 for i in range(6))
        assert all(ours[f"QC-{i}"]["alternatives_count"] == 5 for i in range(6))
        assert ours["QC-ONE"]["alternatives_count"] == 0 and ours["QC-ONE"]["total_stock"] == 0
    finally:
        await _drop(tid)
