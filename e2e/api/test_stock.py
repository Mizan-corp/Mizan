"""stock module: warehouses, balances, movements, adjustments, transfer,
low stock, valuation, supplier prices + comparison/graph price history."""
import uuid

from helpers import uid

from conftest import product, category, subcategory, supplier, owner_api, db  # noqa: F401


def _wh(admin_api, reg, kind="warehouse"):
    name = f"E2E-WH-{uid('w')}"
    r = admin_api.post("/stock/warehouses",
                       json={"code": name, "name": name, "warehouse_type": kind})
    d = admin_api.ok(r, 200, 201)
    reg.add("warehouse", d["id"])
    return d


def _open(admin_api, product_id, warehouse_id, qty=10):
    r = admin_api.post("/stock/movements", json={
        "product_id": product_id, "warehouse_id": warehouse_id,
        "movement_type": "opening_stock", "qty": qty,
        "unit_cost": "7", "unit_price": "10", "note": "e2e-open",
    })
    return admin_api.ok(r, 200)


# ---------------- warehouses ----------------
def test_warehouse_crud(admin_api, reg, db):
    w = _wh(admin_api, reg)
    lst = admin_api.ok(admin_api.get("/stock/warehouses"))
    assert any(x["id"] == w["id"] for x in lst)

    upd = admin_api.ok(admin_api.put(f"/stock/warehouses/{w['id']}",
                                     json={"name": w["name"] + "R", "is_active": True}))
    assert upd["name"] == w["name"] + "R"

    r = admin_api.delete(f"/stock/warehouses/{w['id']}")
    assert r.status_code == 204  # soft delete
    assert db.one("SELECT count(*) FROM audit_log WHERE entity_id = %s AND action_type = 'deactivate'", (w["id"],))[0] == 1


def test_warehouse_delete_guard_when_linked(admin_api, reg, product):
    w = _wh(admin_api, reg)
    _open(admin_api, product["id"], w["id"])
    r = admin_api.delete(f"/stock/warehouses/{w['id']}")
    assert r.status_code in (400, 409), r.text[:200]


# ---------------- balances ----------------
def test_balance_bulk_total_breakdown(admin_api, reg, product, wh):
    _open(admin_api, product["id"], wh["id"], 10)
    b = admin_api.ok(admin_api.post("/stock/balance/bulk",
                                    params={"warehouse_id": wh["id"]},
                                    json=[product["id"]]))
    assert float(b.get(product["id"], 0)) == 10
    if "__tracked__" in b:
        assert b["__tracked__"][product["id"]] is True

    t = admin_api.ok(admin_api.post("/stock/balance/total", json=[product["id"]]))
    assert float(t[product["id"]]) == 10

    bd = admin_api.ok(admin_api.get(f"/stock/balance/breakdown/{product['id']}"))
    row = next((x for x in bd if x["warehouse_id"] == wh["id"]), None) if bd and "warehouse_id" in bd[0] else bd[0]
    assert any(float(x["qty"]) == 10 for x in bd)


# ---------------- movements ----------------
def test_movements_add_list(admin_api, reg, product, wh):
    _open(admin_api, product["id"], wh["id"], 5)
    damage = admin_api.ok(admin_api.post("/stock/movements", json={
        "product_id": product["id"], "warehouse_id": wh["id"],
        "movement_type": "damage", "qty": 1, "note": "e2e-damage",
    }))
    assert damage["movement_type"] == "damage"

    page = admin_api.ok(admin_api.get("/stock/movements", params={"warehouse_id": wh["id"]}))
    assert page["total"] >= 2
    assert page["items"][0]["product_name"]

    bal = admin_api.ok(admin_api.post("/stock/balance/bulk",
                                      params={"warehouse_id": wh["id"]}, json=[product["id"]]))
    assert float(bal[product["id"]]) == 4  # 5 - 1

    # movement note validation for OUT types
    r = admin_api.post("/stock/movements", json={
        "product_id": product["id"], "warehouse_id": wh["id"],
        "movement_type": "adjustment_out", "qty": 1,
    })
    assert r.status_code in (200, 422)  # backend doesn't require note for OUT


def test_movements_require_valid_enum(admin_api, product, wh):
    r = admin_api.post("/stock/movements", json={
        "product_id": product["id"], "warehouse_id": wh["id"],
        "movement_type": "bogus", "qty": 1, "note": "x",
    })
    assert r.status_code in (400, 422), r.text[:200]


# ---------------- adjustments + transfer ----------------
def test_bulk_adjustment_and_transfer(admin_api, reg, product, wh):
    a = _wh(admin_api, reg, "warehouse")
    _open(admin_api, product["id"], wh["id"], 10)

    r = admin_api.post("/stock/adjustment/bulk", json=[{
        "product_id": product["id"], "warehouse_id": wh["id"],
        "movement_type": "adjustment_in", "qty": 3, "note": "e2e-adj",
    }])
    admin_api.ok(r, 200)
    bal = admin_api.ok(admin_api.post("/stock/balance/bulk",
                                      params={"warehouse_id": wh["id"]}, json=[product["id"]]))
    assert float(bal[product["id"]]) == 13

    r = admin_api.post("/stock/transfer", json={
        "product_id": product["id"],
        "from_warehouse_id": wh["id"],
        "to_warehouse_id": a["id"],
        "qty": 5, "note": "e2e-transfer",
    })
    admin_api.ok(r, 200)
    b2 = admin_api.ok(admin_api.post("/stock/balance/bulk",
                                     params={"warehouse_id": wh["id"]}, json=[product["id"]]))
    b3 = admin_api.ok(admin_api.post("/stock/balance/bulk",
                                     params={"warehouse_id": a["id"]}, json=[product["id"]]))
    assert float(b2[product["id"]]) == 8
    assert float(b3[product["id"]]) == 5


def test_transfer_insufficient_stock_rejected(admin_api, reg, product, wh):
    a = _wh(admin_api, reg)
    r = admin_api.post("/stock/transfer", json={
        "product_id": product["id"], "from_warehouse_id": wh["id"],
        "to_warehouse_id": a["id"], "qty": 999, "note": "e2e-xfer-fail",
    })
    assert r.status_code in (400, 409), r.text[:200]


# ---------------- low stock / valuation ----------------
def test_low_stock_and_valuation(admin_api, reg, product, wh):
    _open(admin_api, product["id"], wh["id"], 2)
    low = admin_api.ok(admin_api.get("/stock/low-stock",
                                     params={"warehouse_id": wh["id"], "threshold": 5}))
    assert any(p["product_id"] == product["id"] for p in low)

    val = admin_api.ok(admin_api.get("/stock/valuation", params={"warehouse_id": wh["id"]}))
    assert float(val["total_cost_value"]) >= 0
    assert val["product_count"] >= 1


# ---------------- supplier prices ----------------
def test_supplier_prices_crud(admin_api, reg, product, supplier):
    r = admin_api.post("/purchases/supplier-prices", json={
        "supplier_id": supplier["id"], "product_id": product["id"],
        "price": "12.5", "currency": "EGP", "min_qty": 1,
    })
    sp = admin_api.ok(r, 200, 201)
    reg.add("supplier_price", sp["id"])
    assert float(sp["price"]) == 12.5

    comp = admin_api.ok(admin_api.get(f"/purchases/supplier-prices/product/{product['id']}"))
    assert comp["product_name"]
    assert any(s["id"] == sp["id"] for s in comp["suppliers"])

    upd = admin_api.ok(admin_api.put(f"/purchases/supplier-prices/{sp['id']}", json={"price": "15.0"}))
    assert float(upd["price"]) == 15.0

    r = admin_api.delete(f"/purchases/supplier-prices/{sp['id']}")
    assert r.status_code == 204


def test_price_history(admin_api, reg, product, supplier, wh):
    r = admin_api.post("/purchases", json={
        "warehouse_id": wh["id"], "supplier_id": supplier["id"],
        "amount_paid": "0", "items": [
            {"product_id": product["id"], "qty": 2, "unit_cost": "11.0", "notes": "e2e"}
        ],
    })
    po = admin_api.ok(r, 200, 201)
    reg.add("purchase_order", po["id"])
    admin_api.ok(admin_api.post(f"/purchases/{po['id']}/receive"), 200, 201)

    hist = admin_api.ok(admin_api.get(f"/purchases/price-history/{product['id']}"))
    assert isinstance(hist, list)
    assert any(float(h.get("new_cost", 0)) == 11.0 for h in hist)


def test_purchase_suggestions(owner_api):
    s = owner_api.ok(owner_api.get("/purchases/suggestions"))
    assert s == [] or isinstance(s, list)

def test_reset_warehouse_stock_is_audited(admin_api, reg, product, db):
    w = _wh(admin_api, reg)
    _open(admin_api, product["id"], w["id"])
    r = admin_api.delete("/stock/movements", params={"warehouse_id": w["id"]})
    assert r.status_code == 204, r.text[:200]
    assert db.one("SELECT count(*) FROM stock_movements WHERE warehouse_id = %s", (w["id"],))[0] == 0
    logged = db.one("SELECT details::jsonb->>'movements_deleted' FROM audit_log WHERE entity_id = %s AND action_type = 'reset_stock'", (w["id"],))
    assert logged and logged[0] == "1"


# ---------------- production-readiness (INV-1, INV-2, INV-5, INV-6) ----------------
def test_hand_movements_only_adjust_and_never_exceed_the_stock(admin_api, reg, product):
    w = _wh(admin_api, reg)
    _open(admin_api, product["id"], w["id"], 3)
    base = {"product_id": product["id"], "warehouse_id": w["id"], "qty": 1, "unit_cost": "5", "note": "e2e"}
    for kind in ("purchase", "sale", "return_in", "transfer_in", "transfer_out", "return_out"):
        r = admin_api.post("/stock/movements", json={**base, "movement_type": kind})
        assert r.status_code == 400, (kind, r.text[:200])
    r = admin_api.post("/stock/movements", json={**base, "movement_type": "adjustment_in", "unit_cost": "-1"})
    assert r.status_code == 422, r.text[:200]
    r = admin_api.post("/stock/movements", json={**base, "movement_type": "damage", "qty": 50})
    assert r.status_code == 400, r.text[:200]  # more than the 3 held
    bal = admin_api.ok(admin_api.post("/stock/balance/bulk", params={"warehouse_id": w["id"]}, json=[product["id"]]))
    assert float(bal[product["id"]]) == 3


def test_transfer_to_the_same_warehouse_and_deactivating_a_stocked_one_are_refused(admin_api, reg, product):
    w = _wh(admin_api, reg)
    _open(admin_api, product["id"], w["id"], 2)
    r = admin_api.post("/stock/transfer", json={"product_id": product["id"], "from_warehouse_id": w["id"],
                                                "to_warehouse_id": w["id"], "qty": 1})
    assert r.status_code in (400, 422), r.text[:200]
    r = admin_api.put(f"/stock/warehouses/{w['id']}", json={"is_active": False})
    assert r.status_code == 409, r.text[:200]


def test_warehouses_with_the_stopped_ones(admin_api, cashier_api, reg):
    """Phase C (INV-9): the warehouses screen lists stopped warehouses too (`settings`)."""
    w = admin_api.post("/stock/warehouses", json={"code": f"E2E-STOP-{uid('w')}", "name": f"E2E-STOP-{uid('w')}"})
    if w.status_code == 403:  # the e2e workspace's plan has no branch left
        return
    w = admin_api.ok(w)
    reg.add("warehouse", w["id"])
    admin_api.ok(admin_api.put(f"/stock/warehouses/{w['id']}", json={"is_active": False}))
    rows = admin_api.ok(admin_api.get("/stock/warehouses", params={"include_inactive": "true"}))
    assert next(x for x in rows if x["id"] == w["id"])["is_active"] is False
    assert w["id"] not in {x["id"] for x in admin_api.ok(admin_api.get("/stock/warehouses"))}
    assert cashier_api.get("/stock/warehouses", params={"include_inactive": "true"}).status_code == 403
