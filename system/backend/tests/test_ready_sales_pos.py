"""Sales and POS ready for production, Phase A (PRODUCTION_READINESS: SAL-1..9, POS-1..3, PLAT-6).

Each test failed on the code before this change:
- SAL-1: the client decided the price, the discount and whether stock could go below zero
  (`allow_negative_stock`, `is_offline_sync`, `local_id`).
- SAL-2: a sale sent twice by the offline queue was recorded twice; the key lived in the notes.
- SAL-3: a sale went into a closed shift, another branch's shift, or none (cash in no drawer).
- SAL-4/PLAT-6: numbers came from one sequence for every workspace; drafts burnt invoice numbers.
- SAL-5: audit rows written after the service's commit were lost; cancel, partial return and
  quotation edits wrote none.
- SAL-6: sales were readable with a sign-in only, from every branch.
- SAL-7: a cashier could cancel; a return could be refunded from another cashier's shift.
- SAL-8/POS-7: a customer's balance was clamped at zero.
- SAL-9: bad dates and unknown ids were 500s.
- POS-1: any drawer row type by hand (sale, return, revenue delivery).
- POS-2: revenue delivery wrote the safe by raw SQL, unchecked and uncapped.
- POS-3: nothing in the database stopped a second open shift.
"""
import asyncio
import json
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app
from app.activities.general.modules.contacts.models.party import Customer
from app.activities.general.modules.finance.models.payment_wallet import PaymentWallet
from app.activities.general.modules.finance.models.safe import Safe
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement
from app.activities.general.modules.pos import service as pos_service
from app.activities.general.modules.pos.models import DrawerTxType, Shift
from app.activities.general.modules.sales.schemas import SaleItemCreate
from app.core.exceptions import BusinessError
from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password
from app.platform.permissions.roles import standard_permissions
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from app.platform.tenancy.models import Tenant

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")

PASSWORD = "Pass123!"


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _grant(s, user_id, tid, role: str) -> None:
    """The user acts as a workspace role holding exactly what the standard role holds in this
    code (the shared test database's standard rows may be synced by another branch's code)."""
    rid = uuid.uuid4()
    await s.execute(text("INSERT INTO sys_roles (id, tenant_id, code, name, name_en, is_system, is_clinical, grants) "
                         "VALUES (:id, :t, :c, :c, :c, false, false, CAST(:g AS jsonb))"),
                    {"id": rid, "t": tid, "c": f"{role}-{uuid.uuid4().hex[:8]}", "g": json.dumps(standard_permissions(role))})
    await s.execute(text("INSERT INTO user_role_assignments (id, user_id, role_id, is_active, tenant_id) "
                         "VALUES (gen_random_uuid(), :u, :r, true, :t)"), {"u": user_id, "r": rid, "t": tid})
    await s.execute(text("UPDATE users SET active_role_id = :r WHERE id = :u"), {"r": rid, "u": user_id})


def _headers(user_id, tid) -> dict:
    token = create_access_token({"sub": str(user_id), "tid": str(tid)})
    return {"Authorization": f"Bearer {token}"}


async def _env(stock: Decimal = Decimal("50")) -> dict:
    """A workspace with two branches; a cashier (assigned to both) with an open shift in the
    first, a second cashier with an open shift there too, a manager (no shift), a tracked product
    (retail 100, wholesale 85) with `stock` units, a customer, a wallet and a safe."""
    tid = uuid.uuid4()
    current_tenant_id.set(None)
    ids = {k: uuid.uuid4() for k in ("wh", "wh2", "wh3", "cashier", "cashier2", "manager", "product",
                                      "customer", "wallet", "safe", "shift", "shift2")}
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=tid, name=f"Ready {tid.hex[:6]}", slug=f"ready-{tid.hex[:10]}", status="active",
                     plan="enterprise", active_modules=["sales", "pos", "inventory", "finance", "contacts"]))
        await s.flush()
        s.add_all([
            Warehouse(id=ids["wh"], tenant_id=tid, code=f"W1-{tid.hex[:4]}", name="الفرع الأول", is_active=True),
            Warehouse(id=ids["wh2"], tenant_id=tid, code=f"W2-{tid.hex[:4]}", name="الفرع الثاني", is_active=True),
            Warehouse(id=ids["wh3"], tenant_id=tid, code=f"W3-{tid.hex[:4]}", name="فرع بعيد", is_active=True),
        ])
        for key, role, manager in (("cashier", "cashier", False), ("cashier2", "cashier", False),
                                   ("manager", "manager", True)):
            s.add(User(id=ids[key], tenant_id=tid, username=f"{key}_{tid.hex[:8]}", full_name=key, role=role,
                       password_hash=hash_password(PASSWORD), is_active=True, is_manager=manager))
        s.add_all([
            Product(id=ids["product"], tenant_id=tid, name="صنف", code=f"P-{tid.hex[:6]}", retail_price=Decimal("100"),
                    wholesale_price=Decimal("85"), cost_price=Decimal("60"), stock_status="tracked", is_active=True),
            Customer(id=ids["customer"], tenant_id=tid, name="عميل", balance=Decimal("0")),
            PaymentWallet(id=ids["wallet"], tenant_id=tid, name="محفظة", type="vodafone", balance=Decimal("0"),
                          is_active=True),
            Safe(id=ids["safe"], tenant_id=tid, name="الخزنة", balance=Decimal("0"), is_active=True),
        ])
        await s.flush()
        s.add_all([
            Shift(id=ids["shift"], tenant_id=tid, cashier_id=ids["cashier"], warehouse_id=ids["wh"], status="open",
                  initial_amount=Decimal("1000"), started_at=datetime.now(UTC)),
            Shift(id=ids["shift2"], tenant_id=tid, cashier_id=ids["cashier2"], warehouse_id=ids["wh"], status="open",
                  initial_amount=Decimal("500"), started_at=datetime.now(UTC)),
        ])
        await s.commit()
    current_tenant_id.set(tid)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, tid)
        for key in ("cashier", "cashier2"):
            for wh in ("wh", "wh2"):
                await s.execute(text("INSERT INTO user_warehouses (user_id, warehouse_id) VALUES (:u, :w)"),
                                {"u": ids[key], "w": ids[wh]})
        for key, role in (("cashier", "cashier"), ("cashier2", "cashier"), ("manager", "manager")):
            await _grant(s, ids[key], tid, role)
        await apply_movement(s, product_id=ids["product"], warehouse_id=ids["wh"],
                             movement_type=MovementType.opening_stock, qty=stock, unit_cost=Decimal("60"),
                             created_by=ids["manager"])
        # The second branch sells too: a tracked product is checked in every branch (inventory INV-1).
        await apply_movement(s, product_id=ids["product"], warehouse_id=ids["wh2"],
                             movement_type=MovementType.opening_stock, qty=Decimal("50"), unit_cost=Decimal("60"),
                             created_by=ids["manager"])
        await s.commit()
    current_tenant_id.set(None)
    env = {"tid": tid, **ids}
    env["h"] = {k: _headers(ids[k], tid) for k in ("cashier", "cashier2", "manager")}
    return env


async def _sql(env, sql: str, **params):
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tid"])
        res = await s.execute(text(sql), params)
        out = res.all() if res.returns_rows else []
        await s.commit()
    current_tenant_id.set(None)
    return out


async def _setting(env, module: str, **values) -> None:
    await _sql(env, "INSERT INTO store_settings (id, tenant_id, key, value) VALUES (:i, :t, :k, :v) "
                    "ON CONFLICT (tenant_id, key) DO UPDATE SET value = EXCLUDED.value",
               i=uuid.uuid4(), t=env["tid"], k=f"mod_settings_{module}", v=json.dumps(values))


def _body(env, qty=1, price="100", **kw) -> dict:
    return {"warehouse_id": str(env["wh"]),
            "items": [{"product_id": str(env["product"]), "qty": str(qty), "unit_price": str(price)}], **kw}


# ── SAL-1 ─────────────────────────────────────────────────────────────────────────────────────

async def test_price_and_discount_are_decided_on_the_server():
    env = await _env()
    async with _client() as c:
        cheap = await c.post("/sales", json=_body(env, price="1"), headers=env["h"]["cashier"])
        assert cheap.status_code == 400, cheap.text
        assert (await c.post("/sales", json=_body(env, price="-5"), headers=env["h"]["cashier"])).status_code == 422
        over = await c.post("/sales", json=_body(env, discount_amount="500"), headers=env["h"]["cashier"])
        assert over.status_code == 400 and "الخصم" in over.json()["detail"]
        # Wholesale sells at the wholesale price.
        wholesale = await c.post("/sales", json=_body(env, price="85", sale_mode="wholesale"), headers=env["h"]["cashier"])
        assert wholesale.status_code == 200, wholesale.text

        # Another price needs the setting AND the permission (managers).
        await _setting(env, "pos", allow_price_override=True)
        assert (await c.post("/sales", json=_body(env, price="90"), headers=env["h"]["cashier"])).status_code == 400
        opened = await c.post("/shifts/open", json={"warehouse_id": str(env["wh"]), "initial_amount": "0"},
                              headers=env["h"]["manager"])
        assert opened.status_code == 200, opened.text
        ok = await c.post("/sales", json=_body(env, price="90"), headers=env["h"]["manager"])
        assert ok.status_code == 200, ok.text
        assert Decimal(ok.json()["net_total"]) == Decimal("90")
        await _setting(env, "pos", allow_price_override=False)
        assert (await c.post("/sales", json=_body(env, price="90"), headers=env["h"]["manager"])).status_code == 400

        # Discounts follow allow_manual_discount.
        await _setting(env, "sales", allow_manual_discount=False)
        assert (await c.post("/sales", json=_body(env, discount_amount="5"), headers=env["h"]["cashier"])).status_code == 400


async def test_client_flags_dont_sell_below_stock():
    env = await _env(stock=Decimal("5"))
    flags = {"allow_negative_stock": True, "is_offline_sync": True, "local_id": str(uuid.uuid4())}
    async with _client() as c:
        r = await c.post("/sales", json=_body(env, qty=6, **flags), headers=env["h"]["cashier"])
        assert r.status_code == 400 and "المخزون غير كافي" in r.json()["detail"], r.text
        # A manager may (sales:negative_stock); the shortage is in the audit log.
        await c.post("/shifts/open", json={"warehouse_id": str(env["wh"]), "initial_amount": "0"}, headers=env["h"]["manager"])
        m = await c.post("/sales", json=_body(env, qty=6), headers=env["h"]["manager"])
        assert m.status_code == 200, m.text
        # A workspace that doesn't prevent it lets everyone.
        await _setting(env, "inventory", prevent_negative_stock=False)
        assert (await c.post("/sales", json=_body(env, qty=2), headers=env["h"]["cashier"])).status_code == 200
    rows = await _sql(env, "SELECT 1 FROM audit_log WHERE action = 'inventory_discrepancy' AND entity_id = :p", p=env["product"])
    assert len(rows) == 2


# ── SAL-2 ─────────────────────────────────────────────────────────────────────────────────────

async def test_the_same_local_id_records_one_sale():
    env = await _env()
    lid = str(uuid.uuid4())
    async with _client() as c:
        first, second = await asyncio.gather(
            c.post("/sales", json=_body(env, local_id=lid, notes="ملاحظة"), headers=env["h"]["cashier"]),
            c.post("/sales", json=_body(env, local_id=lid, notes="ملاحظة"), headers=env["h"]["cashier"]))
        assert first.status_code == 200 and second.status_code == 200, (first.text, second.text)
        assert first.json()["id"] == second.json()["id"]
        again = await c.post("/sales", json=_body(env, local_id=lid, notes="ملاحظة"), headers=env["h"]["cashier"])
        assert again.json()["id"] == first.json()["id"]
        assert (await c.post("/sales", json=_body(env, local_id="not-a-uuid"), headers=env["h"]["cashier"])).status_code == 422
    rows = await _sql(env, "SELECT id, notes FROM sales WHERE local_id = :l", l=uuid.UUID(lid))
    assert len(rows) == 1 and rows[0].notes == "ملاحظة"  # the key is its own column, not in the notes
    assert len(await _sql(env, "SELECT 1 FROM drawer_transactions WHERE ref_id = :s", s=rows[0].id)) == 1


# ── SAL-3 ─────────────────────────────────────────────────────────────────────────────────────

async def test_sales_go_into_the_users_open_shift_in_their_branch():
    env = await _env()
    h = env["h"]["cashier"]
    async with _client() as c:
        # No shift_id: the cashier's open shift in the branch.
        r = await c.post("/sales", json=_body(env), headers=h)
        assert r.status_code == 200 and r.json()["shift_id"] == str(env["shift"])
        # Cash in a branch where the cashier has no open shift.
        r = await c.post("/sales", json={**_body(env), "warehouse_id": str(env["wh2"])}, headers=h)
        assert r.status_code == 400 and "وردية" in r.json()["detail"], r.text
        # Their shift named for another branch's sale.
        r = await c.post("/sales", json={**_body(env), "warehouse_id": str(env["wh2"]), "shift_id": str(env["shift"])},
                         headers=h)
        assert r.status_code == 400
        # Someone else's shift.
        assert (await c.post("/sales", json=_body(env, shift_id=str(env["shift2"])), headers=h)).status_code == 400
        # A wallet sale without a shift: refused while require_active_shift is on (the default).
        wallet_sale = {**_body(env), "warehouse_id": str(env["wh2"]), "payment_method": "wallet",
                       "wallet_id": str(env["wallet"])}
        assert (await c.post("/sales", json=wallet_sale, headers=h)).status_code == 400
        await _setting(env, "pos", require_active_shift=False)
        r = await c.post("/sales", json=wallet_sale, headers=h)
        assert r.status_code == 200 and r.json()["shift_id"] is None, r.text
        # A branch the cashier isn't assigned to.
        assert (await c.post("/sales", json={**_body(env), "warehouse_id": str(env["wh3"])}, headers=h)).status_code == 403
    # A closed shift takes no more sales.
    await _sql(env, "UPDATE shifts SET status = 'closed' WHERE id = :id", id=env["shift"])
    async with _client() as c:
        r = await c.post("/sales", json=_body(env, shift_id=str(env["shift"])), headers=h)
        assert r.status_code == 400 and "مغلقة" in r.json()["detail"]


# ── SAL-4 / PLAT-6 ────────────────────────────────────────────────────────────────────────────

async def test_numbers_count_per_workspace_and_drafts_take_no_invoice_number():
    a, b = await _env(), await _env()
    async with _client() as c:
        s1 = (await c.post("/sales", json=_body(a), headers=a["h"]["cashier"])).json()
        draft = (await c.post("/sales/draft", json=_body(a), headers=a["h"]["cashier"])).json()
        confirmed = (await c.put(f"/sales/{draft['id']}/confirm", headers=a["h"]["cashier"])).json()
        ret = (await c.post(f"/sales/{s1['id']}/return", headers=a["h"]["cashier"])).json()
        other = (await c.post("/sales", json=_body(b), headers=b["h"]["cashier"])).json()
    assert s1["invoice_number"] == "INV-000001"
    assert draft["invoice_number"] == "DRF-000001"
    assert confirmed["invoice_number"] == "INV-000002"  # no number lost to the draft
    assert ret["doc_number"] == "RET-000001"
    assert other["invoice_number"] == "INV-000001"  # the other workspace counts on its own


async def test_a_workspace_counter_starts_after_numbers_already_used():
    env = await _env()
    async with _client() as c:
        await c.post("/sales", json=_body(env), headers=env["h"]["cashier"])
    await _sql(env, "UPDATE sales SET invoice_number = 'INV-000500' WHERE tenant_id = :t", t=env["tid"])
    await _sql(env, "DELETE FROM doc_counters WHERE tenant_id = :t", t=env["tid"])
    async with _client() as c:
        nxt = (await c.post("/sales", json=_body(env), headers=env["h"]["cashier"])).json()
    assert nxt["invoice_number"] == "INV-000501"


# ── SAL-5 ─────────────────────────────────────────────────────────────────────────────────────

async def test_audit_rows_are_written_with_the_document():
    env = await _env()
    async with _client() as c:
        sale = (await c.post("/sales", json=_body(env, qty=3), headers=env["h"]["cashier"])).json()
        part = await c.post(f"/sales/{sale['id']}/partial-return",
                            json={"items": [{"product_id": str(env["product"]), "qty": "1"}]}, headers=env["h"]["cashier"])
        assert part.status_code == 200, part.text
        other = (await c.post("/sales", json=_body(env), headers=env["h"]["cashier"])).json()
        await c.post("/shifts/open", json={"warehouse_id": str(env["wh"]), "initial_amount": "0"}, headers=env["h"]["manager"])
        cancel = await c.put(f"/sales/{other['id']}/cancel", headers=env["h"]["manager"])
        assert cancel.status_code == 200, cancel.text
        q = (await c.post("/sales/quotations", json=_body(env), headers=env["h"]["cashier"])).json()
        assert (await c.put(f"/sales/{q['id']}", json={"notes": "تعديل"}, headers=env["h"]["cashier"])).status_code == 200
        assert (await c.delete(f"/sales/{q['id']}", headers=env["h"]["cashier"])).status_code == 204
    rows = {(r.entity_id, r.action) for r in await _sql(env, "SELECT entity_id, action FROM audit_log WHERE tenant_id = :t",
                                                        t=env["tid"])}
    sid, oid, qid = uuid.UUID(sale["id"]), uuid.UUID(other["id"]), uuid.UUID(q["id"])
    assert {(sid, "create"), (sid, "partial_return"), (oid, "cancel"), (qid, "create"), (qid, "update"),
            (qid, "delete")} <= rows


# ── SAL-6 / SAL-9 ─────────────────────────────────────────────────────────────────────────────

async def test_reads_need_a_permission_and_stay_in_the_users_branches():
    env = await _env()
    async with _client() as c:
        await c.post("/shifts/open", json={"warehouse_id": str(env["wh3"]), "initial_amount": "0"}, headers=env["h"]["manager"])
        far = (await c.post("/sales", json={**_body(env), "warehouse_id": str(env["wh3"])}, headers=env["h"]["manager"]))
        assert far.status_code == 200, far.text
        far = far.json()
        near = (await c.post("/sales", json=_body(env), headers=env["h"]["cashier"])).json()
        listed = {s["id"] for s in (await c.get("/sales", headers=env["h"]["cashier"])).json()}
        assert near["id"] in listed and far["id"] not in listed
        assert far["id"] in {s["id"] for s in (await c.get("/sales", headers=env["h"]["manager"])).json()}
        assert (await c.get(f"/sales/{far['id']}", headers=env["h"]["cashier"])).status_code == 403
        assert (await c.get(f"/sales/{uuid.uuid4()}", headers=env["h"]["cashier"])).status_code == 404
        # Typed filters: bad input is a 422, not a 500; the last day is included.
        assert (await c.get("/sales", params={"from_date": "yesterday"}, headers=env["h"]["manager"])).status_code == 422
        assert (await c.get("/sales", params={"status": "bogus"}, headers=env["h"]["manager"])).status_code == 422
        today = datetime.now().date().isoformat()
        r = await c.get("/sales", params={"from_date": today, "to_date": today}, headers=env["h"]["manager"])
        assert r.status_code == 200 and near["id"] in {s["id"] for s in r.json()}
        # Unknown ids are a 404 in Arabic, not an IntegrityError.
        r = await c.post("/sales", json=_body(env, customer_id=str(uuid.uuid4())), headers=env["h"]["cashier"])
        assert r.status_code == 404 and r.json()["detail"] == "العميل غير موجود"
        r = await c.post("/sales", json={**_body(env), "items": [{"product_id": str(uuid.uuid4()), "qty": "1",
                                                                   "unit_price": "1"}]}, headers=env["h"]["cashier"])
        assert r.status_code == 404
    # Signed in without a sales or POS permission.
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tid"])
        u = User(id=uuid.uuid4(), tenant_id=env["tid"], username=f"store_{uuid.uuid4().hex[:8]}", full_name="مخازن",
                 role="storekeeper", password_hash=hash_password(PASSWORD), is_active=True)
        s.add(u)
        await s.flush()
        await _grant(s, u.id, env["tid"], "storekeeper")
        await s.commit()
    current_tenant_id.set(None)
    async with _client() as c:
        hs = _headers(u.id, env["tid"])
        assert (await c.get("/sales", headers=hs)).status_code == 403
        assert (await c.get("/sales/drafts", headers=hs)).status_code == 403


# ── SAL-7 ─────────────────────────────────────────────────────────────────────────────────────

async def test_cancel_is_a_managers_and_refunds_come_from_ones_own_shift():
    env = await _env()
    async with _client() as c:
        sale = (await c.post("/sales", json=_body(env, qty=2), headers=env["h"]["cashier"])).json()
        assert (await c.put(f"/sales/{sale['id']}/cancel", headers=env["h"]["cashier"])).status_code == 403
        # A manager without an open shift can't refund cash, nor out of the cashier's shift.
        r = await c.post(f"/sales/{sale['id']}/partial-return",
                         json={"items": [{"product_id": str(env["product"]), "qty": "1"}], "shift_id": str(env["shift"])},
                         headers=env["h"]["manager"])
        assert r.status_code == 400, r.text
        r = await c.post(f"/sales/{sale['id']}/return", headers=env["h"]["manager"])
        assert r.status_code == 400 and "وردية" in r.json()["detail"]
        # Another cashier refunds from their own shift, never from the seller's.
        r = await c.post(f"/sales/{sale['id']}/partial-return",
                         json={"items": [{"product_id": str(env["product"]), "qty": "1"}]}, headers=env["h"]["cashier2"])
        assert r.status_code == 200, r.text
    rows = await _sql(env, "SELECT shift_id FROM drawer_transactions WHERE type = 'return_' AND ref_id = :r",
                      r=uuid.UUID(r.json()["sale_id"]))
    assert [x.shift_id for x in rows] == [env["shift2"]]


# ── SAL-8 / POS-7 ─────────────────────────────────────────────────────────────────────────────

async def test_customer_balances_are_never_clamped_at_zero():
    env = await _env()
    async with _client() as c:
        credit = (await c.post("/sales", json=_body(env, is_credit=True, customer_id=str(env["customer"]),
                                                    payment_method="credit"), headers=env["h"]["cashier"])).json()
        # The customer pays 150 on a debt of 100 at the drawer: we owe them 50.
        r = await c.post(f"/shifts/{env['shift']}/transactions",
                         json={"type": "deposit", "amount": "150", "customer_id": str(env["customer"])},
                         headers=env["h"]["cashier"])
        assert r.status_code == 200, r.text
        assert (await _sql(env, "SELECT balance FROM customers WHERE id = :c", c=env["customer"]))[0].balance == Decimal("-50")
        # Returning the credit sale takes its 100 off as well.
        assert (await c.post(f"/sales/{credit['id']}/return", headers=env["h"]["cashier"])).status_code == 200
    assert (await _sql(env, "SELECT balance FROM customers WHERE id = :c", c=env["customer"]))[0].balance == Decimal("-150")


# ── POS-1 ─────────────────────────────────────────────────────────────────────────────────────

async def test_drawer_rows_by_hand_are_deposits_expenses_or_withdrawals():
    env = await _env()
    url = f"/shifts/{env['shift']}/transactions"
    async with _client() as c:
        for kind in ("sale", "return", "revenue_delivery"):
            assert (await c.post(url, json={"type": kind, "amount": "10"}, headers=env["h"]["cashier"])).status_code == 422
        bad = {"type": "expense", "amount": "10", "payment_method": "bitcoin"}
        assert (await c.post(url, json=bad, headers=env["h"]["cashier"])).status_code == 422
        r = await c.post(url, json={"type": "expense", "amount": "10", "payment_method": "wallet",
                                    "wallet_id": str(uuid.uuid4())}, headers=env["h"]["cashier"])
        assert r.status_code == 404, r.text
        r = await c.post(url, json={"type": "expense", "amount": "10", "category_id": str(uuid.uuid4())},
                         headers=env["h"]["cashier"])
        assert r.status_code == 404, r.text
        ok = await c.post(url, json={"type": "expense", "amount": "10"}, headers=env["h"]["cashier"])
        assert ok.status_code == 200
    current_tenant_id.set(env["tid"])
    async with AsyncSessionLocal() as s:
        with pytest.raises(BusinessError):
            await pos_service.add_transaction(s, env["shift"], DrawerTxType.return_, Decimal("10"), env["cashier"])


# ── POS-2 ─────────────────────────────────────────────────────────────────────────────────────

async def test_revenue_delivery_goes_through_the_safe_and_is_capped_at_the_drawer():
    env = await _env()
    url = f"/shifts/{env['shift']}/revenue-delivery"
    auth = {"manager_id": str(env["manager"]), "manager_password": PASSWORD}
    async with _client() as c:
        r = await c.post(url, json={"amount": "1500", "safe_id": str(env["safe"]), **auth}, headers=env["h"]["cashier"])
        assert r.status_code == 400 and "النقدية المتوقعة" in r.json()["detail"], r.text
        r = await c.post(url, json={"amount": "100", "safe_id": str(uuid.uuid4()), **auth}, headers=env["h"]["cashier"])
        assert r.status_code == 404
        # Another cashier can't hand over this drawer.
        r = await c.post(url, json={"amount": "100", "safe_id": str(env["safe"]), **auth}, headers=env["h"]["cashier2"])
        assert r.status_code == 403
        await _sql(env, "UPDATE safes SET is_active = false WHERE id = :s", s=env["safe"])
        r = await c.post(url, json={"amount": "100", "safe_id": str(env["safe"]), **auth}, headers=env["h"]["cashier"])
        assert r.status_code == 400
        await _sql(env, "UPDATE safes SET is_active = true WHERE id = :s", s=env["safe"])
        r = await c.post(url, json={"amount": "400", "safe_id": str(env["safe"]), **auth}, headers=env["h"]["cashier"])
        assert r.status_code == 200, r.text
        assert r.json()["doc_number"] == "DEP-000001"
        summary = (await c.get(f"/shifts/{env['shift']}/summary", headers=env["h"]["cashier"])).json()
    assert Decimal(summary["expected_balance"]) == Decimal("600")
    safe = (await _sql(env, "SELECT balance FROM safes WHERE id = :s", s=env["safe"]))[0]
    assert safe.balance == Decimal("400")
    tx = await _sql(env, "SELECT tx_type, amount, balance_after FROM safe_transactions WHERE safe_id = :s", s=env["safe"])
    assert [(t.tx_type, t.amount, t.balance_after) for t in tx] == [("deposit", Decimal("400"), Decimal("400"))]
    dep = await _sql(env, "SELECT doc_number, shift_id FROM safe_deposits WHERE safe_id = :s", s=env["safe"])
    assert [(d.doc_number, d.shift_id) for d in dep] == [("DEP-000001", env["shift"])]


# ── POS-3 ─────────────────────────────────────────────────────────────────────────────────────

async def test_only_one_open_shift_per_cashier_and_branch():
    env = await _env()
    body = {"warehouse_id": str(env["wh2"]), "initial_amount": "0"}
    async with _client() as c:
        a, b = await asyncio.gather(c.post("/shifts/open", json=body, headers=env["h"]["cashier"]),
                                    c.post("/shifts/open", json=body, headers=env["h"]["cashier"]))
        assert sorted([a.status_code, b.status_code]) == [200, 400], (a.text, b.text)
        r = await c.post("/shifts/open", json={**body, "warehouse_id": str(env["wh3"])}, headers=env["h"]["cashier"])
        assert r.status_code == 403
        r = await c.post("/shifts/open", json={"warehouse_id": str(env["wh"]), "initial_amount": "0",
                                               "supervisor_id": str(uuid.uuid4())}, headers=env["h"]["manager"])
        assert r.status_code == 404
    # The database itself refuses a second open shift.
    with pytest.raises(Exception, match="uq_shifts_open_cashier_warehouse"):
        await _sql(env, "INSERT INTO shifts (id, tenant_id, cashier_id, warehouse_id, status, initial_amount) "
                        "VALUES (:i, :t, :c, :w, 'open', 0)", i=uuid.uuid4(), t=env["tid"], c=env["cashier"], w=env["wh"])
    current_tenant_id.set(None)


def test_sale_lines_are_bounded():
    from pydantic import ValidationError

    pid = uuid.uuid4()
    for bad in ({"unit_price": "-1"}, {"unit_price": "1", "discount": "-1"}, {"unit_price": "10", "discount": "11"},
                {"unit_price": "1e12"}):
        with pytest.raises(ValidationError):
            SaleItemCreate(product_id=pid, qty=Decimal("1"), **bad)
