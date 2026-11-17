"""Pharmacy stock in batches (ADR-006 phase 4c): the inventory pharmacy variant keeps stock in
batches with expiry dates, sells first-expiry-first-out, never sells expired or quarantined
batches, and every batch's quantity matches stock."""
from datetime import date, timedelta

import pytest
from helpers import uid

from conftest import admin_api, owner_api, reg, db, wh, ensure_shift  # noqa: F401


@pytest.fixture
def pharmacy(owner_api, db):
    """The e2e workspace runs as a pharmacy (with the batches module) during the test."""
    tid = owner_api.ok(owner_api.get("/auth/me"))["tenant_id"]
    before = db.one("SELECT sector, active_modules FROM tenants WHERE id = %s", (tid,))
    db.q("UPDATE tenants SET sector = 'pharmacy', active_modules = active_modules || '[\"batches\"]'::jsonb WHERE id = %s", (tid,))
    try:
        yield tid
    finally:
        db.q("UPDATE tenants SET sector = %s, active_modules = %s::jsonb WHERE id = %s", (before[0], __import__("json").dumps(before[1]), tid))


def _lots(api, product_id, warehouse_id):
    rows = api.ok(api.get("/modules/batches", params={"product_id": product_id, "warehouse_id": warehouse_id}))
    return {r["batch_number"]: float(r["qty"]) for r in rows}


def test_pharmacy_stock_is_kept_in_batches(owner_api, reg, wh, pharmacy, db):
    profile = owner_api.ok(owner_api.get("/settings/workspace-profile"))
    assert profile["variants"].get("inventory") == "pharmacy"
    assert "scientific_name" in [f["key"] for f in profile["fields"]["product"]]

    sub = owner_api.ok(owner_api.get("/products", params={"limit": 1}))
    sub_id = (sub.get("items", sub) if isinstance(sub, dict) else sub)[0]["subcategory_id"]
    drug = owner_api.ok(owner_api.post("/products", json={
        "subcategory_id": sub_id, "name": "E2E دواء " + uid("d"), "retail_price": "20",
        "extra": {"scientific_name": "E2Etestamol", "strength": "5 mg"}}))
    reg.add("product", drug["id"])
    assert drug["extra"]["scientific_name"] == "E2Etestamol"
    found = owner_api.ok(owner_api.get("/products", params={"search": "E2Etestamol"}))
    assert any(p["id"] == drug["id"] for p in (found.get("items", found) if isinstance(found, dict) else found))

    def stock_in(batch, expiry, qty):
        body = {"product_id": drug["id"], "warehouse_id": wh["id"], "movement_type": "opening_stock", "qty": str(qty), "unit_cost": "8"}
        if batch:
            body.update(batch_number=batch, expiry_date=expiry.isoformat())
        return owner_api.post("/stock/movements", json=body)

    today = date.today()
    assert stock_in(None, None, 1).status_code == 422  # receiving needs a batch and expiry
    for batch, expiry, qty in (("SOON", today + timedelta(days=10), 3), ("OLD", today - timedelta(days=3), 5),
                               ("LATER", today + timedelta(days=400), 4)):
        owner_api.ok(stock_in(batch, expiry, qty))
    assert _lots(owner_api, drug["id"], wh["id"]) == {"SOON": 3, "OLD": 5, "LATER": 4}

    ensure_shift(owner_api, reg, wh["id"])  # the sales' cash goes into the seller's open shift
    sale = owner_api.ok(owner_api.post("/sales", json={
        "warehouse_id": wh["id"], "items": [{"product_id": drug["id"], "qty": 4, "unit_price": 20}]}))
    reg.add("sale", sale["id"])
    line = sale["items"][0]["extra"]
    assert line["batch_number"] == "SOON" and [b["batch_number"] for b in line["batches"]] == ["SOON", "LATER"]
    assert _lots(owner_api, drug["id"], wh["id"]) == {"OLD": 5, "LATER": 3}  # expired stock untouched

    r = owner_api.post("/sales", json={"warehouse_id": wh["id"], "items": [{"product_id": drug["id"], "qty": 4, "unit_price": 20}]})
    assert r.status_code == 409, r.text[:200]  # only 3 sellable: the rest has expired

    expiring = owner_api.ok(owner_api.get("/modules/batches/expiring", params={"days": 30}))
    assert {"OLD"} <= {x["batch_number"] for x in expiring if x["product_id"] == drug["id"]}

    later = next(x for x in owner_api.ok(owner_api.get("/modules/batches", params={"product_id": drug["id"]}))
                 if x["batch_number"] == "LATER")
    owner_api.ok(owner_api.post(f"/modules/batches/{later['id']}/status", json={"status": "quarantined"}))
    r = owner_api.post("/sales", json={"warehouse_id": wh["id"], "items": [{"product_id": drug["id"], "qty": 1, "unit_price": 20}]})
    assert r.status_code == 409, r.text[:200]  # a quarantined batch isn't sold
    owner_api.ok(owner_api.post(f"/modules/batches/{later['id']}/status", json={"status": "active"}))

    owner_api.ok(owner_api.put(f"/sales/{sale['id']}/cancel"))
    assert _lots(owner_api, drug["id"], wh["id"]) == {"SOON": 3, "OLD": 5, "LATER": 4}  # back into the same batches

    two = owner_api.ok(owner_api.post("/sales", json={
        "warehouse_id": wh["id"], "items": [{"product_id": drug["id"], "qty": 2, "unit_price": 20}]}))
    reg.add("sale", two["id"])
    assert _lots(owner_api, drug["id"], wh["id"])["SOON"] == 1
    ret = owner_api.ok(owner_api.post(f"/sales/{two['id']}/partial-return", json={"items": [{"product_id": drug["id"], "qty": 1}]}))
    reg.add("sale", ret.get("id") or ret.get("return_id") or "")
    assert _lots(owner_api, drug["id"], wh["id"])["SOON"] == 2  # a return goes back into its batch

    twh = owner_api.ok(owner_api.post("/stock/warehouses", json={
        "code": f"E2E-WH-{uid('w')}", "name": f"E2E-WH-{uid('w')}", "warehouse_type": "warehouse"}))
    reg.add("warehouse", twh["id"])
    owner_api.ok(owner_api.post("/operations/dispatch", json={
        "from_warehouse_id": wh["id"], "to_warehouse_id": twh["id"], "items": [{"product_id": drug["id"], "qty": 2}]}))
    assert _lots(owner_api, drug["id"], twh["id"]) == {"SOON": 2}  # the same batch arrives (FEFO)

    balances = dict(db.q("SELECT warehouse_id::text, qty FROM stock_balances WHERE product_id = %s", (drug["id"],)))
    for w in (wh["id"], twh["id"]):
        assert float(balances[w]) == sum(_lots(owner_api, drug["id"], w).values())  # batches == stock
