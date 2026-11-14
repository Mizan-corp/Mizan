"""Departments, rooms and doctors' rosters (#36): master data, roster-filtered slots, no overlaps."""
import os

import pytest

from app.activities.healthcare.modules.healthcare_clinic.scheduling import DEFAULT_DEPARTMENTS, parse_slot
from tests.test_clinic_patient_access import _client, _env, _patient

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

MONDAY = "2026-11-16"  # weekday() == 0


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


def test_slot_times_old_and_new():
    assert parse_slot("11:30 AM") == 11 * 60 + 30
    assert parse_slot("12:15 PM") == 12 * 60 + 15
    assert parse_slot("12:00 AM") == 0
    assert parse_slot("02:30 م") == 14 * 60 + 30
    assert parse_slot("14:05") == 14 * 60 + 5
    assert parse_slot("9") == 9 * 60
    assert parse_slot("25:00") is None and parse_slot("13:00 PM") is None and parse_slot("بعد الظهر") is None


async def _setup(c, env):
    h = env["h"]
    deps = (await c.get("/clinic/departments", headers=h["reception"])).json()
    assert len(deps) == len(DEFAULT_DEPARTMENTS)  # seeded on first read
    assert len((await c.get("/clinic/departments", headers=h["doc_a"])).json()) == len(DEFAULT_DEPARTMENTS)  # idempotent
    im = next(d for d in deps if d["code"] == "IM")
    ped = next(d for d in deps if d["code"] == "PED")
    room = (await c.post("/clinic/rooms", json={"name": "غرفة 1", "department_id": im["id"]}, headers=h["reception"])).json()
    return im, ped, room


async def test_master_data_is_managed_by_the_front_desk_only():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        im, _, room = await _setup(c, env)
        assert (await c.post("/clinic/departments", json={"code": "card", "name": "القلب"}, headers=h["doc_a"])).status_code == 403
        r = await c.post("/clinic/departments", json={"code": "card", "name": "القلب", "specialty_code": "cardiology"}, headers=h["reception"])
        assert r.status_code == 200 and r.json()["code"] == "CARD"
        assert (await c.post("/clinic/departments", json={"code": "CARD", "name": "قلب 2"}, headers=h["reception"])).status_code == 409
        assert (await c.post("/clinic/rooms", json={"name": "x"}, headers=h["nurse"])).status_code == 403

        sched = {"doctor_user_id": str(env["users"]["doc_a"].id), "department_id": im["id"], "room_id": room["id"],
                 "weekday": 0, "start_time": "09:00", "end_time": "11:00", "slot_minutes": 20}
        assert (await c.post("/clinic/schedules", json=sched, headers=h["doc_a"])).status_code == 403
        # Nurses don't get rosters; end before start is refused.
        assert (await c.post("/clinic/schedules", json={**sched, "doctor_user_id": str(env["users"]["nurse"].id)},
                             headers=h["reception"])).status_code == 400
        assert (await c.post("/clinic/schedules", json={**sched, "end_time": "08:00"}, headers=h["reception"])).status_code == 400
        assert (await c.post("/clinic/schedules", json=sched, headers=h["reception"])).status_code == 200
        # Another doctor in the same room at an overlapping time, or the same doctor twice: refused.
        other = {**sched, "doctor_user_id": str(env["users"]["doc_b"].id), "start_time": "10:00", "end_time": "12:00"}
        assert (await c.post("/clinic/schedules", json=other, headers=h["reception"])).status_code == 409
        assert (await c.post("/clinic/schedules", json={**sched, "room_id": None, "start_time": "10:40", "end_time": "12:00"},
                             headers=h["reception"])).status_code == 409
        assert (await c.post("/clinic/schedules", json={**other, "room_id": None}, headers=h["reception"])).status_code == 200


async def test_roster_filters_doctors_and_offers_its_slots():
    env = await _env()
    h = env["h"]
    doc_a, doc_b = str(env["users"]["doc_a"].id), str(env["users"]["doc_b"].id)
    async with _client() as c:
        im, ped, room = await _setup(c, env)
        await c.post("/clinic/schedules", headers=h["reception"], json={
            "doctor_user_id": doc_a, "department_id": im["id"], "room_id": room["id"],
            "weekday": 0, "start_time": "09:00", "end_time": "10:00", "slot_minutes": 20})
        await c.post("/clinic/schedules", headers=h["reception"], json={
            "doctor_user_id": doc_b, "department_id": ped["id"], "weekday": 1, "start_time": "16:00", "end_time": "18:00"})

        in_im = {d["id"] for d in (await c.get("/clinic/clinicians", params={"department_id": im["id"]}, headers=h["reception"])).json()}
        assert in_im == {doc_a}
        in_ped = {d["id"] for d in (await c.get("/clinic/clinicians", params={"department_id": ped["id"]}, headers=h["reception"])).json()}
        assert in_ped == {doc_b}

        slots = (await c.get("/clinic/schedule/slots", params={"doctor_user_id": doc_a, "date": MONDAY}, headers=h["reception"])).json()
        assert slots["has_roster"] and [s["time"] for s in slots["slots"]] == ["09:00", "09:20", "09:40"]
        assert all(s["available"] and s["room_name"] == "غرفة 1" for s in slots["slots"])
        tuesday = (await c.get("/clinic/schedule/slots", params={"doctor_user_id": doc_a, "date": "2026-11-17"}, headers=h["reception"])).json()
        assert tuesday == {"slots": [], "has_roster": True}

        pid = await _patient(c, env, "مريض الجدول")
        book = {"patient_id": pid, "doctor_user_id": doc_a, "department_id": im["id"], "appointment_date": MONDAY}
        # Outside the roster, or not at a slot start: refused.
        assert (await c.post("/clinic/appointments", json={**book, "time_slot": "11:00"}, headers=h["reception"])).status_code == 400
        assert (await c.post("/clinic/appointments", json={**book, "time_slot": "09:10"}, headers=h["reception"])).status_code == 400
        assert (await c.post("/clinic/appointments", json={**book, "time_slot": "nonsense"}, headers=h["reception"])).status_code == 400
        r = await c.post("/clinic/appointments", json={**book, "time_slot": "9:20 AM"}, headers=h["reception"])
        assert r.status_code == 200, r.text
        appt = r.json()
        assert appt["time_slot"] == "09:20" and appt["room_id"] == room["id"]
        assert appt["department_id"] == im["id"] and appt["department"] == im["name"]

        slots = (await c.get("/clinic/schedule/slots", params={"doctor_user_id": doc_a, "date": MONDAY}, headers=h["reception"])).json()
        assert [s["available"] for s in slots["slots"]] == [True, False, True]


async def test_overlapping_appointments_are_refused():
    env = await _env()
    h = env["h"]
    doc_a, doc_b = str(env["users"]["doc_a"].id), str(env["users"]["doc_b"].id)
    async with _client() as c:
        im, _, room = await _setup(c, env)
        p1 = await _patient(c, env, "مريض أول")
        p2 = await _patient(c, env, "مريض ثان")

        # Unrostered doctors: the same doctor at an overlapping time (15 minutes by default) is refused.
        base = {"department_id": im["id"], "appointment_date": MONDAY}
        assert (await c.post("/clinic/appointments", json={**base, "patient_id": p1, "doctor_user_id": doc_b, "time_slot": "12:00"},
                             headers=h["reception"])).status_code == 200
        r = await c.post("/clinic/appointments", json={**base, "patient_id": p2, "doctor_user_id": doc_b, "time_slot": "12:10 PM"},
                         headers=h["reception"])
        assert r.status_code == 409 and "د. بسمة" in r.json()["detail"]
        ok = await c.post("/clinic/appointments", json={**base, "patient_id": p2, "doctor_user_id": doc_b, "time_slot": "12:15"},
                          headers=h["reception"])
        assert ok.status_code == 200
        # The same room with another doctor at the same time: refused.
        assert (await c.post("/clinic/appointments", json={**base, "patient_id": p1, "doctor_user_id": doc_a, "time_slot": "13:00",
                                                           "room_id": room["id"]}, headers=h["reception"])).status_code == 200
        r = await c.post("/clinic/appointments", json={**base, "patient_id": p2, "doctor_user_id": doc_b, "time_slot": "13:00",
                                                       "room_id": room["id"]}, headers=h["reception"])
        assert r.status_code == 409 and "غرفة" in r.json()["detail"]

        # A cancelled appointment frees its time; rescheduling into a taken one is refused.
        assert (await c.post(f"/clinic/appointments/{ok.json()['id']}/cancel", json={"reason": "اعتذار"}, headers=h["reception"])).status_code == 200
        again = await c.post("/clinic/appointments", json={**base, "patient_id": p1, "doctor_user_id": doc_b, "time_slot": "12:15"},
                             headers=h["reception"])
        assert again.status_code == 200
        r = await c.post(f"/clinic/appointments/{again.json()['id']}/reschedule", json={"new_date": MONDAY, "new_time_slot": "12:05"},
                         headers=h["reception"])
        assert r.status_code == 409
        r = await c.post(f"/clinic/appointments/{again.json()['id']}/reschedule", json={"new_date": MONDAY, "new_time_slot": "2:30 PM"},
                         headers=h["reception"])
        assert r.status_code == 200 and r.json()["time_slot"] == "14:30"
