"""Stock, stock operations and purchases made production-ready (PRODUCTION_READINESS.md, Phase A).

- INV-1 balances are never clamped and every out-movement is checked (untracked decided by the product);
- INV-2 only adjustments and damage by hand, opening stock under `inventory:opening`, costs >= 0;
- INV-3 a stock reset never deletes what the ledger holds and rebuilds the average cost;
- INV-5 transfers: two different warehouses the user works in, audited;
- INV-6 a warehouse holding stock can't be deactivated; INV-7 valuation at average cost;
- OPS-1 goods receipt without a supplier or ledger entry is gone; OPS-2 branch access on operations;
- PUR-1 supplier payments need `finance`, purchasing needs `purchases`; PUR-2 orders show a total.
Each test fails on the code before these fixes.
"""
import json
import os
import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.activities.general.modules.contacts.models.party import Supplier
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement, get_balance
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


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _env(accounting: bool = False) -> dict:
    """A workspace with warehouses A and B, a manager, a storekeeper of A only and an accountant, a
    supplier, a safe holding 1000, and a tracked product with 10 units at cost 60 in A."""
    t = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=t, name=f"Ready {t.hex[:6]}", slug=f"ready-{t.hex[:8]}", status="active",
                     active_modules=MODULES + (["accounting"] if accounting else [])))
        await s.flush()
        a = Warehouse(id=uuid.uuid4(), tenant_id=t, code=f"A-{t.hex[:4]}", name="المخزن أ", is_active=True)
        b = Warehouse(id=uuid.uuid4(), tenant_id=t, code=f"B-{t.hex[:4]}", name="المخزن ب", is_active=True)
        users = {}
        for role, manager in (("manager", True), ("storekeeper", False), ("accountant", False)):
            users[role] = User(id=uuid.uuid4(), tenant_id=t, username=f"{role[:5]}_{t.hex[:8]}", full_name=role,
                               role=role, password_hash=hash_password("Pass123!"), is_manager=manager,
                               permissions=standard_permissions(role), is_active=True)
        product = Product(id=uuid.uuid4(), tenant_id=t, name="صنف مخزن", code=f"P-{t.hex[:6]}",
                          retail_price=D("100"), cost_price=D("60"), stock_status="tracked", is_active=True)
        service = Product(id=uuid.uuid4(), tenant_id=t, name="خدمة", code=f"S-{t.hex[:6]}",
                          retail_price=D("50"), cost_price=D("0"), stock_status="untracked", is_active=True)
        supplier = Supplier(id=uuid.uuid4(), tenant_id=t, name="مورد", balance=D("0"))
        s.add_all([a, b, *users.values(), product, service, supplier])
        await s.flush()
        await s.execute(text("INSERT INTO user_warehouses (user_id, warehouse_id) VALUES (:u, :w)"),
                        {"u": users["storekeeper"].id, "w": a.id})
        # Each user gets a workspace role holding exactly the standard role's permissions of this code
        # (the shared standard roles may be re-synced meanwhile by another checkout's tests).
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
        await apply_movement(s, product_id=product.id, warehouse_id=a.id, movement_type=MovementType.opening_stock,
                             qty=D("10"), unit_cost=D("60"), created_by=users["manager"].id)
        await s.commit()

    def headers(u):
        return {"Authorization": "Bearer " + create_access_token(
            {"sub": str(u.id), "role": u.role, "username": u.username, "tid": str(t)})}

    return {"tenant_id": t, "a": a.id, "b": b.id, "product": product.id, "service": service.id,
            "supplier": supplier.id, "safe": safe_id, "users": {k: u.id for k, u in users.items()},
            "h": {k: headers(u) for k, u in users.items()}}


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _scalar(env, sql: str, **params):
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        return (await s.execute(text(sql), params)).scalar()


async def _balance(env, product, warehouse) -> Decimal:
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        return await get_balance(s, product, warehouse)


async def _movements_sum(env, product, warehouse) -> Decimal:
    return D(str(await _scalar(env, """
        SELECT COALESCE(SUM(CASE WHEN movement_type::text IN
            ('opening_stock','purchase','return_in','adjustment_in','transfer_in') THEN qty ELSE -qty END), 0)
        FROM stock_movements WHERE product_id = :p AND warehouse_id = :w""", p=product, w=warehouse)))


async def _move(env, kind, qty, *, product=None, warehouse=None, **kw):
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        mv, _ = await apply_movement(s, product_id=product or env["product"], warehouse_id=warehouse or env["a"],
                                     movement_type=kind, qty=D(str(qty)), note="اختبار", **kw)
        await s.commit()
        return mv


# ── INV-1 ────────────────────────────────────────────────────────────────────────────────────────

async def test_out_movement_beyond_the_balance_is_refused_and_never_clamped():
    env = await _env()
    with pytest.raises(HTTPException) as e:
        await _move(env, MovementType.adjustment_out, 15)
    assert e.value.status_code == 400 and "الرصيد غير كافٍ" in e.value.detail
    assert await _balance(env, env["product"], env["a"]) == D("10")

    # The workspace allows negative stock: the balance goes below zero and still equals the movements.
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        from app.framework.loader import registry
        await registry.save_settings(s, "inventory", {"prevent_negative_stock": False})
        await s.commit()
    await _move(env, MovementType.damage, 15)
    assert await _balance(env, env["product"], env["a"]) == D("-5")
    assert await _movements_sum(env, env["product"], env["a"]) == D("-5")


async def test_tracked_product_is_checked_in_a_warehouse_without_a_status_row():
    """It was treated as untracked in sales wherever it had no warehouse_product_status row."""
    env = await _env()
    from app.activities.general.modules.sales.services.sales import _is_untracked

    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        assert await _is_untracked(s, env["product"], env["b"]) is False
        assert await _is_untracked(s, env["service"], env["b"]) is True
    with pytest.raises(HTTPException, match="الرصيد غير كافٍ"):
        await _move(env, MovementType.sale, 1, warehouse=env["b"])
    assert await _balance(env, env["product"], env["b"]) == D("0")
    # An untracked product (a service) is sold without stock; its balance follows the movements.
    await _move(env, MovementType.sale, 2, product=env["service"], warehouse=env["b"])
    assert await _balance(env, env["service"], env["b"]) == D("-2")
    # A document that decided so (offline sale sync) may still go below zero.
    await _move(env, MovementType.sale, 12, allow_negative=True)
    assert await _balance(env, env["product"], env["a"]) == D("-2") == await _movements_sum(env, env["product"], env["a"])


# ── INV-2 ────────────────────────────────────────────────────────────────────────────────────────

async def test_hand_movements_are_adjustments_and_damage_only():
    env = await _env()
    body = {"product_id": str(env["product"]), "warehouse_id": str(env["a"]), "qty": "3", "unit_cost": "70", "note": "x"}
    async with _client() as c:
        for kind in ("purchase", "sale", "return_in", "transfer_in", "transfer_out", "return_out"):
            r = await c.post("/stock/movements", json={**body, "movement_type": kind}, headers=env["h"]["manager"])
            assert r.status_code == 400, (kind, r.text)
        r = await c.post("/stock/adjustment/bulk", json=[{**body, "movement_type": "adjustment_in"},
                                                         {**body, "movement_type": "purchase"}], headers=env["h"]["manager"])
        assert r.status_code == 400
        r = await c.post("/stock/movements", json={**body, "movement_type": "adjustment_in", "unit_cost": "-5"},
                         headers=env["h"]["manager"])
        assert r.status_code == 422
        # Opening stock needs its own permission: the storekeeper doesn't hold it, the manager does.
        r = await c.post("/stock/movements", json={**body, "movement_type": "opening_stock"}, headers=env["h"]["storekeeper"])
        assert r.status_code == 403
        r = await c.post("/stock/movements", json={**body, "movement_type": "opening_stock"}, headers=env["h"]["manager"])
        assert r.status_code == 200, r.text
        r = await c.post("/stock/movements", json={**body, "movement_type": "adjustment_in"}, headers=env["h"]["storekeeper"])
        assert r.status_code == 200, r.text
        # Not into a warehouse the storekeeper doesn't work in.
        r = await c.post("/stock/movements", json={**body, "warehouse_id": str(env["b"]), "movement_type": "adjustment_in"},
                         headers=env["h"]["storekeeper"])
        assert r.status_code == 403
    assert await _balance(env, env["product"], env["a"]) == D("16")  # 10 + 3 opening + 3 adjustment


async def test_opening_stock_after_the_ledger_opening_is_posted_to_opening_equity():
    env = await _env(accounting=True)
    current_tenant_id.set(env["tenant_id"])
    from app.activities.general.modules.accounting.services import posting
    from app.activities.general.modules.accounting.services.chart import account_by_role

    mv = await _move(env, MovementType.opening_stock, 2, unit_cost=D("60"))
    assert await _scalar(env, "SELECT count(*) FROM acc_entries WHERE source_id = :id", id=mv.id) == 0
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        _, sid = await posting.active_source(s, env["tenant_id"], "opening", "opening", "opening")
        inv, eq = (await account_by_role(s, env["tenant_id"], "inventory")).id, (await account_by_role(s, env["tenant_id"], "opening_equity")).id
        await posting.post(s, env["tenant_id"], "opening", sid, "opening", posting.today(),
                           [posting.dr(inv, D("720")), posting.cr(eq, D("720"))])
        await s.commit()
    mv = await _move(env, MovementType.opening_stock, 5, unit_cost=D("60"))
    rows = (await _scalar(env, """
        SELECT json_agg(json_build_array(a.role, l.debit, l.credit)) FROM acc_lines l
        JOIN acc_entries e ON e.id = l.entry_id JOIN acc_accounts a ON a.id = l.account_id
        WHERE e.source_type = 'stock_movement' AND e.source_id = :id""", id=mv.id))
    assert sorted(rows) == sorted([["inventory", 300.0, 0.0], ["opening_equity", 0.0, 300.0]])


# ── INV-3 ────────────────────────────────────────────────────────────────────────────────────────

async def test_reset_refuses_posted_or_document_movements_and_rebuilds_the_average():
    env = await _env()
    await _move(env, MovementType.opening_stock, 10, warehouse=env["b"], unit_cost=D("100"))
    assert D(str(await _scalar(env, "SELECT avg_cost FROM products WHERE id = :p", p=env["product"]))) == D("80")
    async with _client() as c:
        r = await c.delete("/stock/movements", params={"warehouse_id": str(env["b"])}, headers=env["h"]["manager"])
        assert r.status_code == 204, r.text
    # Back to the stock of A only: the average is A's again, not the one including B's deleted units.
    assert D(str(await _scalar(env, "SELECT avg_cost FROM products WHERE id = :p", p=env["product"]))) == D("60")

    # A transfer's other half is elsewhere: no reset.
    async with _client() as c:
        r = await c.post("/stock/transfer", json={"product_id": str(env["product"]), "from_warehouse_id": str(env["a"]),
                                                  "to_warehouse_id": str(env["b"]), "qty": "2"}, headers=env["h"]["manager"])
        assert r.status_code == 200, r.text
        r = await c.delete("/stock/movements", params={"warehouse_id": str(env["b"])}, headers=env["h"]["manager"])
        assert r.status_code == 409


async def test_reset_refuses_movements_in_the_ledger():
    env = await _env(accounting=True)
    await _move(env, MovementType.adjustment_in, 1, warehouse=env["b"], unit_cost=D("60"))  # posted: Dr inventory
    async with _client() as c:
        r = await c.delete("/stock/movements", params={"warehouse_id": str(env["b"])}, headers=env["h"]["manager"])
    assert r.status_code == 409 and "الدفاتر" in r.json()["detail"]
    assert await _scalar(env, "SELECT count(*) FROM stock_movements WHERE warehouse_id = :w", w=env["b"]) == 1


# ── INV-5, INV-6, INV-7 ──────────────────────────────────────────────────────────────────────────

async def test_transfers_need_two_warehouses_the_user_works_in_and_are_audited():
    env = await _env()
    body = {"product_id": str(env["product"]), "from_warehouse_id": str(env["a"]), "to_warehouse_id": str(env["a"]), "qty": "1"}
    async with _client() as c:
        r = await c.post("/stock/transfer", json=body, headers=env["h"]["manager"])
        assert r.status_code == 400 and "نفسه" in r.json()["detail"]
        r = await c.post("/stock/transfer", json={**body, "to_warehouse_id": str(env["b"])}, headers=env["h"]["storekeeper"])
        assert r.status_code == 403
        r = await c.post("/stock/transfer", json={**body, "to_warehouse_id": str(env["b"]), "qty": "50"}, headers=env["h"]["manager"])
        assert r.status_code == 400 and "الرصيد غير كافٍ" in r.json()["detail"]
        r = await c.post("/stock/transfer", json={**body, "to_warehouse_id": str(env["b"]), "qty": "4"}, headers=env["h"]["manager"])
        assert r.status_code == 200, r.text
    assert await _balance(env, env["product"], env["a"]) == D("6")
    assert await _balance(env, env["product"], env["b"]) == D("4")
    assert await _scalar(env, "SELECT count(*) FROM audit_log WHERE entity_type = 'stock' AND action = 'transfer'") == 1


async def test_a_warehouse_holding_stock_is_not_deactivated():
    env = await _env()
    async with _client() as c:
        r = await c.put(f"/stock/warehouses/{env['a']}", json={"is_active": False}, headers=env["h"]["manager"])
        assert r.status_code == 409, r.text
        r = await c.put(f"/stock/warehouses/{env['b']}", json={"is_active": False}, headers=env["h"]["manager"])
        assert r.status_code == 200, r.text
        r = await c.put(f"/stock/warehouses/{env['a']}", json={"code": f"B-{env['tenant_id'].hex[:4]}"}, headers=env["h"]["manager"])
        assert r.status_code == 409  # the code is taken
    assert await _scalar(env, "SELECT is_active FROM warehouses WHERE id = :w", w=env["a"]) is True


async def test_valuation_is_at_average_cost():
    env = await _env()
    await _move(env, MovementType.adjustment_in, 10, unit_cost=D("100"))  # average (10×60 + 10×100) / 20 = 80
    await _scalar(env, "UPDATE products SET cost_price = 999 WHERE id = :p RETURNING id", p=env["product"])
    async with _client() as c:
        r = await c.get("/stock/valuation", params={"warehouse_id": str(env["a"])}, headers=env["h"]["manager"])
    assert r.status_code == 200 and D(str(r.json()["total_cost_value"])) == D("1600")


# ── OPS ──────────────────────────────────────────────────────────────────────────────────────────

async def test_goods_receipt_without_a_purchase_is_gone_and_operations_check_branches():
    env = await _env()
    item = [{"product_id": str(env["product"]), "qty": "2", "unit_cost": "70", "note": None}]
    async with _client() as c:
        r = await c.post("/operations/goods-receipt", json={"warehouse_id": str(env["a"]), "items": item},
                         headers=env["h"]["manager"])
        assert r.status_code == 410 and "المشتريات" in r.json()["detail"]
        r = await c.post("/operations/dispatch", json={"from_warehouse_id": str(env["a"]), "to_warehouse_id": str(env["b"]),
                                                       "items": item}, headers=env["h"]["storekeeper"])
        assert r.status_code == 403
        r = await c.post("/operations/stock-request", json={"from_warehouse_id": str(env["a"]), "to_warehouse_id": str(env["b"]),
                                                            "items": item}, headers=env["h"]["storekeeper"])
        assert r.status_code == 403
        r = await c.post("/operations/dispatch", json={"from_warehouse_id": str(env["a"]), "to_warehouse_id": str(env["b"]),
                                                       "items": item, "notes": None}, headers=env["h"]["manager"])
        assert r.status_code == 200, r.text
        r = await c.get("/operations/", headers=env["h"]["accountant"])
        assert r.status_code == 403
    assert await _balance(env, env["product"], env["a"]) == D("8")
