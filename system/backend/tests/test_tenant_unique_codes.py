"""Codes a workspace types or numbers itself are unique per workspace, not across all
workspaces (#18, migration v49)."""
import os
import uuid

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError

from app.db.base import AsyncSessionLocal
from app.platform.tenancy.models import Tenant
from app.modules.pharmacy.pharmacy.models import PharmacyPrescription
from app.modules.school.school.models import SchoolStudent

from main import app  # noqa: F401  (registers every model)

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

# Unique indexes on workspace tables that deliberately don't include tenant_id.
GLOBAL_BY_DESIGN = {
    "ecom_abandoned_carts",       # cart_token: random
    "tenant_billing_invoices",    # invoice_ref: the platform's own numbering (Paymob callbacks)
    "hr_attendance",              # (employee_id, work_date): the employee is the workspace's
    "hr_payroll",                 # (employee_id, month)
    "hr_payroll_entries",         # (period_id, employee_id)
    "supplier_prices",            # (supplier_id, product_id)
    "user_permission_overrides",  # (user_id, permission_id)
    "sys_roles",                  # code WHERE tenant_id IS NULL: the platform's standard roles
}


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


async def _tenant(session) -> uuid.UUID:
    tid = uuid.uuid4()
    session.add(Tenant(id=tid, name=f"Codes {tid.hex[:6]}", slug=f"codes-{tid.hex[:8]}", status="active"))
    await session.flush()
    return tid


def _student(tid, code):
    return SchoolStudent(tenant_id=tid, code=code, name="طالب", grade="1", parent_phone="0100")


async def test_two_workspaces_can_use_the_same_codes():
    async with AsyncSessionLocal() as s:
        a, b = await _tenant(s), await _tenant(s)
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            s.add_all([
                _student(a, "STU-1001"), _student(b, "STU-1001"),
                PharmacyPrescription(tenant_id=a, rx_number="RX-0001", patient_name="م", doctor_name="د"),
                PharmacyPrescription(tenant_id=b, rx_number="RX-0001", patient_name="م", doctor_name="د"),
            ])
            await s.commit()

        # Still unique inside one workspace.
        async with AsyncSessionLocal() as s:
            s.add(_student(a, "STU-1001"))
            with pytest.raises(IntegrityError):
                await s.commit()
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Tenant).where(Tenant.id.in_([a, b])))
            await s.commit()


async def test_no_workspace_table_has_a_global_unique_code():
    """Guard: a unique index on a workspace table must include tenant_id (or be listed above)."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text("""
            SELECT t.relname, i.relname
            FROM pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public' AND ix.indisunique AND NOT ix.indisprimary
              AND EXISTS (SELECT 1 FROM pg_attribute a
                          WHERE a.attrelid = t.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped)
              AND NOT EXISTS (SELECT 1 FROM unnest(ix.indkey) k
                              JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k
                              WHERE a.attname = 'tenant_id')
        """))).all()
    offenders = sorted(f"{table}.{index}" for table, index in rows if table not in GLOBAL_BY_DESIGN)
    assert not offenders, f"unique across all workspaces (add tenant_id): {offenders}"
