"""Patient-level clinical access (#113): care team, break-glass, access log, privacy officer."""
import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app
from app.db.base import AsyncSessionLocal
from app.platform.auth.security import create_access_token, hash_password
from app.platform.auth.models.user import User
from app.platform.permissions.roles import standard_permissions
from app.platform.tenancy.models import Tenant
from tests.conftest import give_roles

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

ROLES = {
    "doc_a": ("doctor", "د. أحمد الفريق"),
    "doc_b": ("doctor", "د. بسمة الخارجية"),
    "nurse": ("nurse", "ممرضة نور"),
    "reception": ("receptionist", "موظف الاستقبال"),
    "pharmacist": ("pharmacist", "الصيدلي"),
    "lab": ("lab_tech", "فني المختبر"),
    "manager": ("manager", "مدير العيادة"),
}


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def _sql(sql: str, **params):
    async with AsyncSessionLocal() as s:
        await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        result = await s.execute(text(sql), params)
        rows = result.all() if result.returns_rows else None
        await s.commit()
        return rows


async def _env():
    async with AsyncSessionLocal() as session:
        t_id = uuid.uuid4()
        session.add(Tenant(id=t_id, name=f"Access Clinic {t_id.hex[:6]}", slug=f"acc-{t_id.hex[:6]}",
                           status="active", active_modules=["healthcare_clinic", "pharmacy", "finance"]))
        await session.flush()
        users = {}
        for key, (role, name) in ROLES.items():
            u = User(id=uuid.uuid4(), tenant_id=t_id, username=f"{key}_{t_id.hex[:6]}", full_name=name, role=role,
                     password_hash=hash_password("Pass12345!"), permissions=standard_permissions(role), is_active=True)
            session.add(u)
            users[key] = u
        await give_roles(session)
        await session.commit()
    headers = {
        k: {"Authorization": "Bearer " + create_access_token(
            {"sub": str(u.id), "role": u.role, "username": u.username, "tid": str(t_id)})}
        for k, u in users.items()
    }
    return {"tenant_id": str(t_id), "users": users, "h": headers}


async def _patient(c, env, name: str) -> str:
    r = await c.post("/clinic/patients", headers=env["h"]["reception"], json={
        "patient_mrn": f"MRN-{uuid.uuid4().hex[:6]}", "full_name": name, "national_id": uuid.uuid4().hex[:14],
        "phone": "0100000000", "gender": "ذكر", "date_of_birth": "1980-01-01", "blood_group": "B+",
        "allergies": "بنسلين", "chronic_conditions": "سكري",
    })
    assert r.status_code == 200, r.text
    assert r.json()["allergies"] is None  # the receptionist registered it but doesn't read it back
    return r.json()["id"]


def _encounter(pid: str) -> dict:
    return {"patient_id": pid, "patient_name": "x", "doctor_name": "د. أحمد الفريق", "department": "باطنة",
            "encounter_date": "2026-11-14", "chief_complaint": "صداع", "icd10_code": "R51",
            "icd10_description": "صداع", "clinical_notes": "ملاحظات سرية"}


def _rx(pid: str) -> dict:
    return {"patient_id": pid, "patient_name": "x", "doctor_name": "د. أحمد الفريق", "issue_date": "2026-11-14",
            "medication_name": "Paracetamol", "dosage": "500mg", "frequency": "مرتين"}


def _lab(pid: str) -> dict:
    return {"patient_id": pid, "patient_name": "x", "doctor_name": "د. أحمد الفريق", "test_name": "CBC",
            "category": "دم", "specimen_barcode": "S-1"}


async def _book(c, env, pid: str, doctor_key: str):
    return await _book_as(c, env, pid, doctor_key, "reception")


async def _book_as(c, env, pid: str, doctor_key: str, actor: str):
    return await c.post("/clinic/appointments", headers=env["h"][actor], json={
        "patient_id": pid, "doctor_user_id": str(env["users"][doctor_key].id), "department": "باطنة",
        "appointment_date": "2026-11-14", "time_slot": "10:00 AM",
    })


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_care_team_decides_and_booking_grants_access():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        p1 = await _patient(c, env, "مريض الفريق")
        p2 = await _patient(c, env, "مريض آخر")

        # An unassigned doctor is refused on the patient's clinical record.
        for path in ("/clinic/encounters", "/clinic/prescriptions", "/clinic/lab-orders"):
            r = await c.get(path, params={"patient_id": p1}, headers=h["doc_a"])
            assert r.status_code == 403, path
            assert "الوصول الطارئ" in r.json()["detail"]
        assert (await c.post("/clinic/encounters", json=_encounter(p1), headers=h["doc_a"])).status_code == 403
        assert (await c.post("/clinic/prescriptions", json=_rx(p1), headers=h["doc_a"])).status_code == 403
        assert (await c.post("/clinic/lab-orders", json=_lab(p1), headers=h["doc_a"])).status_code == 403

        # The booking form lists clinicians only.
        clinicians = (await c.get("/clinic/clinicians", headers=h["reception"])).json()
        ids = {x["id"] for x in clinicians}
        assert {str(env["users"][k].id) for k in ("doc_a", "doc_b", "nurse")} <= ids
        assert str(env["users"]["reception"].id) not in ids
        bad = await c.post("/clinic/appointments", headers=h["reception"], json={
            "patient_id": p1, "doctor_user_id": str(env["users"]["reception"].id), "department": "باطنة",
            "appointment_date": "2026-11-14", "time_slot": "10:00 AM"})
        assert bad.status_code == 400

        # Booking with the doctor puts them on the care team.
        appt = await _book(c, env, p1, "doc_a")
        assert appt.status_code == 200, appt.text
        assert appt.json()["doctor_name"] == "د. أحمد الفريق"
        assert appt.json()["doctor_user_id"] == str(env["users"]["doc_a"].id)

        assert (await c.post("/clinic/encounters", json=_encounter(p1), headers=h["doc_a"])).status_code == 200
        assert (await c.post("/clinic/prescriptions", json=_rx(p1), headers=h["doc_a"])).status_code == 200
        assert (await c.post("/clinic/lab-orders", json=_lab(p1), headers=h["doc_a"])).status_code == 200
        r = await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["doc_a"])
        assert r.status_code == 200 and len(r.json()) == 1
        listed = await c.get("/clinic/encounters", headers=h["doc_a"])
        assert {e["patient_id"] for e in listed.json()} == {p1}
        patients = {p["id"]: p for p in (await c.get("/clinic/patients", headers=h["doc_a"])).json()}
        assert patients[p1]["clinical_access"] is True and patients[p1]["allergies"] == "بنسلين"
        assert patients[p1]["access"] == "team"
        assert patients[p2]["clinical_access"] is False and patients[p2]["allergies"] is None

        # Another doctor sees none of that patient's rows.
        for path in ("/clinic/encounters", "/clinic/prescriptions", "/clinic/lab-orders"):
            rows = (await c.get(path, headers=h["doc_b"])).json()
            assert all(x["patient_id"] != p1 for x in rows), path
            assert (await c.get(path, params={"patient_id": p1}, headers=h["doc_b"])).status_code == 403

        # Reception: patient list with clinical fields redacted, no clinical reads.
        rows = (await c.get("/clinic/patients", headers=h["reception"])).json()
        mine = [p for p in rows if p["id"] in (p1, p2)]
        assert len(mine) == 2
        assert all(p["allergies"] is None and p["chronic_conditions"] is None and p["blood_group"] is None
                   and p["clinical_access"] is False for p in mine)
        single = (await c.get(f"/clinic/patients/{p1}", headers=h["reception"])).json()
        assert single["allergies"] is None
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["reception"])).status_code == 403
        assert (await c.get("/clinic/encounters", headers=h["reception"])).json() == []
        assert (await c.post("/clinic/encounters", json=_encounter(p1), headers=h["reception"])).status_code == 403
        assert (await c.put(f"/clinic/patients/{p1}", json={"allergies": "x"}, headers=h["reception"])).status_code == 403
        assert (await c.put(f"/clinic/patients/{p1}", json={"phone": "0111"}, headers=h["reception"])).status_code == 200
        assert (await c.post(f"/clinic/patients/{p1}/break-glass", json={"reason": "سبب طارئ واضح جداً"},
                             headers=h["reception"])).status_code == 403

        # Work queues: the pharmacist sees every prescription, the lab technician every lab order.
        rx = (await c.get("/clinic/prescriptions", headers=h["pharmacist"])).json()
        assert any(x["patient_id"] == p1 for x in rx)
        labs = (await c.get("/clinic/lab-orders", headers=h["lab"])).json()
        assert any(x["patient_id"] == p1 for x in labs)
        assert (await c.get("/clinic/encounters", headers=h["pharmacist"])).json() == []

        log = await _sql("SELECT resource, how, rows, patient_id FROM clinic_access_log WHERE tenant_id = :t",
                         t=env["tenant_id"])
        got = {(r[0], r[1]) for r in log}
        assert ("encounters", "team") in got
        assert ("prescriptions", "queue") in got and ("lab_orders", "queue") in got
        assert ("patient", "team") in got
        assert any(r[0] == "encounters" and r[3] == p1 and r[2] == 1 for r in log)


async def test_break_glass_opens_one_patient_for_the_window():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        p1 = await _patient(c, env, "مريض طارئ")
        p2 = await _patient(c, env, "مريض ثان")

        short = await c.post(f"/clinic/patients/{p1}/break-glass", json={"reason": "قصير"}, headers=h["doc_b"])
        assert short.status_code == 400
        r = await c.post(f"/clinic/patients/{p1}/break-glass", json={"reason": "المريض فاقد للوعي في الطوارئ"},
                         headers=h["doc_b"])
        assert r.status_code == 200, r.text
        grant_id = r.json()["id"]
        assert r.json()["expires_at"]

        ok = await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["doc_b"])
        assert ok.status_code == 200
        assert (await c.get(f"/clinic/patients/{p1}", headers=h["doc_b"])).json()["access"] == "break_glass"
        assert (await c.get("/clinic/encounters", params={"patient_id": p2}, headers=h["doc_b"])).status_code == 403
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["doc_a"])).status_code == 403

        log = await _sql("SELECT how FROM clinic_access_log WHERE tenant_id = :t AND patient_id = :p AND user_id = :u",
                         t=env["tenant_id"], p=p1, u=env["users"]["doc_b"].id)
        assert ("break_glass",) in log

        # Privacy officers were notified.
        notes = await _sql("SELECT user_id FROM notifications WHERE tenant_id = :t AND type = 'clinic_break_glass'",
                           t=env["tenant_id"])
        assert (env["users"]["manager"].id,) in notes

        await _sql("UPDATE clinic_access_grants SET expires_at = now() - interval '1 minute' WHERE id = :g", g=grant_id)
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["doc_b"])).status_code == 403

        # Privacy endpoints need clinic:privacy.
        for path in ("/clinic/access-log", "/clinic/break-glass"):
            assert (await c.get(path, headers=h["doc_a"])).status_code == 403
            assert (await c.get(path, headers=h["reception"])).status_code == 403
        assert (await c.post(f"/clinic/break-glass/{grant_id}/review", json={"note": "مبرر"},
                             headers=h["doc_b"])).status_code == 403

        grants = (await c.get("/clinic/break-glass", params={"unreviewed": True}, headers=h["manager"])).json()
        assert [g["id"] for g in grants] == [grant_id]
        assert grants[0]["state"] == "expired" and grants[0]["user_name"] == "د. بسمة الخارجية"
        reviewed = await c.post(f"/clinic/break-glass/{grant_id}/review", json={"note": "مبرر طبياً"}, headers=h["manager"])
        assert reviewed.status_code == 200 and reviewed.json()["review_note"] == "مبرر طبياً"
        assert (await c.get("/clinic/break-glass", params={"unreviewed": True}, headers=h["manager"])).json() == []

        logs = (await c.get("/clinic/access-log", params={"patient_id": p1}, headers=h["manager"])).json()
        assert logs["total"] >= 1 and logs["items"][0]["patient_name"] == "مريض طارئ"

        # A revoked grant closes access at once.
        again = (await c.post(f"/clinic/patients/{p2}/break-glass", json={"reason": "استشارة عاجلة من الطوارئ"},
                              headers=h["doc_b"])).json()
        assert (await c.get("/clinic/encounters", params={"patient_id": p2}, headers=h["doc_b"])).status_code == 200
        assert (await c.post(f"/clinic/break-glass/{again['id']}/revoke", headers=h["manager"])).status_code == 200
        assert (await c.get("/clinic/encounters", params={"patient_id": p2}, headers=h["doc_b"])).status_code == 403


async def test_setting_all_and_manager_all_patients():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        p1 = await _patient(c, env, "مريض العيادة الصغيرة")
        assert "clinic:all_patients" in standard_permissions("manager")
        assert "clinic:privacy" in standard_permissions("manager")
        assert "clinic:all_patients" not in standard_permissions("doctor")

        r = await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["manager"])
        assert r.status_code == 200
        assert (await c.get(f"/clinic/patients/{p1}", headers=h["manager"])).json()["access"] == "all"
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["nurse"])).status_code == 403

        await _sql("INSERT INTO store_settings (id, tenant_id, key, value) VALUES (gen_random_uuid(), :t, "
                   "'mod_settings_healthcare_clinic', :v)", t=env["tenant_id"], v=json.dumps({"patient_access": "all"}))
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["nurse"])).status_code == 200
        assert (await c.post("/clinic/encounters", json=_encounter(p1), headers=h["doc_b"])).status_code == 200
        assert (await c.get(f"/clinic/patients/{p1}", headers=h["doc_b"])).json()["access"] == "setting"
        # The setting opens patients to clinicians, never to reception.
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["reception"])).status_code == 403
        assert (await c.get(f"/clinic/patients/{p1}", headers=h["reception"])).json()["allergies"] is None


async def test_care_team_management():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        p1 = await _patient(c, env, "مريض الفريق الطبي")
        assert (await _book(c, env, p1, "doc_a")).status_code == 200
        assert (await _book(c, env, p1, "doc_a")).status_code == 200  # booking again doesn't duplicate

        team = (await c.get(f"/clinic/patients/{p1}/care-team", headers=h["reception"])).json()
        assert [m["user_id"] for m in team] == [str(env["users"]["doc_a"].id)]
        assert team[0]["role"] == "attending"

        # A clinician can't open a record by putting themselves on its team (or booking themselves).
        doc_b = str(env["users"]["doc_b"].id)
        selfadd = await c.post(f"/clinic/patients/{p1}/care-team", json={"user_id": doc_b}, headers=h["doc_b"])
        assert selfadd.status_code == 403
        assert (await _book_as(c, env, p1, "doc_b", "doc_b")).status_code == 403
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["doc_b"])).status_code == 403
        assert (await _book_as(c, env, p1, "doc_a", "doc_a")).status_code == 200  # already on the team

        nurse_id = str(env["users"]["nurse"].id)
        added = await c.post(f"/clinic/patients/{p1}/care-team", json={"user_id": nurse_id, "role": "nurse"},
                             headers=h["reception"])
        assert added.status_code == 200, added.text
        dup = await c.post(f"/clinic/patients/{p1}/care-team", json={"user_id": nurse_id, "role": "nurse"},
                           headers=h["reception"])
        assert dup.status_code == 409
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["nurse"])).status_code == 200

        removed = await c.delete(f"/clinic/patients/{p1}/care-team/{added.json()['id']}", headers=h["reception"])
        assert removed.status_code == 204
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=h["nurse"])).status_code == 403

        audit = await _sql("SELECT action FROM audit_log WHERE tenant_id = :t AND entity_type = 'clinic_care_team'",
                           t=env["tenant_id"])
        assert {("add_member",), ("remove_member",)} <= set(audit)


async def test_backfill_links_records_by_doctor_name():
    from app.activities.healthcare.modules.healthcare_clinic.migrate import backfill_care_team

    env = await _env()
    async with _client() as c:
        p1 = await _patient(c, env, "مريض قديم")
        r = await c.post("/clinic/appointments", headers=env["h"]["reception"], json={
            "patient_id": p1, "doctor_name": "د. أحمد الفريق", "department": "باطنة",
            "appointment_date": "2026-11-14", "time_slot": "10:00 AM"})
        assert r.status_code == 200 and r.json()["doctor_user_id"] is None
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=env["h"]["doc_a"])).status_code == 403

        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await backfill_care_team(s)
            await backfill_care_team(s)
            await s.commit()
        rows = await _sql("SELECT count(*) FROM clinic_care_team WHERE patient_id = :p AND ended_at IS NULL", p=p1)
        assert rows[0][0] == 1
        assert (await c.get("/clinic/encounters", params={"patient_id": p1}, headers=env["h"]["doc_a"])).status_code == 200
