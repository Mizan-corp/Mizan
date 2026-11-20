"""Printed documents (PLAT-5): /print/* need a print token of a user with the document's permission
and branch; unknown documents are 404s; a browser tab gets errors as an Arabic page."""
import uuid

from conftest import (admin_api, cashier_api, ensure_shift, product, reg, supplier, wh)  # noqa: F401


def _token(api) -> str:
    return api.ok(api.post("/auth/print-token", json={}))["token"]


def _print(api, path: str, **headers):
    return api.client.get(path, params={"token": _token(api)}, headers=headers)


def test_documents_print_for_their_permission_only(admin_api, cashier_api, reg, product, supplier, wh):
    ensure_shift(admin_api, reg, wh["id"])
    sale = admin_api.ok(admin_api.post("/sales", json={
        "warehouse_id": wh["id"], "items": [{"product_id": product["id"], "qty": 1, "unit_price": product["retail_price"]}]}))
    reg.add("sale", sale["id"])
    po = admin_api.ok(admin_api.post("/purchases", json={
        "supplier_id": supplier["id"], "warehouse_id": wh["id"],
        "items": [{"product_id": product["id"], "qty": 1, "unit_cost": "60"}]}))
    reg.add("purchase_order", po["id"])
    docs = admin_api.ok(admin_api.get("/archive", params={"limit": 5}))
    paths = [f"/print/sale/{sale['id']}", f"/print/purchase/{po['id']}", f"/print/inventory/{wh['id']}"]
    if docs:
        paths.append(f"/print/archive/{docs[0]['id']}")
    for path in paths:
        r = _print(admin_api, path)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/html"), (path, r.text[:200])
    # The cashier (pos, sales) has no purchases, inventory, reports or archive permission.
    for path in paths[1:]:
        assert _print(cashier_api, path).status_code == 403, path
    r = _print(cashier_api, paths[1], Accept="text/html")
    assert r.status_code == 403 and "تعذرت الطباعة" in r.text
    for path in (f"/print/sale/{uuid.uuid4()}", f"/print/inventory/{uuid.uuid4()}", "/print/dispatch/NOPE-0",
                 "/print/handover/NOPE-0"):
        assert _print(admin_api, path).status_code == 404, path
    assert _print(admin_api, "/print/sale/not-an-id").status_code == 422


def test_archive_filters_are_typed(admin_api, cashier_api):
    assert admin_api.get("/archive", params={"from_date": "2026-01-01", "to_date": "2026-12-31"}).status_code == 200
    assert admin_api.get("/archive", params={"doc_type": "bogus"}).status_code == 422
    assert admin_api.get("/archive", params={"from_date": "nope"}).status_code == 422
    assert cashier_api.get("/archive").status_code == 403


def test_a_users_branches_must_be_the_workspaces(admin_api, reg):
    me = admin_api.ok(admin_api.get("/auth/me"))
    assert admin_api.put(f"/users/{me['id']}/warehouses", json={"warehouse_ids": ["abc"]}).status_code == 422
    r = admin_api.put(f"/users/{me['id']}/warehouses", json={"warehouse_ids": [str(uuid.uuid4())]})
    assert r.status_code == 404
    assert admin_api.get(f"/users/{uuid.uuid4()}/warehouses").status_code == 404
