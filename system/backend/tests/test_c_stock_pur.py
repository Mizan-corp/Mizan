"""Stock, purchases and operations, phase C of PRODUCTION_READINESS.md (screens and completeness).

- INV-9: a product without a category, its picture (listed, removed), stopped products listed for
  `inventory`, stopped warehouses listed for `settings`;
- INV-10: `enable_reorder_alerts` is read (the alert after a sale and the system scan), the scan flags
  real low stock only, and `valuation_method` (FIFO was never built) is gone;
- PUR-4: partial receipts (status partial then received, one goods receipt and one ledger entry each,
  quantities never above what is left, cost, batch and expiry per line), returns from what arrived,
  cancel / delete / edit of drafts and closing a partly received order, the order's detail;
- OPS-4: stock requests approved (`operations:approve`), fulfilled as a dispatch, or cancelled;
- the pharmacy's batch receipt without a supplier or ledger entry is gone (410).
Each test fails on the code before phase C.
"""
import json
import os
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.activities.general.modules.contacts.models.party import Supplier
from app.activities.general.modules.inventory.models.product import Category, Product, Subcategory
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement, check_low_stock_and_notify
from app.db.base import AsyncSessionLocal
from app.framework.loader import registry
from app.models.registry import load_all_models
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password
from app.platform.permissions.access import assign_roles
from app.platform.permissions.roles import standard_permissions
from app.platform.tenancy.context import bind_tenant, current_tenant_id, install_tenancy_events
from app.platform.tenancy.models import Tenant
from main import app

load_all_models()
install_tenancy_events()

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

D = Decimal
MODULES = ["sales", "pos", "shifts", "inventory", "operations", "finance", "contacts", "purchases"]


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _env(accounting: bool = False, extra_modules: tuple = ()) -> dict:
    """A workspace with warehouses A and B, a manager, a storekeeper of A only, an accountant and a
    cashier, a supplier, a safe holding 1000, a category with a subcategory, and a tracked product
    with 10 units at cost 60 in A and 20 in B."""
    t = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=t, name=f"PhaseC {t.hex[:6]}", slug=f"phc-{t.hex[:8]}", status="active",
                     active_modules=MODULES + (["accounting"] if accounting else []) + list(extra_modules)))
        await s.flush()
        a = Warehouse(id=uuid.uuid4(), tenant_id=t, code=f"A-{t.hex[:4]}", name="المخزن أ", is_active=True)
        b = Warehouse(id=uuid.uuid4(), tenant_id=t, code=f"B-{t.hex[:4]}", name="المخزن ب", is_active=True)
        users = {}
        for role, manager in (("manager", True), ("storekeeper", False), ("accountant", False), ("cashier", False)):
            users[role] = User(id=uuid.uuid4(), tenant_id=t, username=f"{role[:5]}_{t.hex[:8]}", full_name=role,
                               role=role, password_hash=hash_password("Pass123!"), is_manager=manager,
                               permissions=standard_permissions(role), is_active=True)
        cat = Category(id=uuid.uuid4(), tenant_id=t, name="مشروبات")
        sub = Subcategory(id=uuid.uuid4(), tenant_id=t, category_id=cat.id, name="عصائر")
        product = Product(id=uuid.uuid4(), tenant_id=t, name="صنف مخزن", code=f"P-{t.hex[:6]}", subcategory_id=sub.id,
                          retail_price=D("100"), cost_price=D("60"), stock_status="tracked", is_active=True)
        other = Product(id=uuid.uuid4(), tenant_id=t, name="صنف آخر", code=f"Q-{t.hex[:6]}",
                        retail_price=D("40"), cost_price=D("20"), stock_status="tracked", is_active=True)
        supplier = Supplier(id=uuid.uuid4(), tenant_id=t, name="مورد", balance=D("0"))
        s.add_all([a, b, *users.values(), cat])
        await s.flush()
        s.add_all([sub])
        await s.flush()
        s.add_all([product, other, supplier])
        await s.flush()
        await s.execute(text("INSERT INTO user_warehouses (user_id, warehouse_id) VALUES (:u, :w)"),
                        {"u": users["storekeeper"].id, "w": a.id})
        await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        for role, u in users.items():
            rid = uuid.uuid4()
            await s.execute(text(
                "INSERT INTO sys_roles (id, tenant_id, code, name, name_en, is_system, is_clinical, grants) "
                "VALUES (:id, :t, :c, :c, :c, false, false, CAST(:g AS jsonb))"),
                {"id": rid, "t": t, "c": f"{role}-{rid.hex[:8]}", "g": json.dumps(standard_permissions(role))})
            await assign_roles(s, u, [rid])
        await s.commit()
    current_tenant_id.set(t)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        safe_id = uuid.uuid4()
        await s.execute(text("INSERT INTO safes (id, tenant_id, name, balance) VALUES (:id, :t, 'الخزينة', 1000)"),
                        {"id": safe_id, "t": t})
        for wh, qty in ((a.id, D("10")), (b.id, D("20"))):
            await apply_movement(s, product_id=product.id, warehouse_id=wh, movement_type=MovementType.opening_stock,
                                 qty=qty, unit_cost=D("60"), created_by=users["manager"].id)
        await s.commit()

    def headers(u):
        return {"Authorization": "Bearer " + create_access_token(
            {"sub": str(u.id), "role": u.role, "username": u.username, "tid": str(t)})}

    return {"tenant_id": t, "a": a.id, "b": b.id, "product": product.id, "other": other.id, "sub": sub.id,
            "supplier": supplier.id, "safe": safe_id, "users": {k: u.id for k, u in users.items()},
            "h": {k: headers(u) for k, u in users.items()}}


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _scalar(env, sql: str, **params):
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        return (await s.execute(text(sql), params)).scalar()


async def _rows(env, sql: str, **params):
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        return (await s.execute(text(sql), params)).mappings().all()


async def _exec(env, sql: str, **params):
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        await s.execute(text(sql), {"t": env["tenant_id"], **params})
        await s.commit()


async def _balance(env, wh, product=None):
    return D(str(await _scalar(env, "SELECT COALESCE(qty, 0) FROM stock_balances WHERE product_id = :p AND warehouse_id = :w",
                               p=product or env["product"], w=wh) or 0))


async def _order(c, env, lines, who="manager", warehouse="a", **extra):
    r = await c.post("/purchases", json={"warehouse_id": str(env[warehouse]), "supplier_id": str(env["supplier"]),
                                         "items": lines, **extra}, headers=env["h"][who])
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ── INV-9 ────────────────────────────────────────────────────────────────────────────────────

async def test_a_product_can_be_added_without_a_category_and_taken_out_of_one():
    env = await _env()
    async with _client() as c:
        r = await c.post("/products", json={"name": "صنف بلا تصنيف", "retail_price": "15"}, headers=env["h"]["manager"])
        assert r.status_code == 200, r.text
        assert r.json()["subcategory_id"] is None
        r = await c.put(f"/products/{env['product']}", json={"clear_subcategory": True}, headers=env["h"]["manager"])
        assert r.status_code == 200 and r.json()["subcategory_id"] is None


async def test_a_products_picture_is_listed_and_can_be_removed():
    env = await _env()
    await _exec(env, "UPDATE products SET image_url = '/uploads/x/product_image/p.png' WHERE id = :p", p=env["product"])
    async with _client() as c:
        r = await c.get(f"/products/{env['product']}", headers=env["h"]["manager"])
        assert r.json()["image_url"] == "/uploads/x/product_image/p.png"
        listed = (await c.get("/products", params={"search": "صنف مخزن"}, headers=env["h"]["cashier"])).json()["items"]
        assert listed[0]["image_url"] == "/uploads/x/product_image/p.png"
        assert (await c.delete(f"/products/{env['product']}/image", headers=env["h"]["cashier"])).status_code == 403
        assert (await c.delete(f"/products/{env['product']}/image", headers=env["h"]["manager"])).status_code == 204
        assert (await c.get(f"/products/{env['product']}", headers=env["h"]["manager"])).json()["image_url"] is None


async def test_stopped_products_are_listed_for_inventory_and_can_come_back():
    env = await _env()
    async with _client() as c:
        assert (await c.delete(f"/products/{env['other']}", headers=env["h"]["manager"])).status_code == 204
        active = (await c.get("/products", headers=env["h"]["manager"])).json()["items"]
        assert str(env["other"]) not in {p["id"] for p in active}
        stopped = (await c.get("/products", params={"status": "inactive"}, headers=env["h"]["manager"])).json()
        assert [p["id"] for p in stopped["items"]] == [str(env["other"])] and stopped["total"] == 1
        assert (await c.get("/products", params={"status": "all"}, headers=env["h"]["cashier"])).status_code == 403
        r = await c.put(f"/products/{env['other']}", json={"is_active": True}, headers=env["h"]["manager"])
        assert r.status_code == 200 and r.json()["is_active"] is True
    assert await _scalar(env, "SELECT COUNT(*) FROM audit_log WHERE entity_type = 'product' AND action = 'deactivate' "
                              "AND entity_id = :p", p=env["other"]) == 1


async def test_stopped_warehouses_are_listed_for_whoever_manages_them():
    env = await _env()
    await _exec(env, "UPDATE warehouses SET is_active = false WHERE id = :w", w=env["b"])
    async with _client() as c:
        r = await c.get("/stock/warehouses", params={"include_inactive": "true"}, headers=env["h"]["manager"])
        assert r.status_code == 200
        rows = {w["id"]: w for w in r.json()}
        assert rows[str(env["b"])]["is_active"] is False and rows[str(env["a"])]["is_active"] is True
        plain = (await c.get("/stock/warehouses", headers=env["h"]["manager"])).json()
        assert str(env["b"]) not in {w["id"] for w in plain}
        r = await c.get("/stock/warehouses", params={"include_inactive": "true"}, headers=env["h"]["storekeeper"])
        assert r.status_code == 403
        # The trial plan has one branch: bringing B back counts like adding one.
        r = await c.put(f"/stock/warehouses/{env['b']}", json={"is_active": True}, headers=env["h"]["manager"])
        assert r.status_code == 403
        await _exec(env, "UPDATE tenants SET plan = 'pro' WHERE id = :t")
        r = await c.put(f"/stock/warehouses/{env['b']}", json={"is_active": True}, headers=env["h"]["manager"])
        assert r.status_code == 200 and r.json()["is_active"] is True
        r = await c.post("/stock/warehouses", json={"code": f"C-{env['tenant_id'].hex[:4]}", "name": "فرع ج"},
                         headers=env["h"]["manager"])
        assert r.status_code == 200 and r.json()["is_active"] is True
    assert await _scalar(env, "SELECT COUNT(*) FROM audit_log WHERE entity_type = 'warehouse' AND action = 'create'") == 1


# ── INV-10 ───────────────────────────────────────────────────────────────────────────────────

async def test_reorder_alerts_follow_the_setting():
    env = await _env()
    await _exec(env, "UPDATE products SET reorder_level = 50 WHERE id = :p", p=env["product"])

    async def alerts():
        return await _scalar(env, "SELECT COUNT(*) FROM notifications WHERE type = 'low_stock'")

    await _exec(env, "INSERT INTO store_settings (id, tenant_id, key, value) VALUES (:i, :t, 'mod_settings_inventory', :v)",
                i=uuid.uuid4(), v=json.dumps({"enable_reorder_alerts": False}))
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        await check_low_stock_and_notify(s, env["tenant_id"], [env["product"]], env["a"])
    assert await alerts() == 0
    async with _client() as c:
        assert (await c.post("/notifications/generate-system-alerts", headers=env["h"]["manager"])).status_code == 200
    assert await alerts() == 0

    await _exec(env, "UPDATE store_settings SET value = :v WHERE key = 'mod_settings_inventory'",
                v=json.dumps({"enable_reorder_alerts": True}))
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        await check_low_stock_and_notify(s, env["tenant_id"], [env["product"]], env["a"])
    assert await alerts() == 1


async def test_the_system_scan_flags_only_products_really_at_their_reorder_level():
    env = await _env()
    # 30 in stock, reorder point 5 and level 5: not low; the old scan flagged any product with a point.
    await _exec(env, "UPDATE products SET reorder_point = 5, reorder_level = 5 WHERE id = :p", p=env["product"])
    await _exec(env, "UPDATE products SET reorder_point = 5, reorder_level = 0 WHERE id = :p", p=env["other"])
    async with _client() as c:
        await c.post("/notifications/generate-system-alerts", headers=env["h"]["manager"])
    assert await _scalar(env, "SELECT COUNT(*) FROM notifications WHERE type = 'low_stock'") == 0
    await _exec(env, "UPDATE products SET reorder_level = 40 WHERE id = :p", p=env["product"])
    async with _client() as c:
        await c.post("/notifications/generate-system-alerts", headers=env["h"]["manager"])
    body = await _scalar(env, "SELECT body FROM notifications WHERE type = 'low_stock'")
    assert body and "صنف مخزن" in body


def test_the_valuation_method_setting_that_offered_fifo_is_gone():
    keys = {f.key for f in registry.get_manifest("inventory").settings_schema}
    assert "valuation_method" not in keys
    assert keys == {"prevent_negative_stock", "enable_reorder_alerts"}


# ── PUR-4 ────────────────────────────────────────────────────────────────────────────────────

async def test_an_order_is_received_in_two_receipts_each_posted_once():
    env = await _env(accounting=True)
    async with _client() as c:
        po = await _order(c, env, [{"product_id": str(env["product"]), "qty": 10, "unit_cost": 50},
                                   {"product_id": str(env["other"]), "qty": 4, "unit_cost": 20}])
        detail = (await c.get(f"/purchases/{po}", headers=env["h"]["manager"])).json()
        line = {i["product_id"]: i["id"] for i in detail["items"]}
        r = await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"], json={"items": [
            {"item_id": line[str(env["product"])], "qty_received": 4},
            {"item_id": line[str(env["other"])], "qty_received": 0}]})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "partial" and r.json()["receipt_number"].startswith("GRN-")
        assert await _balance(env, env["a"]) == D("14")
        assert D(str(await _scalar(env, "SELECT balance FROM suppliers WHERE id = :s", s=env["supplier"]))) == D("200")
        po_row = (await c.get(f"/purchases/{po}", headers=env["h"]["manager"])).json()
        assert po_row["status"] == "partial" and D(str(po_row["total"])) == D("200")
        left = {i["product_id"]: D(str(i["qty_remaining"])) for i in po_row["items"]}
        assert left == {str(env["product"]): D("6"), str(env["other"]): D("4")}

        # The rest arrives: nothing listed means what is left of every line.
        r = await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"], json={})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "received"
        assert await _balance(env, env["a"]) == D("20")
        assert await _balance(env, env["a"], env["other"]) == D("4")
        assert D(str(await _scalar(env, "SELECT balance FROM suppliers WHERE id = :s", s=env["supplier"]))) == D("580")
        done = (await c.get(f"/purchases/{po}", headers=env["h"]["manager"])).json()
        assert done["status"] == "received" and D(str(done["total"])) == D("580")
        assert [r["seq"] for r in done["receipts"]] == [1, 2]
        assert [D(str(r["total"])) for r in done["receipts"]] == [D("200"), D("380")]
        assert len(done["payments"]) == 2  # the two receipts' invoices on the supplier's account
        r = await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"], json={})
        assert r.status_code == 400

    entries = await _rows(env, """
        SELECT e.event, SUM(l.debit) AS d FROM acc_entries e JOIN acc_lines l ON l.entry_id = e.id
        WHERE e.source_type = 'purchase' AND e.source_id = :po GROUP BY e.event ORDER BY e.event""", po=uuid.UUID(po))
    assert [(r["event"], D(str(r["d"]))) for r in entries] == [("receive", D("200.00")), ("receive-2", D("380.00"))]
    payables = await _scalar(env, """
        SELECT SUM(l.credit - l.debit) FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id
        WHERE a.role = 'payables' AND l.party_id = :s""", s=env["supplier"])
    assert D(str(payables)) == D("580.00")


async def test_a_receipt_never_takes_more_than_is_left_and_keeps_cost_batch_and_expiry():
    env = await _env()
    async with _client() as c:
        po = await _order(c, env, [{"product_id": str(env["product"]), "qty": 5, "unit_cost": 50}])
        r = await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"],
                         json={"items": [{"product_id": str(env["product"]), "qty_received": 6}]})
        assert r.status_code == 400 and "المتبقي" in r.json()["detail"]
        r = await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"], json={"items": [
            {"product_id": str(env["product"]), "qty_received": 3, "unit_cost": 55, "batch_number": "L-7",
             "expiry_date": "2027-03-01"}]})
        assert r.status_code == 200, r.text
        receipt = (await c.get(f"/purchases/{po}", headers=env["h"]["manager"])).json()["receipts"][0]
        item = receipt["items"][0]
        assert (D(str(item["qty"])), D(str(item["unit_cost"])), item["batch_number"], item["expiry_date"]) == \
            (D("3"), D("55.00"), "L-7", "2027-03-01")
        r = await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"],
                         json={"items": [{"product_id": str(env["product"]), "qty_received": 0}]})
        assert r.status_code == 400  # nothing to receive
    cost = await _scalar(env, "SELECT unit_cost FROM stock_movements WHERE purchase_id = :po", po=uuid.UUID(po))
    assert D(str(cost)) == D("55.00")


async def test_a_partly_received_order_returns_at_most_what_arrived():
    env = await _env(accounting=True)
    async with _client() as c:
        po = await _order(c, env, [{"product_id": str(env["product"]), "qty": 10, "unit_cost": 50}])
        await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"],
                     json={"items": [{"product_id": str(env["product"]), "qty_received": 4, "unit_cost": 50}]})
        await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"],
                     json={"items": [{"product_id": str(env["product"]), "qty_received": 2, "unit_cost": 80}]})
        info = (await c.get(f"/purchases/{po}/returns", headers=env["h"]["manager"])).json()
        row = info["returnable"][0]
        # 4 at 50 and 2 at 80: 360 for 6, the order's own average cost.
        assert (D(str(row["received"])), D(str(row["returnable"])), D(str(row["unit_cost"]))) == (D("6"), D("6"), D("60.00"))
        r = await c.post(f"/purchases/{po}/returns", headers=env["h"]["manager"],
                         json={"items": [{"product_id": str(env["product"]), "qty": 7}]})
        assert r.status_code == 400
        r = await c.post(f"/purchases/{po}/returns", headers=env["h"]["manager"],
                         json={"items": [{"product_id": str(env["product"]), "qty": 6}]})
        assert r.status_code == 201, r.text
        assert D(str(r.json()["total"])) == D("360.00")
    assert D(str(await _scalar(env, "SELECT balance FROM suppliers WHERE id = :s", s=env["supplier"]))) == D("0")
    inventory = await _scalar(env, """
        SELECT SUM(l.debit - l.credit) FROM acc_lines l JOIN acc_entries e ON e.id = l.entry_id
        JOIN acc_accounts a ON a.id = l.account_id
        WHERE a.role = 'inventory' AND (e.source_id = :po OR e.source_type = 'purchase_return')""", po=uuid.UUID(po))
    assert D(str(inventory)) == D("0.00")


async def test_drafts_are_cancelled_deleted_and_edited_and_received_orders_are_not():
    env = await _env()
    async with _client() as c:
        draft = await _order(c, env, [{"product_id": str(env["product"]), "qty": 2, "unit_cost": 50}])
        r = await c.put(f"/purchases/{draft}", headers=env["h"]["manager"], json={
            "warehouse_id": str(env["b"]), "clear_supplier": True,
            "items": [{"product_id": str(env["other"]), "qty": 3, "unit_cost": 21}]})
        assert r.status_code == 200, r.text
        edited = (await c.get(f"/purchases/{draft}", headers=env["h"]["manager"])).json()
        assert edited["warehouse_id"] == str(env["b"]) and edited["supplier_id"] is None
        assert [(i["product_id"], D(str(i["qty_ordered"]))) for i in edited["items"]] == [(str(env["other"]), D("3"))]
        r = await c.put(f"/purchases/{draft}", headers=env["h"]["manager"], json={"items": [
            {"product_id": str(env["other"]), "qty": 1, "unit_cost": 1}, {"product_id": str(env["other"]), "qty": 1, "unit_cost": 1}]})
        assert r.status_code == 400  # one line per product
        # A storekeeper of A can't change an order of B.
        assert (await c.put(f"/purchases/{draft}", headers=env["h"]["storekeeper"], json={"notes": "x"})).status_code == 403

        r = await c.post(f"/purchases/{draft}/cancel", headers=env["h"]["manager"], json={"reason": "خطأ"})
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
        assert (await c.post(f"/purchases/{draft}/receive", headers=env["h"]["manager"], json={})).status_code == 400
        assert (await c.delete(f"/purchases/{draft}", headers=env["h"]["manager"])).status_code == 400

        other = await _order(c, env, [{"product_id": str(env["product"]), "qty": 2, "unit_cost": 50}])
        assert (await c.delete(f"/purchases/{other}", headers=env["h"]["cashier"])).status_code == 403
        assert (await c.delete(f"/purchases/{other}", headers=env["h"]["manager"])).status_code == 204
        assert (await c.get(f"/purchases/{other}", headers=env["h"]["manager"])).status_code == 404

        got = await _order(c, env, [{"product_id": str(env["product"]), "qty": 2, "unit_cost": 50}])
        await c.post(f"/purchases/{got}/receive", headers=env["h"]["manager"], json={})
        assert (await c.post(f"/purchases/{got}/cancel", headers=env["h"]["manager"])).status_code == 400
        assert (await c.put(f"/purchases/{got}", headers=env["h"]["manager"], json={"notes": "x"})).status_code == 400
        assert (await c.delete(f"/purchases/{got}", headers=env["h"]["manager"])).status_code == 400
        assert (await c.get("/purchases", params={"status": "cancelled"}, headers=env["h"]["manager"])).json()["total"] == 1
    actions = {r["action"] for r in await _rows(env, "SELECT action FROM audit_log WHERE entity_type = 'purchase'")}
    assert {"create", "update", "cancel", "delete", "receive"} <= actions


async def test_a_partly_received_order_is_closed_with_what_arrived():
    env = await _env()
    async with _client() as c:
        po = await _order(c, env, [{"product_id": str(env["product"]), "qty": 10, "unit_cost": 50}])
        assert (await c.post(f"/purchases/{po}/close", headers=env["h"]["manager"])).status_code == 400  # a draft
        await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"],
                     json={"items": [{"product_id": str(env["product"]), "qty_received": 3}]})
        r = await c.post(f"/purchases/{po}/close", headers=env["h"]["manager"], json={"reason": "المورد لن يورّد الباقي"})
        assert r.status_code == 200 and r.json()["status"] == "received"
        assert (await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"], json={})).status_code == 400
        assert D(str((await c.get(f"/purchases/{po}", headers=env["h"]["manager"])).json()["total"])) == D("150")
    assert D(str(await _scalar(env, "SELECT balance FROM suppliers WHERE id = :s", s=env["supplier"]))) == D("150")


async def test_a_planned_payment_is_made_with_the_first_receipt_only():
    env = await _env()
    async with _client() as c:
        po = await _order(c, env, [{"product_id": str(env["product"]), "qty": 10, "unit_cost": 50}],
                          amount_paid=100, safe_id=str(env["safe"]))
        r = await c.post(f"/purchases/{po}/receive", headers=env["h"]["manager"],
                         json={"items": [{"product_id": str(env["product"]), "qty_received": 4}]})
        assert r.status_code == 200, r.text
        # The second receipt pays nothing unless it says so, and needs no `finance`.
        r = await c.post(f"/purchases/{po}/receive", headers=env["h"]["storekeeper"], json={})
        assert r.status_code == 200, r.text
        detail = (await c.get(f"/purchases/{po}", headers=env["h"]["manager"])).json()
    assert [D(str(r["amount_paid"])) for r in detail["receipts"]] == [D("100"), D("0")]
    assert D(str(await _scalar(env, "SELECT balance FROM safes WHERE id = :s", s=env["safe"]))) == D("900")
    assert D(str(await _scalar(env, "SELECT balance FROM suppliers WHERE id = :s", s=env["supplier"]))) == D("400")


# ── OPS-4 ────────────────────────────────────────────────────────────────────────────────────

async def _request(c, env, qty=5, who="storekeeper"):
    r = await c.post("/operations/stock-request", headers=env["h"][who], json={
        "from_warehouse_id": str(env["b"]), "to_warehouse_id": str(env["a"]),
        "items": [{"product_id": str(env["product"]), "qty": qty}]})
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def test_a_stock_request_is_approved_then_fulfilled_as_a_dispatch():
    env = await _env()
    async with _client() as c:
        req = await _request(c, env, qty=8)
        assert (await c.post(f"/operations/stock-requests/{req}/fulfil", headers=env["h"]["manager"])).status_code == 400
        assert (await c.post(f"/operations/stock-requests/{req}/approve", headers=env["h"]["storekeeper"])).status_code == 403
        r = await c.post(f"/operations/stock-requests/{req}/approve", headers=env["h"]["manager"], json={"note": "موافق"})
        assert r.status_code == 200 and r.json()["status"] == "approved"
        # The storekeeper of A doesn't work in B, where the goods leave from.
        assert (await c.post(f"/operations/stock-requests/{req}/fulfil", headers=env["h"]["storekeeper"])).status_code == 403
        r = await c.post(f"/operations/stock-requests/{req}/fulfil", headers=env["h"]["manager"], json={
            "items": [{"product_id": str(env["product"]), "qty": 9}]})
        assert r.status_code == 400  # more than asked for
        r = await c.post(f"/operations/stock-requests/{req}/fulfil", headers=env["h"]["manager"], json={
            "items": [{"product_id": str(env["product"]), "qty": 6}]})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["status"] == "fulfilled" and out["metadata"]["dispatch_number"].startswith("DSP-")
        assert (await c.post(f"/operations/stock-requests/{req}/fulfil", headers=env["h"]["manager"])).status_code == 400
        assert (await c.post(f"/operations/stock-requests/{req}/cancel", headers=env["h"]["manager"])).status_code == 400
        listed = (await c.get("/operations/", params={"doc_type": "stock_request", "status": "fulfilled"},
                              headers=env["h"]["manager"])).json()
        assert [d["id"] for d in listed["items"]] == [req]
    assert await _balance(env, env["a"]) == D("16") and await _balance(env, env["b"]) == D("14")
    actions = {r["action"] for r in await _rows(env, "SELECT action FROM audit_log WHERE entity_type = 'stock_request'")}
    assert actions == {"create", "approve", "fulfil"}


async def test_a_stock_request_is_cancelled_by_its_maker_before_approval_or_by_an_approver():
    env = await _env()
    async with _client() as c:
        own = await _request(c, env)
        r = await c.post(f"/operations/stock-requests/{own}/cancel", headers=env["h"]["storekeeper"], json={"reason": "لا داعي"})
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
        assert (await c.post(f"/operations/stock-requests/{own}/approve", headers=env["h"]["manager"])).status_code == 400

        approved = await _request(c, env)
        await c.post(f"/operations/stock-requests/{approved}/approve", headers=env["h"]["manager"])
        # Once approved its maker can't cancel it; an approver can (a rejection).
        assert (await c.post(f"/operations/stock-requests/{approved}/cancel", headers=env["h"]["storekeeper"])).status_code == 403
        r = await c.post(f"/operations/stock-requests/{approved}/cancel", headers=env["h"]["manager"])
        assert r.status_code == 200 and r.json()["metadata"]["cancelled_by"] == "manager"

        theirs = await _request(c, env, who="manager")
        assert (await c.post(f"/operations/stock-requests/{theirs}/cancel", headers=env["h"]["storekeeper"])).status_code == 403
        assert (await c.post(f"/operations/stock-requests/{uuid.uuid4()}/approve", headers=env["h"]["manager"])).status_code == 404
    assert await _balance(env, env["a"]) == D("10")


async def test_another_workspaces_orders_and_stock_requests_are_not_found():
    env, other = await _env(), await _env()
    async with _client() as c:
        po = await _order(c, env, [{"product_id": str(env["product"]), "qty": 2, "unit_cost": 50}])
        for method, path in (("post", "cancel"), ("post", "close"), ("delete", "")):
            r = await getattr(c, method)(f"/purchases/{po}" + (f"/{path}" if path else ""), headers=other["h"]["manager"])
            assert r.status_code == 404, (path, r.text)
        assert (await c.post(f"/purchases/{po}/cancel", headers=env["h"]["manager"])).status_code == 200
        req = await _request(c, env)
        assert (await c.post(f"/operations/stock-requests/{req}/approve", headers=other["h"]["manager"])).status_code == 404
        assert (await c.post(f"/operations/stock-requests/{req}/cancel", headers=other["h"]["manager"])).status_code == 404
        assert (await c.post(f"/operations/stock-requests/{req}/approve", headers=env["h"]["manager"])).status_code == 200


# ── The pharmacy's batch receipt ─────────────────────────────────────────────────────────────

async def test_the_pharmacy_batch_receipt_without_a_supplier_is_gone():
    env = await _env(extra_modules=("pharmacy",))
    async with _client() as c:
        r = await c.post("/pharmacy/batches", headers=env["h"]["manager"], json={
            "product_id": str(env["product"]), "warehouse_id": str(env["a"]), "batch_number": "B1",
            "expiry_date": "2027-01-01", "quantity": 5, "purchase_cost": 10})
        assert r.status_code == 410 and "أمر الشراء" in r.json()["detail"]
    assert await _balance(env, env["a"]) == D("10")
