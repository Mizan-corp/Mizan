"""Inventory and purchases, phase B of PRODUCTION_READINESS.md: permissions on reads, validation,
error codes, indexes.

- INV-4 names, lengths and barcodes bounded and unique (409/422/404, never a 500); collections checked;
- INV-8 the catalogue is read by those who sell, buy or move stock; costs only with inventory,
  purchases or reports; the movement log only with inventory;
- INV-11 bounded product pages and bulk reorder, Arabic errors;
- PUR-3 typed and checked input; PUR-5 reads for purchasing or finance, a paged supplier ledger with a
  running balance, suggestions from the maintained balances; PUR-6 indexes, receipts honour closed
  months; PUR-7 Arabic errors, `auto_update_purchase_price` read.
Each test fails on the code before these fixes.
"""
import json
import os
import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.activities.general.modules.contacts.models.party import Supplier
from app.activities.general.modules.inventory.models.product import Category, Product, Subcategory
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.stock_balance import StockBalance
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement
from app.db.base import AsyncSessionLocal
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
ARABIC = range(0x0600, 0x06FF)


def _arabic(detail) -> bool:
    return isinstance(detail, str) and any(ord(ch) in ARABIC for ch in detail)


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


# The users of the workspace and what their role holds: the standard roles' permissions, a clerk who
# only keeps the customer list, and a finance officer with nothing of purchasing.
ROLES = {"manager": None, "storekeeper": None, "accountant": None, "cashier": None,
         "clerk": ["customers"], "treasurer": ["finance"]}


async def _env() -> dict:
    """A workspace with warehouse A, the users of ROLES (the cashier and the storekeeper work in A), a category with a
    subcategory, a supplier, and a tracked product (cost 60) with 10 units in A."""
    t = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=t, name=f"B {t.hex[:6]}", slug=f"b-stock-{t.hex[:8]}", status="active", active_modules=MODULES))
        await s.flush()
        a = Warehouse(id=uuid.uuid4(), tenant_id=t, code=f"A-{t.hex[:4]}", name="المخزن أ", is_active=True)
        cat = Category(id=uuid.uuid4(), tenant_id=t, name="مشروبات")
        sub = Subcategory(id=uuid.uuid4(), tenant_id=t, category_id=cat.id, name="عصائر")
        users, grants = {}, {}
        for role, own in ROLES.items():
            grants[role] = own if own is not None else standard_permissions(role)
            users[role] = User(id=uuid.uuid4(), tenant_id=t, username=f"{role[:5]}_{t.hex[:8]}", full_name=role,
                               role=role if own is None else "cashier", password_hash=hash_password("Pass123!"),
                               is_manager=role == "manager", permissions=grants[role], is_active=True)
        product = Product(id=uuid.uuid4(), tenant_id=t, subcategory_id=sub.id, name="عصير برتقال", code=f"P-{t.hex[:6]}",
                          barcode=f"62{t.int % 10**11:011d}", retail_price=D("100"), cost_price=D("60"),
                          stock_status="tracked", is_active=True)
        supplier = Supplier(id=uuid.uuid4(), tenant_id=t, name="مورد", balance=D("0"))
        s.add_all([a, cat, sub, *users.values(), product, supplier])
        await s.flush()
        for role in ("cashier", "storekeeper"):
            await s.execute(text("INSERT INTO user_warehouses (user_id, warehouse_id) VALUES (:u, :w)"),
                            {"u": users[role].id, "w": a.id})
        await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        for role, u in users.items():
            rid = uuid.uuid4()
            await s.execute(text(
                "INSERT INTO sys_roles (id, tenant_id, code, name, name_en, is_system, is_clinical, grants) "
                "VALUES (:id, :t, :c, :c, :c, false, false, CAST(:g AS jsonb))"),
                {"id": rid, "t": t, "c": f"{role}-{rid.hex[:8]}", "g": json.dumps(grants[role])})
            await assign_roles(s, u, [rid])
        await s.commit()
    current_tenant_id.set(t)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        await apply_movement(s, product_id=product.id, warehouse_id=a.id, movement_type=MovementType.opening_stock,
                             qty=D("10"), unit_cost=D("60"), created_by=users["manager"].id)
        await s.commit()

    def headers(u):
        return {"Authorization": "Bearer " + create_access_token(
            {"sub": str(u.id), "role": u.role, "username": u.username, "tid": str(t)})}

    return {"tenant_id": t, "a": a.id, "category": cat.id, "subcategory": sub.id, "product": product.id,
            "barcode": product.barcode, "supplier": supplier.id, "users": {k: u.id for k, u in users.items()},
            "h": {k: headers(u) for k, u in users.items()}}


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _sql(env, sql: str, **params):
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        r = await s.execute(text(sql), params)
        value = r.scalar() if r.returns_rows else None
        await s.commit()
        return value


def _product_body(env, **kw):
    return {"subcategory_id": str(env["subcategory"]), "name": "صنف جديد", "retail_price": "10",
            "cost_price": "6", **kw}


# ── INV-4 ────────────────────────────────────────────────────────────────────────────────────────

async def test_category_and_subcategory_names_are_bounded_and_unique():
    env = await _env()
    h = env["h"]["storekeeper"]
    async with _client() as c:
        r = await c.post("/categories", json={"name": "مشروبات"}, headers=h)
        assert r.status_code == 409 and _arabic(r.json()["detail"]), r.text
        assert (await c.post("/categories", json={"name": "س" * 129}, headers=h)).status_code == 422
        assert (await c.post("/categories", json={"name": "   "}, headers=h)).status_code == 422
        other = (await c.post("/categories", json={"name": "  حلويات "}, headers=h)).json()
        assert other["name"] == "حلويات"
        r = await c.put(f"/categories/{other['id']}", json={"name": "مشروبات"}, headers=h)
        assert r.status_code == 409
        r = await c.put(f"/categories/{uuid.uuid4()}", json={"name": "أي"}, headers=h)
        assert r.status_code == 404 and _arabic(r.json()["detail"])

        sub = {"category_id": str(env["category"]), "name": "عصائر"}
        r = await c.post("/subcategories", json=sub, headers=h)
        assert r.status_code == 409 and _arabic(r.json()["detail"]), r.text
        # The same name under another category is allowed; an unknown category is a 404.
        assert (await c.post("/subcategories", json={**sub, "category_id": other["id"]}, headers=h)).status_code == 200
        r = await c.post("/subcategories", json={**sub, "category_id": str(uuid.uuid4())}, headers=h)
        assert r.status_code == 404 and _arabic(r.json()["detail"])
        assert (await c.post("/subcategories", json={**sub, "name": "x" * 129}, headers=h)).status_code == 422


async def test_product_fields_are_bounded_and_unknown_subcategories_are_404():
    env = await _env()
    h = env["h"]["storekeeper"]
    async with _client() as c:
        for field, value in (("name", "x" * 257), ("code", "x" * 33), ("barcode", "1" * 65), ("unit", "x" * 33),
                             ("retail_price", "-1"), ("retail_price", "99999999999"), ("shelf_number", "x" * 33)):
            r = await c.post("/products", json=_product_body(env, **{field: value}), headers=h)
            assert r.status_code == 422, (field, r.text)
        r = await c.post("/products", json=_product_body(env, subcategory_id=str(uuid.uuid4())), headers=h)
        assert r.status_code == 404 and _arabic(r.json()["detail"])
        r = await c.put(f"/products/{env['product']}", json={"name": "x" * 257}, headers=h)
        assert r.status_code == 422
        r = await c.put(f"/products/{env['product']}", json={"subcategory_id": str(uuid.uuid4())}, headers=h)
        assert r.status_code == 404


async def test_a_barcode_belongs_to_one_active_product():
    env = await _env()
    h = env["h"]["storekeeper"]
    code = env["barcode"]
    async with _client() as c:
        r = await c.post("/products", json=_product_body(env, barcode=code), headers=h)
        assert r.status_code == 409 and "عصير برتقال" in r.json()["detail"], r.text
        # As an extra barcode of another product, too.
        other = (await c.post("/products", json=_product_body(env, barcode=code + "9"), headers=h)).json()
        r = await c.post(f"/products/{other['id']}/barcodes", json={"barcode": code}, headers=h)
        assert r.status_code == 409, r.text
        r = await c.put(f"/products/{other['id']}", json={"barcode": code}, headers=h)
        assert r.status_code == 409, r.text

        # Once the first is deactivated its barcode may go to a new product, and a scan finds the active one.
        assert (await c.delete(f"/products/{env['product']}", headers=h)).status_code == 204
        new = await c.post("/products", json=_product_body(env, barcode=code), headers=h)
        assert new.status_code == 200, new.text
        r = await c.get(f"/products/barcode/{code}", headers=h)
        assert r.status_code == 200 and r.json()["id"] == new.json()["id"]
        # Bringing the old one back while the barcode is taken is refused.
        r = await c.put(f"/products/{env['product']}", json={"is_active": True}, headers=h)
        assert r.status_code == 409

        # An inactive product is never found by its barcode.
        assert (await c.delete(f"/products/{new.json()['id']}", headers=h)).status_code == 204
        r = await c.get(f"/products/barcode/{code}", headers=h)
        assert r.status_code == 404 and r.json()["detail"] == "لا يوجد صنف نشط بهذا الباركود"
        r = await c.get(f"/products/barcode/{'9' * 80}", headers=h)
        assert r.status_code == 404


async def test_the_barcode_index_refuses_two_active_products():
    """The partial unique index of v101 (the model declares it; create_all builds it)."""
    env = await _env()
    from sqlalchemy.exc import IntegrityError

    async def add(barcode, active=True):
        current_tenant_id.set(env["tenant_id"])
        async with AsyncSessionLocal() as s:
            await bind_tenant(s, env["tenant_id"])
            s.add(Product(id=uuid.uuid4(), tenant_id=env["tenant_id"], name="نسخة", barcode=barcode, is_active=active,
                          retail_price=D("1")))
            await s.commit()

    with pytest.raises(IntegrityError, match="uq_products_tenant_barcode_active"):
        await add(env["barcode"])
    # Inactive copies are not refused (history), nor are empty barcodes.
    await add(env["barcode"], active=False)
    await add("")
    await add("")


async def test_collections_check_products_prices_and_ids():
    env = await _env()
    other = await _env()  # another workspace's product
    h = env["h"]["storekeeper"]
    item = {"product_id": str(env["product"]), "qty": "2"}
    async with _client() as c:
        r = await c.post("/collections", json={"name": "عرض", "items": [{**item, "product_id": str(other["product"])}]}, headers=h)
        assert r.status_code == 404 and _arabic(r.json()["detail"]), r.text
        r = await c.post("/collections", json={"name": "عرض", "items": [{**item, "product_id": str(uuid.uuid4())}]}, headers=h)
        assert r.status_code == 404
        assert (await c.post("/collections", json={"name": "عرض", "retail_price": "-1", "items": [item]}, headers=h)).status_code == 422
        assert (await c.post("/collections", json={"name": "عرض", "items": [item] * 201}, headers=h)).status_code == 422
        assert (await c.post("/collections", json={"name": "عرض", "items": [item, item]}, headers=h)).status_code == 400
        r = await c.post("/collections", json={"name": "عرض", "retail_price": "150", "items": [item]}, headers=h)
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        r = await c.put(f"/collections/{uuid.uuid4()}", json={"name": "عرض", "items": [item]}, headers=h)
        assert r.status_code == 404 and _arabic(r.json()["detail"])
        assert (await c.delete(f"/collections/{uuid.uuid4()}", headers=h)).status_code == 404
        r = await c.get(f"/collections/{cid}/availability", params={"warehouse_id": str(env["a"])}, headers=h)
        assert r.status_code == 200 and r.json()["can_make"] == 5  # 10 in stock, 2 a collection
    assert await _sql(env, "SELECT COUNT(*) FROM collection_items") == 1


# ── INV-8 ────────────────────────────────────────────────────────────────────────────────────────

async def test_catalogue_reads_need_a_permission_and_costs_are_for_stock_roles():
    env = await _env()
    pid, code = str(env["product"]), env["barcode"]
    async with _client() as c:
        coll = await c.post("/collections", json={"name": "عرض", "items": [{"product_id": pid, "qty": "1"}]},
                            headers=env["h"]["storekeeper"])
        assert coll.status_code == 201
        reads = ["/products", f"/products/{pid}", f"/products/barcode/{code}", "/categories", "/subcategories",
                 "/collections"]
        # Someone who only keeps the customer list reads no catalogue, stock or costs.
        for path in reads:
            assert (await c.get(path, headers=env["h"]["clerk"])).status_code == 403, path
        r = await c.post("/stock/balance/bulk", params={"warehouse_id": str(env["a"])}, json=[pid], headers=env["h"]["clerk"])
        assert r.status_code == 403
        assert (await c.post("/stock/balance/total", json=[pid], headers=env["h"]["clerk"])).status_code == 403
        assert (await c.get(f"/stock/balance/breakdown/{pid}", headers=env["h"]["clerk"])).status_code == 403

        # A cashier finds what to sell, with its price and the branch's stock, but no cost.
        r = await c.get("/products", params={"search": "عصير", "warehouse_id": str(env["a"])}, headers=env["h"]["cashier"])
        assert r.status_code == 200, r.text
        row = r.json()["items"][0]
        assert row["id"] == pid and D(row["retail_price"]) == D("100") and D(str(row["current_qty"])) == D("10")
        assert row["cost_price"] is None and row["avg_cost"] is None
        for path in (f"/products/{pid}", f"/products/barcode/{code}"):
            got = (await c.get(path, headers=env["h"]["cashier"])).json()
            assert got["cost_price"] is None and got["avg_cost"] is None, path
        scan = await c.get(f"/pos/scan/{code}", params={"warehouse_id": str(env["a"])}, headers=env["h"]["cashier"])
        assert scan.status_code == 200 and scan.json()["product"]["cost_price"] is None
        items = (await c.get("/collections", headers=env["h"]["cashier"])).json()["items"][0]["items"]
        assert items[0]["cost_price"] is None
        assert (await c.get("/categories", headers=env["h"]["cashier"])).status_code == 200
        # The movement log carries costs: inventory only.
        assert (await c.get(f"/products/{pid}/movements", headers=env["h"]["cashier"])).status_code == 403

        # Stock and purchasing roles see the costs.
        for role in ("storekeeper", "accountant", "manager"):
            got = (await c.get(f"/products/{pid}", headers=env["h"][role])).json()
            assert D(got["cost_price"]) == D("60") and D(got["avg_cost"]) == D("60"), role
        items = (await c.get("/collections", headers=env["h"]["storekeeper"])).json()["items"][0]["items"]
        assert D(str(items[0]["cost_price"])) == D("60")
        r = await c.get(f"/products/{pid}/movements", headers=env["h"]["storekeeper"],
                        params={"from_date": "2000-01-01", "to_date": datetime.now().date().isoformat()})
        assert r.status_code == 200 and r.json()["total"] == 1
        r = await c.get(f"/products/{pid}/movements", params={"from_date": "x"}, headers=env["h"]["storekeeper"])
        assert r.status_code == 422
        r = await c.get(f"/products/{uuid.uuid4()}/movements", headers=env["h"]["storekeeper"])
        assert r.status_code == 404


# ── INV-11 ───────────────────────────────────────────────────────────────────────────────────────

async def test_product_pages_and_bulk_reorder_are_bounded():
    env = await _env()
    h = env["h"]["storekeeper"]
    async with _client() as c:
        page = (await c.get("/products", headers=h)).json()
        assert page["size"] == 50 and page["total"] == 1
        assert (await c.get("/products", params={"page_size": 501}, headers=h)).status_code == 422
        assert (await c.get("/products", params={"search": "x" * 129}, headers=h)).status_code == 422
        body = {"product_ids": [str(uuid.uuid4()) for _ in range(501)], "reorder_level": 3}
        assert (await c.post("/products/bulk-reorder-level", json=body, headers=h)).status_code == 422
        body = {"product_ids": [str(env["product"])], "reorder_level": -1}
        assert (await c.post("/products/bulk-reorder-level", json=body, headers=h)).status_code == 422
        assert (await c.post("/products/bulk-reorder-level", json={"product_ids": []}, headers=h)).status_code == 422
        r = await c.post("/products/bulk-reorder-level", json={"product_ids": [str(env["product"])], "reorder_level": 7}, headers=h)
        assert r.json()["updated_count"] == 1
        r = await c.get(f"/products/{uuid.uuid4()}", headers=h)
        assert r.status_code == 404 and r.json()["detail"] == "الصنف غير موجود"
        r = await c.put(f"/barcodes/{uuid.uuid4()}", json={"barcode": "1"}, headers=h)
        assert r.status_code == 404 and _arabic(r.json()["detail"])


# ── PUR-3, PUR-7 ─────────────────────────────────────────────────────────────────────────────────

async def test_purchases_input_is_typed_and_unknown_references_are_arabic_404s():
    env = await _env()
    h = env["h"]["storekeeper"]
    async with _client() as c:
        assert (await c.post("/suppliers", json={"name": "س", "type": "anything"}, headers=h)).status_code == 422
        assert (await c.get("/suppliers", params={"type": "anything"}, headers=h)).status_code == 422
        r = await c.post("/suppliers", json={"name": "  شركة النيل ", "type": "manufacturer"}, headers=h)
        assert r.status_code == 201 and r.json()["name"] == "شركة النيل"
        found = (await c.get("/suppliers", params={"search": "النيل"}, headers=h)).json()
        assert [x["name"] for x in found["items"]] == ["شركة النيل"]
        for q in ({"page": 0}, {"page_size": 201}):
            assert (await c.get("/purchases", params=q, headers=h)).status_code == 422
        r = await c.post("/purchases/quick-add-product", json={"name": "جديد", "retail_price": "-1"}, headers=h)
        assert r.status_code == 422
        r = await c.post("/purchases/quick-add-product", json={"name": "جديد", "subcategory_id": str(uuid.uuid4())}, headers=h)
        assert r.status_code == 404 and _arabic(r.json()["detail"])
        r = await c.post("/purchases/quick-add-product", json={"name": "جديد", "cost_price": "1.5", "retail_price": "3"}, headers=h)
        assert r.status_code == 200 and D(str(r.json()["cost_price"])) == D("1.50")

        for path in (f"/purchases/supplier-prices/product/{uuid.uuid4()}", f"/purchases/price-history/{uuid.uuid4()}",
                     f"/purchases/{uuid.uuid4()}", f"/purchases/{uuid.uuid4()}/returns", f"/suppliers/{uuid.uuid4()}/ledger"):
            r = await c.get(path, headers=h)
            assert r.status_code == 404 and _arabic(r.json()["detail"]), (path, r.text)
        for method, path, body in (("put", f"/purchases/supplier-prices/{uuid.uuid4()}", {"price": "5"}),
                                   ("delete", f"/purchases/supplier-prices/{uuid.uuid4()}", None),
                                   ("put", f"/purchases/{uuid.uuid4()}", {"notes": "x"})):
            r = await c.request(method.upper(), path, json=body, headers=h)
            assert r.status_code == 404 and _arabic(r.json()["detail"]), (path, r.text)
        r = await c.post("/purchases/supplier-prices", headers=h,
                         json={"supplier_id": str(env["supplier"]), "product_id": str(uuid.uuid4()), "price": "5"})
        assert r.status_code == 404 and _arabic(r.json()["detail"])


async def test_a_receipt_updates_the_listed_cost_only_while_the_setting_is_on():
    env = await _env()
    po = {"warehouse_id": str(env["a"]), "supplier_id": str(env["supplier"]),
          "items": [{"product_id": str(env["product"]), "qty": "5", "unit_cost": "80"}]}
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        from app.framework.loader import registry
        await registry.save_settings(s, "purchases", {"auto_update_purchase_price": False})
        await s.commit()
    async with _client() as c:
        pid = (await c.post("/purchases", json=po, headers=env["h"]["storekeeper"])).json()["id"]
        r = await c.post(f"/purchases/{pid}/receive", json={}, headers=env["h"]["storekeeper"])
        assert r.status_code == 200, r.text
        hist = (await c.get(f"/purchases/price-history/{env['product']}", headers=env["h"]["storekeeper"])).json()
    assert await _sql(env, "SELECT cost_price FROM products WHERE id = :p", p=env["product"]) == D("60.00")
    assert D(str(hist[0]["new_cost"])) == D("80.00")  # the purchase price is still recorded
    # The average cost follows the receipt whatever the setting: (10 × 60 + 5 × 80) / 15.
    assert await _sql(env, "SELECT round(avg_cost, 2) FROM products WHERE id = :p", p=env["product"]) == D("66.67")

    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        await registry.save_settings(s, "purchases", {"auto_update_purchase_price": True})
        await s.commit()
    async with _client() as c:
        pid = (await c.post("/purchases", json=po, headers=env["h"]["storekeeper"])).json()["id"]
        assert (await c.post(f"/purchases/{pid}/receive", json={}, headers=env["h"]["storekeeper"])).status_code == 200
    assert await _sql(env, "SELECT cost_price FROM products WHERE id = :p", p=env["product"]) == D("80.00")


# ── PUR-5 ────────────────────────────────────────────────────────────────────────────────────────

async def test_purchase_reads_for_purchasing_or_finance_and_a_paged_supplier_ledger():
    env = await _env()
    sup = str(env["supplier"])
    async with _client() as c:
        for i, kind in enumerate(("debit", "debit", "credit")):
            body = {"amount": str(100 * (i + 1)), "type": kind}
            if kind == "credit":
                safe = uuid.uuid4()
                await _sql(env, "INSERT INTO safes (id, tenant_id, name, balance) VALUES (:id, :t, 'خزنة', 1000)",
                           id=safe, t=env["tenant_id"])
                body["safe_id"] = str(safe)
            r = await c.post(f"/suppliers/{sup}/transactions", json=body, headers=env["h"]["treasurer"])
            assert r.status_code == 201, r.text
        # Oldest first: +100, +200, −300; each line with what we owe after it, on every page.
        first = (await c.get(f"/suppliers/{sup}/ledger", params={"page_size": 2}, headers=env["h"]["treasurer"])).json()
        assert first["total"] == 3 and first["pages"] == 2
        assert [D(str(x["balance"])) for x in first["items"]] == [D("100"), D("300")]
        last = (await c.get(f"/suppliers/{sup}/ledger", params={"page_size": 2, "page": 2}, headers=env["h"]["treasurer"])).json()
        assert [(x["type"], D(str(x["credit"])), D(str(x["balance"]))) for x in last["items"]] == [("credit", D("300"), D("0"))]
        newest = (await c.get(f"/suppliers/{sup}/ledger", params={"newest_first": "true", "page_size": 1},
                              headers=env["h"]["storekeeper"])).json()
        assert D(str(newest["items"][0]["balance"])) == D("0") and D(str(newest["supplier"]["balance"])) == D("0")
        assert (await c.get(f"/suppliers/{sup}/ledger", params={"page_size": 501}, headers=env["h"]["storekeeper"])).status_code == 422

        # Finance reads orders and costs; neither a cashier nor a customers clerk does.
        assert (await c.get("/purchases", headers=env["h"]["treasurer"])).status_code == 200
        assert (await c.get(f"/purchases/price-history/{env['product']}", headers=env["h"]["treasurer"])).status_code == 200
        for role in ("cashier", "clerk"):
            for path in ("/purchases", "/purchases/suggestions", f"/suppliers/{sup}/ledger", "/suppliers"):
                assert (await c.get(path, headers=env["h"][role])).status_code == 403, (role, path)


async def test_suggestions_read_the_maintained_balances():
    """A product whose stock is in stock_balances (opening data loaded without movements, as the demo
    does) was suggested by the scan of the movements, which saw none."""
    env = await _env()
    t = env["tenant_id"]
    current_tenant_id.set(t)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        stocked = Product(id=uuid.uuid4(), tenant_id=t, name="مخزون كافٍ", retail_price=D("5"), reorder_point=D("5"),
                          stock_status="tracked", is_active=True)
        short = Product(id=uuid.uuid4(), tenant_id=t, name="ناقص", retail_price=D("5"), reorder_point=D("5"),
                        stock_status="tracked", is_active=True)
        service = Product(id=uuid.uuid4(), tenant_id=t, name="خدمة", retail_price=D("5"), reorder_point=D("5"),
                          stock_status="untracked", is_active=True)
        s.add_all([stocked, short, service])
        await s.flush()
        s.add_all([StockBalance(tenant_id=t, product_id=stocked.id, warehouse_id=env["a"], qty=D("20")),
                   StockBalance(tenant_id=t, product_id=short.id, warehouse_id=env["a"], qty=D("2"))])
        await s.commit()
    async with _client() as c:
        r = await c.get("/purchases/suggestions", headers=env["h"]["storekeeper"])
        assert r.status_code == 200, r.text
    names = [x["name"] for x in r.json()]
    assert names == ["ناقص"], names


# ── PUR-6 ────────────────────────────────────────────────────────────────────────────────────────

async def test_receiving_in_a_closed_month_is_refused():
    env = await _env()
    po = {"warehouse_id": str(env["a"]), "supplier_id": str(env["supplier"]),
          "items": [{"product_id": str(env["product"]), "qty": "1", "unit_cost": "5"}]}
    async with _client() as c:
        pid = (await c.post("/purchases", json=po, headers=env["h"]["storekeeper"])).json()["id"]
        await _sql(env, "INSERT INTO accounting_periods (id, tenant_id, month, status) VALUES (:id, :t, :m, 'closed')",
                   id=uuid.uuid4(), t=env["tenant_id"], m=datetime.now().strftime("%Y-%m"))
        r = await c.post(f"/purchases/{pid}/receive", json={}, headers=env["h"]["storekeeper"])
        assert r.status_code == 400 and "مغلق" in r.json()["detail"], r.text
    assert await _sql(env, "SELECT status::text FROM purchase_orders WHERE id = :id", id=pid) == "draft"


def test_the_models_declare_the_indexes_the_lists_filter_on():
    """CI builds tables from the models: the indexes must be declared there too (v101 makes them in
    migrated databases)."""
    from app.db.base import Base

    def names(table):
        return {i.name for i in Base.metadata.tables[table].indexes}

    assert {"idx_purchase_order_items_po_id", "idx_purchase_order_items_product_id"} <= names("purchase_order_items")
    assert "idx_sup_tx_supplier" in names("supplier_transactions")
    assert "idx_pph_product" in names("purchase_price_history")
    assert "idx_purchase_orders_supplier_id" in names("purchase_orders")
    assert "uq_products_tenant_barcode_active" in names("products")
    assert "uq_subcategories_category_name" in {c.name for c in Base.metadata.tables["subcategories"].constraints}


async def test_v101_makes_the_unique_indexes_only_where_the_data_allows():
    from app.db.migrations import MIGRATIONS, split_statements

    sql = dict(MIGRATIONS)["v101_b_stock_pur"]
    assert MIGRATIONS[-1][0] == "v101_b_stock_pur" or "v101_b_stock_pur" in dict(MIGRATIONS)
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        for stmt in split_statements(sql):
            await s.execute(text(stmt))  # runs cleanly where the indexes already exist
        names = set((await s.execute(text(
            "SELECT indexname FROM pg_indexes WHERE indexname IN "
            "('uq_products_tenant_barcode_active', 'uq_subcategories_category_name', 'idx_sup_tx_supplier', "
            "'idx_pph_product', 'idx_purchase_orders_supplier_id', 'idx_purchase_order_items_po_id', "
            "'idx_purchase_order_items_product_id')"))).scalars())
        await s.rollback()
    assert len(names) == 7, names
