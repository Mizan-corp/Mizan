"""Clinic role separation (#131): each clinical role holds its own clinic permissions, not the umbrella."""
import json
import os
import uuid

import pytest
from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from app.db.migrations import MIGRATIONS, split_statements
from app.platform.permissions.roles import standard_permissions
from tests.test_clinic_patient_access import _book, _client, _encounter, _env, _lab, _patient, _rx, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

CLINICAL = ("doctor", "nurse", "receptionist", "lab_tech", "pharmacist")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


def test_only_admin_and_manager_hold_the_umbrella():
    for role in CLINICAL:
        assert "clinic" not in standard_permissions(role), role
        assert "clinic:view" in standard_permissions(role), role
    assert "clinic" in standard_permissions("manager")
    assert "clinic" in standard_permissions("admin")
    assert set(standard_permissions("doctor")) & {"clinic:manage", "clinic:billing", "clinic:dispense", "clinic:lab"} == set()
    assert {"clinic:manage", "clinic:billing"} <= set(standard_permissions("receptionist"))
    assert "clinic:doctor" not in standard_permissions("nurse")


async def test_each_role_does_only_its_own_work():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        pid = await _patient(c, env, "مريض الأدوار")
        assert (await _book(c, env, pid, "doc_a")).status_code == 200

        # Reception: no encounters, no prescriptions, no lab results.
        assert (await c.post("/clinic/encounters", json=_encounter(pid), headers=h["reception"])).status_code == 403
        assert (await c.post("/clinic/prescriptions", json=_rx(pid), headers=h["reception"])).status_code == 403
        # Lab technician: can't prescribe. Pharmacist: can't examine. Nurse: can't register patients.
        assert (await c.post("/clinic/prescriptions", json=_rx(pid), headers=h["lab"])).status_code == 403
        assert (await c.post("/clinic/encounters", json=_encounter(pid), headers=h["pharmacist"])).status_code == 403
        assert (await c.post("/clinic/patients", headers=h["nurse"], json={
            "patient_mrn": f"MRN-{uuid.uuid4().hex[:6]}", "full_name": "x", "national_id": "1", "phone": "1",
            "gender": "ذكر", "date_of_birth": "1980-01-01"})).status_code == 403

        # The doctor on the care team examines, prescribes and orders tests.
        assert (await c.post("/clinic/encounters", json=_encounter(pid), headers=h["doc_a"])).status_code == 200
        rx = await c.post("/clinic/prescriptions", json=_rx(pid), headers=h["doc_a"])
        assert rx.status_code == 200
        lab = await c.post("/clinic/lab-orders", json=_lab(pid), headers=h["doc_a"])
        assert lab.status_code == 200

        # Only the lab records results; only the pharmacy dispenses; the doctor doesn't bill.
        result = {"result_value": "11.5", "is_signed_off": True}
        assert (await c.post(f"/clinic/lab-orders/{lab.json()['id']}/result", json=result, headers=h["doc_a"])).status_code == 403
        assert (await c.post(f"/clinic/lab-orders/{lab.json()['id']}/result", json=result, headers=h["reception"])).status_code == 403
        assert (await c.post(f"/clinic/lab-orders/{lab.json()['id']}/result", json=result, headers=h["lab"])).status_code == 200
        assert (await c.post(f"/clinic/prescriptions/{rx.json()['id']}/dispense", json={}, headers=h["doc_a"])).status_code == 403
        assert (await c.post(f"/clinic/prescriptions/{rx.json()['id']}/dispense", json={}, headers=h["reception"])).status_code == 403
        assert (await c.post(f"/clinic/prescriptions/{rx.json()['id']}/dispense", json={}, headers=h["pharmacist"])).status_code == 200
        assert (await c.get("/clinic/invoices", headers=h["doc_a"])).status_code == 403
        assert (await c.get("/clinic/invoices", headers=h["pharmacist"])).status_code == 403

        # Billing sees the charges, not the medication or the test.
        invoices = await c.get("/clinic/invoices", params={"patient_id": pid}, headers=h["reception"])
        assert invoices.status_code == 200
        lines = [ch["description"] for inv in invoices.json() for ch in inv["charges"]]
        assert f"صرف أدوية — روشتة {rx.json()['rx_ref']}" in lines
        assert f"رسوم فحص مخبري — طلب {lab.json()['order_ref']}" in lines
        assert not any("Paracetamol" in d or "CBC" in d for d in lines)

        # The queue: doctors and nurses move patients; the lab doesn't. The ward: nurses.
        appt_id = (await c.get("/clinic/appointments", headers=h["reception"])).json()["items"][0]["id"]
        assert (await c.post(f"/clinic/appointments/{appt_id}/status", json={"status": "waiting"}, headers=h["lab"])).status_code == 403
        assert (await c.post(f"/clinic/appointments/{appt_id}/status", json={"status": "waiting"}, headers=h["nurse"])).status_code == 200
        assert (await c.post(f"/clinic/appointments/{appt_id}/status", json={"status": "in_consultation"}, headers=h["doc_a"])).status_code == 200

        # Money figures in the summary are billing's.
        assert "total_revenue_billed" not in (await c.get("/clinic/summary", headers=h["doc_a"])).json()
        assert "total_revenue_billed" in (await c.get("/clinic/summary", headers=h["reception"])).json()


async def test_v84_strips_the_umbrella_from_personal_copies_only():
    tenant = await _sql("SELECT id FROM tenants LIMIT 1")
    t = tenant[0][0]
    suffix = uuid.uuid4().hex[:8]
    copy_code, own_code = f"doctor-{suffix}", f"ws-clinic-{suffix}"
    for code in (copy_code, own_code):
        await _sql("INSERT INTO sys_roles (id, tenant_id, code, name, name_en, is_system, is_clinical, grants) "
                   "VALUES (gen_random_uuid(), :t, :c, :c, :c, false, true, CAST(:g AS jsonb))",
                   t=t, c=code, g=json.dumps(["clinic", "clinic:doctor", "patients"]))
    sql = dict(MIGRATIONS)["v84_clinic_role_separation"]
    for _ in range(2):  # idempotent
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            for stmt in split_statements(sql):
                if stmt.strip():
                    await s.execute(text(stmt))
            await s.commit()
    rows = dict(await _sql("SELECT code, grants FROM sys_roles WHERE code IN (:a, :b)", a=copy_code, b=own_code))
    assert rows[copy_code] == ["clinic:doctor", "clinic:view", "patients"]
    assert rows[own_code] == ["clinic", "clinic:doctor", "patients"]
    await _sql("DELETE FROM sys_roles WHERE code IN (:a, :b)", a=copy_code, b=own_code)
