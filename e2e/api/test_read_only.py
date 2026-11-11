"""A workspace whose trial or paid period ended is read-only (#66): writes are refused, reading,
printing and signing out keep working, and renewing makes it writable again at once."""
from conftest import admin_api, db  # noqa: F401


def _workspace(admin_api):
    return admin_api.ok(admin_api.get("/auth/me"))["tenant_id"]


def test_lapsed_workspace_is_read_only(admin_api, db):
    tid = _workspace(admin_api)
    before = db.one("SELECT plan, trial_ends_at, paid_until FROM tenants WHERE id = %s", (tid,))
    try:
        db.q("UPDATE tenants SET plan = 'pro', trial_ends_at = NULL, paid_until = now() - interval '1 minute' WHERE id = %s", (tid,))
        r = admin_api.post("/customers", json={"name": "E2E read-only"})
        assert r.status_code == 403 and r.headers.get("x-mizan-read-only") == "paid", r.text[:200]
        assert admin_api.get("/customers").status_code == 200
        assert admin_api.post("/auth/print-token", json={}).status_code == 200

        db.q("UPDATE tenants SET plan = 'trial', paid_until = NULL, trial_ends_at = now() - interval '1 minute' WHERE id = %s", (tid,))
        r = admin_api.post("/customers", json={"name": "E2E read-only"})
        assert r.status_code == 403 and r.headers.get("x-mizan-read-only") == "trial", r.text[:200]

        db.q("UPDATE tenants SET plan = 'pro', trial_ends_at = NULL, paid_until = now() + interval '1 day' WHERE id = %s", (tid,))
        r = admin_api.post("/customers", json={"name": "E2E-renewed " + tid[:6]})
        assert r.status_code in (200, 201), r.text[:200]
        db.q("DELETE FROM customers WHERE id = %s", (r.json()["id"],))
    finally:
        db.q("UPDATE tenants SET plan = %s, trial_ends_at = %s, paid_until = %s WHERE id = %s", (*before, tid))
