"""Uploaded files go through one service (#114): stored per workspace, replaced files deleted,
sizes counted in the storage quota. Locally the files service writes to the disk."""
import base64
import uuid

from helpers import uid

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")


def _upload(api, path, name="x.png", data=PNG, kind="image/png"):
    return api.client.post(path, files={"file": (name, data, kind)},
                           headers={"X-CSRF-Token": api.client.cookies.get("csrf_token") or ""})


def test_a_product_image_is_stored_per_workspace_and_replaced(admin_api, subcategory, reg, db):
    tid = admin_api.ok(admin_api.get("/auth/me"))["tenant_id"]
    product = admin_api.ok(admin_api.post("/products", json={
        "subcategory_id": subcategory["id"], "name": "E2E-PROD-" + uid("f"), "unit": "عدد", "retail_price": "5"}), 200, 201)
    reg.add("product", product["id"])
    try:
        first = admin_api.ok(_upload(admin_api, f"/products/{product['id']}/image"))["image_url"]
        assert first.startswith(f"/uploads/t/{tid}/product_image/{product['id']}-")
        assert admin_api.client.get(first).content == PNG

        second = admin_api.ok(_upload(admin_api, f"/products/{product['id']}/image"))["image_url"]
        assert second != first
        assert admin_api.client.get(first).status_code == 404  # the replaced file is gone
        assert admin_api.client.get(second).status_code == 200
        rows = db.q("SELECT url, size, kind FROM workspace_files WHERE tenant_id = %s AND owner_id = %s",
                    (tid, product["id"]))
        assert [(r[0], r[1], r[2]) for r in rows] == [(second, len(PNG), "product_image")]

        # A measurement taken moments ago is reused; age it so this one counts the new file.
        db.q("UPDATE storage_usage SET measured_at = now() - interval '1 day' WHERE tenant_id = %s", (tid,))
        usage = admin_api.ok(admin_api.get("/settings/storage", params={"refresh": "true"}))
        files = next(m for m in usage["by_module"] if m["module"] == "files")
        assert files["bytes"] >= len(PNG)
    finally:
        db.q("DELETE FROM workspace_files WHERE owner_id = %s", (product["id"],))


def test_a_purchase_invoice_needs_its_order(admin_api):
    r = _upload(admin_api, f"/purchases/{uuid.uuid4()}/upload-invoice", "inv.pdf", b"%PDF-1.4 e2e", "application/pdf")
    assert r.status_code == 404, r.text[:200]


def test_unsupported_files_are_refused(admin_api, product):
    r = _upload(admin_api, f"/products/{product['id']}/image", "x.exe", b"MZ", "application/octet-stream")
    assert r.status_code == 400
