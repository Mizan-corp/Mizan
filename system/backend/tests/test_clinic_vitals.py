"""Vitals trends (#42): GET /clinic/patients/{id}/vitals-history is a clinical read."""
import os

import pytest

from tests.test_clinic_patient_access import _book, _client, _encounter, _env, _lab, _patient, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def test_vitals_history_needs_the_record_and_is_logged():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        pid = await _patient(c, env, "مريض السكر")
        assert (await _book(c, env, pid, "doc_a")).status_code == 200
        # Two visits, entered out of order; the second without glucose.
        second = {**_encounter(pid), "encounter_date": "2026-11-10", "bp_systolic": 150, "bp_diastolic": 95,
                  "heart_rate": 88, "spo2": 96, "temperature": 37.4}
        first = {**_encounter(pid), "encounter_date": "2026-10-01", "bp_systolic": 135, "bp_diastolic": 85,
                 "heart_rate": 76, "blood_glucose": 182}
        assert (await c.post("/clinic/encounters", json=second, headers=h["doc_a"])).status_code == 200
        assert (await c.post("/clinic/encounters", json=first, headers=h["doc_a"])).status_code == 200
        assert (await c.post("/clinic/encounters", json={**first, "blood_glucose": 5000}, headers=h["doc_a"])).status_code == 422
        lab = await c.post("/clinic/lab-orders", json={**_lab(pid), "test_name": "سكر صائم FBS"}, headers=h["doc_a"])
        await c.post(f"/clinic/lab-orders/{lab.json()['id']}/result", headers=h["lab"],
                     json={"result_value": "126", "numeric_value": 126, "unit": "mg/dL", "is_signed_off": True})

        # Not on the care team, and reception / lab: refused.
        for who in ("doc_b", "reception", "lab", "pharmacist"):
            r = await c.get(f"/clinic/patients/{pid}/vitals-history", headers=h[who])
            assert r.status_code == 403, who

        r = await c.get(f"/clinic/patients/{pid}/vitals-history", headers=h["doc_a"])
        assert r.status_code == 200, r.text
        data = r.json()
        assert [p["date"] for p in data["points"]] == ["2026-10-01", "2026-11-10"]
        assert data["points"][0]["blood_glucose"] == 182 and data["points"][1]["blood_glucose"] is None
        assert data["points"][1]["bp_systolic"] == 150 and data["points"][1]["bp_diastolic"] == 95
        assert data["points"][1]["spo2"] == 96 and data["points"][1]["temperature"] == 37.4
        assert [g["value"] for g in data["glucose_labs"]] == [126]

        logged = await _sql("SELECT how, rows FROM clinic_access_log WHERE patient_id = :p AND resource = 'vitals'", p=pid)
        assert logged == [("team", 3)]

        # Break-glass opens it for doc_b, and that is what the log says.
        assert (await c.post(f"/clinic/patients/{pid}/break-glass", json={"reason": "حالة طارئة في الطوارئ"},
                             headers=h["doc_b"])).status_code == 200
        assert (await c.get(f"/clinic/patients/{pid}/vitals-history", headers=h["doc_b"])).status_code == 200
        hows = {row[0] for row in await _sql("SELECT how FROM clinic_access_log WHERE patient_id = :p AND resource = 'vitals'", p=pid)}
        assert hows == {"team", "break_glass"}
