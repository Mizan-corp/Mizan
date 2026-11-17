"""operations module: dispatch, stock-request, list, PDF; goods receipt is gone (410, use purchases)."""
import uuid

from helpers import uid

from conftest import (admin_api, owner_api, product, supplier, customer,
                      wh, reg, db)  # noqa: F401


def _qty(db, product_id, warehouse_id) -> float:
    row = db.one("SELECT qty FROM stock_balances WHERE product_id = %s AND warehouse_id = %s", (product_id, warehouse_id))
    return float(row[0]) if row else 0.0


def test_dispatch_receipt_request_flow(owner_api, reg, wh, product, db):
    # second warehouse so dispatch/stock-request have distinct endpoints
    twh = owner_api.ok(owner_api.post("/stock/warehouses", json={
        "code": f"E2E-WH-{uid('w')}", "name": f"E2E-WH-{uid('w')}", "warehouse_type": "warehouse"}))
    reg.add("warehouse", twh["id"])

    # seed stock so the transfer has something to move
    mv = owner_api.ok(owner_api.post("/stock/movements", json={
        "product_id": product["id"], "warehouse_id": wh["id"],
        "movement_type": "opening_stock", "qty": "10", "unit_cost": "70"}))
    assert mv.get("qty") or mv.get("id")
    source = _qty(db, product["id"], wh["id"])

    dispatch = owner_api.ok(owner_api.post("/operations/dispatch", json={
        "from_warehouse_id": wh["id"], "to_warehouse_id": twh["id"],
        "items": [{"product_id": product["id"], "qty": 2, "unit_cost": "70"}]}))
    assert dispatch["doc_type"] == "dispatch_order" and dispatch.get("doc_number")
    # Stock really moves between branches (it used to record the movements only).
    assert _qty(db, product["id"], wh["id"]) == source - 2
    assert _qty(db, product["id"], twh["id"]) == 2

    # Goods from a supplier come in through a purchase order (supplier, payable, ledger), not here.
    r = owner_api.post("/operations/goods-receipt", json={
        "warehouse_id": twh["id"], "supplier_name": "e2e",
        "items": [{"product_id": product["id"], "qty": 2, "unit_cost": "70"}]})
    assert r.status_code == 410, r.text[:200]
    assert _qty(db, product["id"], twh["id"]) == 2  # nothing came in

    sr = owner_api.ok(owner_api.post("/operations/stock-request", json={
        "from_warehouse_id": wh["id"], "to_warehouse_id": twh["id"],
        "items": [{"product_id": product["id"], "qty": 2}]}))
    assert sr["doc_type"] == "stock_request" and sr.get("doc_number")

    rows = owner_api.ok(owner_api.get("/operations", params={"page_size": 5}))
    assert rows["total"] >= 2 and len(rows["items"]) <= 5
    assert any(i["doc_number"] == dispatch["doc_number"] for i in owner_api.ok(
        owner_api.get("/operations", params={"doc_type": "dispatch_order", "page_size": 200}))["items"])


def test_dispatch_retry_and_cancel(owner_api, reg, wh, product, db):
    twh = owner_api.ok(owner_api.post("/stock/warehouses", json={
        "code": f"E2E-WH-{uid('w')}", "name": f"E2E-WH-{uid('w')}", "warehouse_type": "warehouse"}))
    reg.add("warehouse", twh["id"])
    owner_api.ok(owner_api.post("/stock/movements", json={
        "product_id": product["id"], "warehouse_id": wh["id"],
        "movement_type": "opening_stock", "qty": "10", "unit_cost": "70"}))
    source = _qty(db, product["id"], wh["id"])
    body = {"from_warehouse_id": wh["id"], "to_warehouse_id": twh["id"], "client_id": str(uuid.uuid4()),
            "items": [{"product_id": product["id"], "qty": 3}]}
    first = owner_api.ok(owner_api.post("/operations/dispatch", json=body))
    again = owner_api.ok(owner_api.post("/operations/dispatch", json=body))
    assert again["doc_number"] == first["doc_number"]  # a retry is the same document (OPS-5)
    assert _qty(db, product["id"], wh["id"]) == source - 3

    cancelled = owner_api.ok(owner_api.post(f"/operations/{first['id']}/cancel", json={"reason": "e2e"}))
    assert cancelled["status"] == "cancelled"
    assert _qty(db, product["id"], wh["id"]) == source and _qty(db, product["id"], twh["id"]) == 0
    assert owner_api.post(f"/operations/{first['id']}/cancel").status_code == 400

def test_operations_refuse_bad_input_and_number_uniquely(owner_api, reg, wh, product):
    twh = owner_api.ok(owner_api.post("/stock/warehouses", json={
        "code": f"E2E-WH-{uid('w')}", "name": f"E2E-WH-{uid('w')}", "warehouse_type": "warehouse"}))
    reg.add("warehouse", twh["id"])

    # A negative quantity would pass the stock check and create stock in the source warehouse.
    r = owner_api.post("/operations/dispatch", json={
        "from_warehouse_id": wh["id"], "to_warehouse_id": twh["id"],
        "items": [{"product_id": product["id"], "qty": -5}]})
    assert r.status_code == 422, r.text[:200]

    r = owner_api.post("/operations/dispatch", json={
        "from_warehouse_id": "00000000-0000-0000-0000-000000000000", "to_warehouse_id": twh["id"],
        "items": [{"product_id": product["id"], "qty": 1}]})
    assert r.status_code == 404, r.text[:200]

    numbers = {owner_api.ok(owner_api.post("/operations/stock-request", json={
        "from_warehouse_id": wh["id"], "to_warehouse_id": twh["id"],
        "items": [{"product_id": product["id"], "qty": 1}]}))["doc_number"] for _ in range(3)}
    assert len(numbers) == 3, numbers
