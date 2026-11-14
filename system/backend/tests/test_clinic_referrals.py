"""Referrals (#45): a doctor refers, the receiving department's doctors see it, accepting puts the
receiving doctor on the care team; the encounter summary is a logged clinical read."""
import os

import pytest

from tests.test_clinic_patient_access import _book, _client, _encounter, _env, _patient, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def _departments(c, env):
    deps = (await c.get("/clinic/departments", headers=env["h"]["reception"])).json()
    return {d["code"]: d for d in deps}


async def test_referral_accepted_joins_the_care_team():
    env = await _env()
    h = env["h"]
    doc_b = str(env["users"]["doc_b"].id)
    async with _client() as c:
        deps = await _departments(c, env)
        ped = deps["PED"]
        # doc_b is on the paediatrics roster.
        assert (await c.post("/clinic/schedules", headers=h["reception"], json={
            "doctor_user_id": doc_b, "department_id": ped["id"], "weekday": 2,
            "start_time": "10:00", "end_time": "12:00"})).status_code == 200
        pid = await _patient(c, env, "مريض محال")
        assert (await _book(c, env, pid, "doc_a")).status_code == 200
        enc = await c.post("/clinic/encounters", json=_encounter(pid), headers=h["doc_a"])
        assert enc.status_code == 200

        body = {"patient_id": pid, "to_department_id": ped["id"], "priority": "urgent",
                "reason": "اشتباه التهاب رئوي عند طفل", "triage_notes": "حرارة 39 وضيق تنفس", "encounter_id": enc.json()["id"]}
        # Only doctors refer, and only patients they reach.
        assert (await c.post("/clinic/referrals", json=body, headers=h["nurse"])).status_code == 403
        assert (await c.post("/clinic/referrals", json=body, headers=h["doc_b"])).status_code == 403
        # A doctor not on the department's roster can't be named.
        assert (await c.post("/clinic/referrals", json={**body, "to_doctor_user_id": str(env["users"]["manager"].id)},
                             headers=h["doc_a"])).status_code == 400
        r = await c.post("/clinic/referrals", json=body, headers=h["doc_a"])
        assert r.status_code == 200, r.text
        ref = r.json()
        assert ref["status"] == "pending" and ref["direction"] == "outgoing"

        # doc_b (rostered in paediatrics) receives it with the triage notes, not yet the record.
        incoming = (await c.get("/clinic/referrals", params={"box": "incoming"}, headers=h["doc_b"])).json()
        assert [x["id"] for x in incoming] == [ref["id"]]
        assert incoming[0]["triage_notes"] == "حرارة 39 وضيق تنفس" and incoming[0]["can_respond"]
        assert (await c.get("/clinic/referrals", params={"box": "incoming"}, headers=h["doc_a"])).json() == []
        detail = (await c.get(f"/clinic/referrals/{ref['id']}", headers=h["doc_b"])).json()
        assert detail["record_access"] is False and detail["last_encounter"] is None
        assert (await c.get("/clinic/encounters", params={"patient_id": pid}, headers=h["doc_b"])).status_code == 403
        # The front desk coordinates without the clinical text; the nurse sees nothing.
        everything = (await c.get("/clinic/referrals", params={"box": "all"}, headers=h["reception"])).json()
        assert everything[0]["id"] == ref["id"] and everything[0]["reason"] is None
        assert (await c.get("/clinic/referrals", params={"box": "all"}, headers=h["nurse"])).status_code == 403
        assert (await c.get(f"/clinic/referrals/{ref['id']}", headers=h["nurse"])).status_code == 403
        # The sender can't accept their own referral.
        assert (await c.post(f"/clinic/referrals/{ref['id']}/accept", json={}, headers=h["doc_a"])).status_code == 403

        acc = await c.post(f"/clinic/referrals/{ref['id']}/accept", json={}, headers=h["doc_b"])
        assert acc.status_code == 200 and acc.json()["status"] == "accepted"
        assert (await c.post(f"/clinic/referrals/{ref['id']}/accept", json={}, headers=h["doc_b"])).status_code == 409
        team = (await c.get(f"/clinic/patients/{pid}/care-team", headers=h["reception"])).json()
        assert any(m["user_id"] == doc_b and m["role"] == "consultant" for m in team)
        # Now the record is theirs: the encounter summary comes with the referral, and it is logged.
        detail = (await c.get(f"/clinic/referrals/{ref['id']}", headers=h["doc_b"])).json()
        assert detail["record_access"] and detail["last_encounter"]["encounter_ref"] == enc.json()["encounter_ref"]
        assert (await c.get("/clinic/encounters", params={"patient_id": pid}, headers=h["doc_b"])).status_code == 200
        logged = await _sql("SELECT count(*) FROM clinic_access_log WHERE patient_id = :p AND resource = 'referral' "
                            "AND user_id = :u", p=pid, u=env["users"]["doc_b"].id)
        assert logged[0][0] >= 1

        done = await c.post(f"/clinic/referrals/{ref['id']}/complete", json={"note": "تم العلاج"}, headers=h["doc_b"])
        assert done.status_code == 200 and done.json()["status"] == "completed"
        notes = await _sql("SELECT count(*) FROM notifications WHERE type = 'clinic_referral' AND user_id = :u",
                           u=env["users"]["doc_a"].id)
        assert notes[0][0] == 1  # the sender heard it was accepted


async def test_named_doctor_receives_and_declines_with_a_reason():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        deps = await _departments(c, env)
        pid = await _patient(c, env, "مريض جلدية")
        assert (await _book(c, env, pid, "doc_a")).status_code == 200
        r = await c.post("/clinic/referrals", headers=h["doc_a"], json={
            "patient_id": pid, "to_department_id": deps["DERM"]["id"], "to_doctor_user_id": str(env["users"]["doc_b"].id),
            "reason": "طفح جلدي مزمن"})
        assert r.status_code == 200, r.text
        ref = r.json()
        assert ref["to_doctor_name"] == "د. بسمة الخارجية"
        assert (await c.post(f"/clinic/referrals/{ref['id']}/decline", json={"note": ""}, headers=h["doc_b"])).status_code == 400
        d = await c.post(f"/clinic/referrals/{ref['id']}/decline", json={"note": "خارج تخصصي الدقيق"}, headers=h["doc_b"])
        assert d.status_code == 200 and d.json()["status"] == "declined"
        team = (await c.get(f"/clinic/patients/{pid}/care-team", headers=h["reception"])).json()
        assert str(env["users"]["doc_b"].id) not in {m["user_id"] for m in team}
