"""How a workspace is composed (ADR-006 D2): what it may install for its activity, and removing a
module: preview, typed `delete`, keep the data 30 days (reinstalling restores it) or delete it
now after an export; modules the activity's variants use can't be removed."""
import gzip
import json

import pytest
from helpers import uid

from conftest import owner_api, db  # noqa: F401


@pytest.fixture
def pharmacy(owner_api, db):
    tid = owner_api.ok(owner_api.get("/auth/me"))["tenant_id"]
    before = db.one("SELECT sector, active_modules FROM tenants WHERE id = %s", (tid,))
    db.q("UPDATE tenants SET sector = 'pharmacy', active_modules = active_modules || '[\"batches\"]'::jsonb WHERE id = %s", (tid,))
    try:
        yield tid
    finally:
        db.q("UPDATE tenants SET sector = %s, active_modules = %s::jsonb WHERE id = %s", (before[0], json.dumps(before[1]), tid))
        db.q("DELETE FROM module_retention WHERE tenant_id = %s", (tid,))


def test_install_rules_follow_the_activity(owner_api, pharmacy):
    catalog = {m["id"]: m for m in owner_api.ok(owner_api.get("/modules"))["catalog"]}
    assert catalog["healthcare_clinic"]["installable"]  # same family (health)
    assert not catalog["restaurant"]["installable"] and catalog["restaurant"]["not_installable_reason"]
    assert owner_api.post("/modules/restaurant/toggle", json={"enabled": True}).status_code == 403
    assert owner_api.post("/modules/pos/toggle", json={"enabled": False}).status_code == 409  # removal has its own flow
    preview = owner_api.ok(owner_api.get("/modules/batches/uninstall-preview"))
    assert preview["blocked_by"]  # the pharmacy's variants use batches
    assert owner_api.post("/modules/batches/uninstall", json={"confirm": "delete", "data": "keep"}).status_code == 409
    assert owner_api.post("/modules/presets/apply", json={"preset_id": "retail"}).status_code == 410


def test_uninstall_keeps_then_restores_then_deletes_with_an_export(owner_api, pharmacy, db):
    owner_api.ok(owner_api.post("/modules/healthcare_clinic/toggle", json={"enabled": True}))
    mrn = "E2E-" + uid("m")
    patient = owner_api.ok(owner_api.post("/clinic/patients", json={
        "patient_mrn": mrn, "full_name": "مريض تجربة", "national_id": "29001010000000", "phone": "0100",
        "gender": "male", "date_of_birth": "1990-01-01"}), 200, 201)

    preview = owner_api.ok(owner_api.get("/modules/healthcare_clinic/uninstall-preview"))
    assert any(d["table"] == "clinic_patients" and d["rows"] >= 1 for d in preview["data"])
    assert owner_api.post("/modules/healthcare_clinic/uninstall", json={"confirm": "nope", "data": "keep"}).status_code == 422

    kept = owner_api.ok(owner_api.post("/modules/healthcare_clinic/uninstall", json={"confirm": "delete", "data": "keep"}))
    assert "healthcare_clinic" in kept["removed"] and kept["purge_after"]
    assert owner_api.get("/clinic/patients").status_code in (403, 404)  # hidden
    assert db.one("SELECT count(*) FROM clinic_patients WHERE patient_mrn = %s", (mrn,))[0] == 1  # still there

    back = owner_api.ok(owner_api.post("/modules/healthcare_clinic/toggle", json={"enabled": True}))
    assert "healthcare_clinic" in back["restored"]
    assert db.one("SELECT count(*) FROM clinic_patients WHERE patient_mrn = %s", (mrn,))[0] == 1

    gone = owner_api.ok(owner_api.post("/modules/healthcare_clinic/uninstall", json={"confirm": "delete", "data": "delete"}))
    assert gone["mode"] == "delete"
    assert db.one("SELECT count(*) FROM clinic_patients WHERE patient_mrn = %s", (mrn,))[0] == 0
    entry = next(r for r in owner_api.ok(owner_api.get("/modules/retention"))
                 if r["module_id"] == "healthcare_clinic" and r["mode"] == "deleted")
    r = owner_api.get(f"/modules/retention/{entry['id']}/export")
    assert r.status_code == 200
    dump = json.loads(gzip.decompress(r.content))
    assert any(p.get("patient_mrn") == mrn for p in dump["tables"]["clinic_patients"])
    assert patient
