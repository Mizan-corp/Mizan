"""Server-side search and pagination of the clinic's patients and appointments (#39)."""
import os
import uuid

import pytest

from tests.test_clinic_patient_access import _book, _client, _env, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def _register(c, env, name: str, phone: str, national_id: str) -> str:
    r = await c.post("/clinic/patients", headers=env["h"]["reception"], json={
        "patient_mrn": f"MRN-{uuid.uuid4().hex[:8]}", "full_name": name, "national_id": national_id,
        "phone": phone, "gender": "ذكر", "date_of_birth": "1980-01-01", "allergies": "بنسلين"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def test_patients_search_and_pages():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        ids = [await _register(c, env, f"مريض الصفحات {i}", f"0109{i:07d}", f"2900{i:010d}") for i in range(7)]
        await _register(c, env, "ياسمين المختلفة", "01555555555", "29999999999999")

        first = (await c.get("/clinic/patients", params={"page_size": 3}, headers=h["reception"])).json()
        assert set(first) == {"items", "total", "page", "pages"}
        assert first["total"] == 8 and first["pages"] == 3 and first["page"] == 1 and len(first["items"]) == 3
        last = (await c.get("/clinic/patients", params={"page_size": 3, "page": 3}, headers=h["reception"])).json()
        assert len(last["items"]) == 2
        seen = {p["id"] for page in (1, 2, 3) for p in (await c.get(
            "/clinic/patients", params={"page_size": 3, "page": page}, headers=h["reception"])).json()["items"]}
        assert len(seen) == 8

        assert (await c.get("/clinic/patients", params={"search": "ياسمين"}, headers=h["reception"])).json()["total"] == 1
        assert (await c.get("/clinic/patients", params={"search": "01555"}, headers=h["reception"])).json()["total"] == 1
        assert (await c.get("/clinic/patients", params={"search": "29999999"}, headers=h["reception"])).json()["total"] == 1
        assert (await c.get("/clinic/patients", params={"search": "الصفحات"}, headers=h["reception"])).json()["total"] == 7
        assert (await c.get("/clinic/patients", params={"page_size": 101}, headers=h["reception"])).status_code == 422
        assert (await c.get("/clinic/patients", params={"page": 0}, headers=h["reception"])).status_code == 422

        # Redaction and the access log hold per page (#113).
        assert all(p["allergies"] is None for p in first["items"])
        assert (await _book(c, env, ids[0], "doc_a")).status_code == 200
        found = (await c.get("/clinic/patients", params={"search": "مريض الصفحات 0"}, headers=h["doc_a"])).json()
        assert found["items"][0]["allergies"] == "بنسلين"
        log = await _sql("SELECT rows FROM clinic_access_log WHERE tenant_id = :t AND user_id = :u AND resource = 'patient'",
                         t=env["tenant_id"], u=env["users"]["doc_a"].id)
        assert (1,) in log


async def test_appointments_search_filters_and_pages():
    env = await _env()
    h = env["h"]
    async with _client() as c:
        a = await _register(c, env, "حسام الدين", "0100", "1")
        b = await _register(c, env, "منار يوسف", "0101", "2")
        for pid in (a, a, b):
            assert (await _book(c, env, pid, "doc_a")).status_code == 200

        all_ = (await c.get("/clinic/appointments", params={"page_size": 2}, headers=h["nurse"])).json()
        assert all_["total"] == 3 and all_["pages"] == 2 and len(all_["items"]) == 2
        assert (await c.get("/clinic/appointments", params={"search": "منار"}, headers=h["nurse"])).json()["total"] == 1
        assert (await c.get("/clinic/appointments", params={"search": "أحمد الفريق"}, headers=h["nurse"])).json()["total"] == 3
        r = await c.get("/clinic/appointments", params={"search": "حسام", "status": "scheduled",
                                                          "appointment_date": "2026-11-14"}, headers=h["nurse"])
        assert r.json()["total"] == 2
        assert (await c.get("/clinic/appointments", params={"status": "completed"}, headers=h["nurse"])).json()["total"] == 0
