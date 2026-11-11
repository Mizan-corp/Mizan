"""Storage quota (ADR-006 D3): measured by module; at 100% uploads are refused while daily work
(sales) goes on."""
import base64

from helpers import uid

from conftest import owner_api, reg, db, wh  # noqa: F401

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def test_storage_is_measured_and_a_full_workspace_refuses_uploads(owner_api, reg, db):
    usage = owner_api.ok(owner_api.get("/settings/storage", params={"refresh": "true"}))
    assert usage["used_bytes"] > 0 and usage["limit_bytes"] > 0 and usage["state"] in ("ok", "warn", "full")
    assert any(m["module"] == "sales" for m in usage["by_module"]) and all(m.get("name") for m in usage["by_module"])

    tid = owner_api.ok(owner_api.get("/auth/me"))["tenant_id"]
    sub = owner_api.ok(owner_api.get("/products", params={"limit": 1}))
    sub_id = (sub.get("items", sub) if isinstance(sub, dict) else sub)[0]["subcategory_id"]
    product = owner_api.ok(owner_api.post("/products", json={"subcategory_id": sub_id, "name": "E2E storage " + uid("s")}))
    reg.add("product", product["id"])
    try:
        db.q("UPDATE storage_usage SET total_bytes = %s, measured_at = now() WHERE tenant_id = %s", (usage["limit_bytes"], tid))
        full = owner_api.ok(owner_api.get("/settings/storage"))
        assert full["state"] == "full"
        r = owner_api.client.post(f"/products/{product['id']}/image", files={"file": ("x.png", PNG, "image/png")},
                                  headers={"X-CSRF-Token": owner_api.client.cookies.get("csrf_token") or ""})
        assert r.status_code == 413, r.text[:200]
    finally:
        db.q("UPDATE storage_usage SET measured_at = now() - interval '1 day' WHERE tenant_id = %s", (tid,))
        owner_api.ok(owner_api.get("/settings/storage", params={"refresh": "true"}))
