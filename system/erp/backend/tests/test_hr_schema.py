"""HR's models are its schema (HR-5): a database whose HR tables were made from the models
(create_all, as CI and local stacks do for missing tables) has the same columns, types and
defaults as the migrated one, and payroll runs on it."""
import os
import uuid

import pytest
from sqlalchemy import MetaData, text

from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from app.platform.tenancy.models import Tenant

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


MONTH = "2025-02"


async def _workspace() -> dict:
    from app.models.registry import load_all_models
    from app.platform.tenancy.context import install_tenancy_events

    load_all_models()
    install_tenancy_events()
    tid, uid = uuid.uuid4(), uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=tid, name=f"HR {tid.hex[:6]}", slug=f"hrs-{tid.hex[:8]}", status="active",
                     active_modules=["finance", "hr"]))
        await s.flush()
        s.add(User(id=uid, tenant_id=tid, username=f"hrs_{tid.hex[:8]}", full_name="مدير", role="admin",
                   password_hash="x", is_active=True))
        await s.commit()
    current_tenant_id.set(tid)
    return {"tid": tid, "uid": uid}


async def _session(ws):
    db = AsyncSessionLocal()
    await bind_tenant(db, ws["tid"])
    user = await db.get(User, ws["uid"])
    db.expunge(user)
    return db, user


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


# ── HR-5: the models are the schema ─────────────────────────────────────────────────────

HR_TABLES = ("hr_employees", "hr_shifts", "hr_attendance", "hr_advances", "hr_settings", "hr_payroll_periods",
             "hr_payroll_entries", "hr_audit_log")


def _family(type_name: str) -> str:
    t = type_name.lower()
    for key, fam in (("uuid", "uuid"), ("char", "text"), ("text", "text"), ("string", "text"), ("timestamp", "timestamp"),
                     ("datetime", "timestamp"), ("date", "date"), ("time", "time"), ("numeric", "numeric"),
                     ("bool", "bool"), ("int", "int"), ("json", "json")):
        if key in t:
            return fam
    return t


async def test_hr_models_match_the_database():
    """Old models lacked hr_employees.shift_id, ignore_lateness and the overtime limit, and typed
    hr_shifts.id, the shift times, attendance.shift_override and edited_by as uuid/time."""
    from app.db.base import Base
    from app.models.registry import load_all_models

    load_all_models()
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text("""
            SELECT table_name, column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ANY(:t)
        """), {"t": list(HR_TABLES)})).all()
    db_cols = {(r.table_name, r.column_name): _family(r.data_type) for r in rows}
    model_cols = {(t, c.name): _family(str(c.type)) for t in HR_TABLES for c in Base.metadata.tables[t].columns}
    assert set(db_cols) == set(model_cols), (set(db_cols) ^ set(model_cols))
    assert {k: v for k, v in model_cols.items() if db_cols[k] != v} == {}


async def test_payroll_runs_on_tables_made_from_the_models():
    """CI and local stacks create missing tables from the models (create_all): payroll must work on
    them (the old hr_shifts uuid id and missing columns broke it). The HR tables are made from the
    models in a scratch schema, then a month is calculated and reported."""
    from app.db.base import Base, engine
    from app.models.registry import load_all_models
    from app.activities.general.modules.hr.routes import hr as routes
    from app.activities.general.modules.hr.services import payroll

    load_all_models()
    ws = await _workspace()
    schema = f"hr_models_{uuid.uuid4().hex[:8]}"
    # Copies without foreign keys: a foreign key to tenants would lock it against the workspaces
    # other tests create and delete meanwhile. Columns, defaults and unique keys are the models'.
    scratch = MetaData()
    tables = []
    for name in HR_TABLES:
        t = Base.metadata.tables[name].to_metadata(scratch)
        for fk in list(t.foreign_key_constraints):
            t.constraints.discard(fk)
        for col in t.columns:
            col.foreign_keys.clear()
        t.foreign_keys.clear()
        tables.append(t)
    async with engine.begin() as conn:
        await conn.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        await conn.execute(text(f"CREATE SCHEMA {schema}"))
        await conn.execute(text(f"SET LOCAL search_path TO {schema}, public"))
        await conn.run_sync(lambda c: scratch.create_all(c, tables=tables, checkfirst=False))
        for t in HR_TABLES:  # what the foundation migration gives every workspace table
            await conn.execute(text(f"ALTER TABLE {schema}.{t} ALTER COLUMN tenant_id "
                                    "SET DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid"))
        await conn.execute(text(f"GRANT USAGE ON SCHEMA {schema} TO PUBLIC"))
        await conn.execute(text(f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO PUBLIC"))
    try:
        db, user = await _session(ws)
        async with db:
            await db.execute(text(f"SET LOCAL search_path TO {schema}, public"))
            emp = (await db.execute(text("""
                INSERT INTO hr_employees (name, monthly_salary, shift_id, ignore_lateness) VALUES ('موظف', 2600, 'S1', true)
                RETURNING id"""))).scalar_one()
            await db.execute(text("INSERT INTO hr_shifts (id, name, start_time, end_time) VALUES ('S1', 'صباحي', '09:00', '17:00')"))
            await db.execute(text("""
                INSERT INTO hr_attendance (employee_id, work_date, check_in, check_out, shift_override, edited_by)
                VALUES (:e, '2025-02-03', '2025-02-03 09:00', '2025-02-03 17:00', 'S1', 'مدير')"""), {"e": emp})
            await db.execute(text("INSERT INTO hr_advances (employee_id, amount, date, record_type) VALUES (:e, 10, '2025-02-03', 'خصم')"),
                             {"e": emp})
            await db.execute(text(f"SET LOCAL search_path TO {schema}, public"))
            result = await payroll.calculate_payroll_month(db, MONTH, str(user.id))
            assert result["employees"] == 1
            await db.execute(text(f"SET LOCAL search_path TO {schema}, public"))
            assert "موظف" in (await routes.payroll_monthly_report(month=MONTH, db=db, _=user)).body.decode()
            await db.rollback()
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
