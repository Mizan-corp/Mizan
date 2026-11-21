"""purchases module: PO CRUD, receive (stock in, cost update, prices),
supplier prices + history + comparison, quick-add, purchase suggestions."""
from helpers import uid

from conftest import (admin_api, owner_api, product, supplier, wh,
                      reg)  # noqa: F401


def _po_payload(prod, wh_, supplier_, qty=5, cost="60"):
    return {
        "supplier_id": supplier_["id"],
        "warehouse_id": wh_["id"],
        "items": [{"product_id": prod["id"], "qty": qty, "unit_cost": cost}],
    }


def test_purchase_order_crud_and_receive(owner_api, admin_api, reg, product, supplier, wh):
    payload = _po_payload(product, wh, supplier)
    po = owner_api.ok(owner_api.post("/purchases", json=payload))
    reg.add("purchase_order", po["id"])
    assert po["status"].lower() in ("draft", "pending", "ordered")

    lst = owner_api.ok(owner_api.get("/purchases"))
    rows = lst if isinstance(lst, list) else lst.get("items", [])
    row = next(x for x in rows if x["id"] == po["id"])
    assert float(row["total"]) == 300  # 5 × 60, computed from the lines

    upd = owner_api.ok(owner_api.put(f"/purchases/{po['id']}",
                                     json={"supplier_id": supplier["id"],
                                           "warehouse_id": wh["id"],
                                           "items": [{"product_id": product["id"], "qty": 7,
                                                      "unit_cost": "60"}]}))
    assert isinstance(upd, dict)

    rec = owner_api.ok(owner_api.post(f"/purchases/{po['id']}/receive"))
    assert rec.get("detail") == "Received"

    bal = admin_api.ok(admin_api.post("/stock/balance/bulk",
                                      params={"warehouse_id": wh["id"]},
                                      json=[product["id"]]))
    assert float(bal.get(str(product["id"]), 0)) == 7

    mv = admin_api.ok(admin_api.get(f"/products/{product['id']}/movements"))
    items = mv.get("items", mv if isinstance(mv, list) else [])
    assert any(m["movement_type"] == "purchase" for m in items)


def test_purchase_reject_receive_twice(owner_api, admin_api, reg, product, supplier, wh):
    po = owner_api.ok(owner_api.post("/purchases", json=_po_payload(product, wh, supplier)))
    reg.add("purchase_order", po["id"])
    owner_api.ok(owner_api.post(f"/purchases/{po['id']}/receive"))
    r = admin_api.post(f"/purchases/{po['id']}/receive")
    assert r.status_code in (400, 409), r.text[:200]


def test_supplier_price_and_history(owner_api, admin_api, reg, product, supplier):
    sp = owner_api.ok(owner_api.post("/purchases/supplier-prices",
                                     json={"supplier_id": supplier["id"],
                                           "product_id": product["id"],
                                           "price": "55"}))
    reg.add("supplier_price", sp.get("id") or "")
    assert float(sp["price"]) == 55

    upd = owner_api.ok(owner_api.put(f"/purchases/supplier-prices/{sp['id']}",
                                     json={"price": "53"}))
    assert float(upd["price"]) == 53

    hist = admin_api.ok(owner_api.get(f"/purchases/price-history/{product['id']}"))
    assert isinstance(hist, list)

    comp = admin_api.ok(owner_api.get(f"/purchases/supplier-prices/product/{product['id']}"))
    assert comp["product_name"] and any(s["id"] == sp["id"] for s in comp["suppliers"])


def test_purchase_quick_add_and_suggestions(owner_api, reg, wh, supplier, product):
    # price suggestions for products with reorder point set
    sug = owner_api.ok(owner_api.get("/purchases/suggestions"))
    assert isinstance(sug, list)

    quick = owner_api.ok(owner_api.post("/purchases/quick-add-product", json={
        "name": f"E2E-QUICK-{uid('p')}", "unit": "عدد", "cost_price": 1, "retail_price": 3}))
    reg.add("product", quick["id"])
    assert float(quick["cost_price"]) == 1

def test_purchase_reads_and_unknown_references(owner_api, product):
    import uuid

    for path in (f"/purchases/{uuid.uuid4()}", f"/purchases/price-history/{uuid.uuid4()}",
                 f"/purchases/supplier-prices/product/{uuid.uuid4()}"):
        r = owner_api.get(path)
        assert r.status_code == 404, (path, r.text[:200])
    assert owner_api.get("/purchases", params={"page_size": 201}).status_code == 422
    assert owner_api.post("/purchases/quick-add-product", json={"name": "E2E-x", "retail_price": "-1"}).status_code == 422
    sug = owner_api.ok(owner_api.get("/purchases/suggestions"))
    assert len(sug) <= 500


def test_partial_receipts_and_the_draft_lifecycle(owner_api, cashier_api, reg, product, supplier, wh):
    """Phase C (PUR-4): an order received in two goods receipts (partial, then received), returns
    limited to what arrived; drafts cancelled, deleted and edited; a partial order closed."""
    po = owner_api.ok(owner_api.post("/purchases", json=_po_payload(product, wh, supplier, qty=10, cost="50")))
    reg.add("purchase_order", po["id"])
    line = owner_api.ok(owner_api.get(f"/purchases/{po['id']}"))["items"][0]
    first = owner_api.ok(owner_api.post(f"/purchases/{po['id']}/receive", json={
        "items": [{"item_id": line["id"], "qty_received": 4, "unit_cost": "52", "batch_number": "E2E-L1",
                   "expiry_date": "2030-01-31"}]}))
    assert first["status"] == "partial" and first["receipt_number"].startswith("GRN-")
    r = owner_api.post(f"/purchases/{po['id']}/receive", json={"items": [{"item_id": line["id"], "qty_received": 7}]})
    assert r.status_code == 400  # more than the 6 left
    assert owner_api.post(f"/purchases/{po['id']}/returns", json={
        "items": [{"product_id": product["id"], "qty": 5}]}).status_code == 400  # only 4 arrived
    assert owner_api.ok(owner_api.post(f"/purchases/{po['id']}/receive", json={}))["status"] == "received"
    detail = owner_api.ok(owner_api.get(f"/purchases/{po['id']}"))
    assert [x["seq"] for x in detail["receipts"]] == [1, 2] and detail["receipts"][0]["items"][0]["batch_number"] == "E2E-L1"
    assert owner_api.ok(owner_api.get("/purchases", params={"status": "received", "search": po["po_number"]}))["total"] == 1

    draft = owner_api.ok(owner_api.post("/purchases", json=_po_payload(product, wh, supplier)))
    reg.add("purchase_order", draft["id"])
    owner_api.ok(owner_api.put(f"/purchases/{draft['id']}", json={"clear_supplier": True, "notes": "e2e"}))
    assert owner_api.ok(owner_api.get(f"/purchases/{draft['id']}"))["supplier_id"] is None
    assert cashier_api.post(f"/purchases/{draft['id']}/cancel").status_code == 403
    assert owner_api.ok(owner_api.post(f"/purchases/{draft['id']}/cancel", json={"reason": "e2e"}))["status"] == "cancelled"
    assert owner_api.delete(f"/purchases/{draft['id']}").status_code == 400  # no longer a draft

    gone = owner_api.ok(owner_api.post("/purchases", json=_po_payload(product, wh, supplier)))
    reg.add("purchase_order", gone["id"])
    assert owner_api.delete(f"/purchases/{gone['id']}").status_code == 204
    assert owner_api.get(f"/purchases/{gone['id']}").status_code == 404

    part = owner_api.ok(owner_api.post("/purchases", json=_po_payload(product, wh, supplier, qty=3)))
    reg.add("purchase_order", part["id"])
    owner_api.ok(owner_api.post(f"/purchases/{part['id']}/receive", json={
        "items": [{"product_id": product["id"], "qty_received": 1}]}))
    assert owner_api.ok(owner_api.post(f"/purchases/{part['id']}/close"))["status"] == "received"
