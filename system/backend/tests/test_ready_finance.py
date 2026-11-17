"""Finance, production readiness (PRODUCTION_READINESS.md, finance).

FIN-2  safes and wallets are created, edited and stopped; a new workspace has a main safe.
FIN-3  the periods list runs from the first activity to now; months close in order.
FIN-4  /reports/ledger totals cover the whole range, payments are not multiplied by lines.
FIN-5  /wallets/summary counts invoices and takes the discount once.
FIN-6  /expenses and /expenses/summary take typed dates and ids (422, never 500).
FIN-7  a withdrawal needs `finance` and the manager flag.
FIN-8  money reads need `finance`/`reports`; branch-limited users see their branches only.
FIN-10 a manual deposit names no shift; unknown references are 404.
FIN-11 deposit, withdraw, wallet→safe and wallet reset are idempotent.
FIN-12 partial updates, 404 for unknown ids, the category type is an enum.
Workspace isolation: another workspace's safe or receipt is a 404.
"""
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app
from app.activities.general.modules.sales.schemas import SaleCreate, SaleItemCreate, SplitPaymentItem
from app.activities.general.modules.sales.services import sales as sales_service
from app.db.base import AsyncSessionLocal
from app.models.registry import load_all_models
from app.platform.auth.models.user import User, user_warehouses
from app.platform.auth.security import create_access_token, hash_password
from app.platform.permissions.roles import standard_permissions
from app.platform.tenancy.context import bind_tenant, current_tenant_id, install_tenancy_events
from tests.conftest import give_roles
from tests.test_accounting_ledger import _env

load_all_models()
install_tenancy_events()

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

D = Decimal


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _ws(accounting: bool = False) -> dict:
    """The ledger tests' workspace (a branch, an open shift, a customer, a wallet, a safe of 1000, a
    product), a second branch, and users with headers: admin (manager), accountant (finance: every branch, though assigned to the
    first), boss (manager flag without finance), cashier (customers), doctor (reports without finance,
    limited to the first branch)."""
    env = await _env(accounting)
    t = env["tenant_id"]
    wh2 = uuid.uuid4()
    current_tenant_id.set(None)
    users = {}
    async with AsyncSessionLocal() as s:
        await s.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        await s.execute(text("INSERT INTO warehouses (id, tenant_id, code, name, is_active) VALUES (:id, :t, :c, 'فرع ٢', true)"),
                        {"id": wh2, "t": t, "c": f"W2-{t.hex[:6]}"})
        for name, role, manager in (("admin", "admin", True), ("accountant", "accountant", False),
                                    ("boss", "cashier", True), ("cashier", "cashier", False),
                                    ("doctor", "doctor", False)):
            u = User(id=uuid.uuid4(), tenant_id=t, username=f"{name}_{t.hex[:8]}", full_name=name, role=role,
                     password_hash=hash_password("Pass12345!"), permissions=standard_permissions(role),
                     is_active=True, is_manager=manager)
            s.add(u)
            users[name] = u
        await give_roles(s)
        await s.execute(user_warehouses.insert().values(user_id=users["accountant"].id, warehouse_id=env["warehouse_id"]))
        await s.execute(user_warehouses.insert().values(user_id=users["doctor"].id, warehouse_id=env["warehouse_id"]))
        await s.commit()
    current_tenant_id.set(t)
    env["warehouse2_id"] = wh2
    env["users"] = {k: u.id for k, u in users.items()}
    env["h"] = {k: {"Authorization": "Bearer " + create_access_token(
        {"sub": str(u.id), "role": u.role, "username": u.username, "tid": str(t)})} for k, u in users.items()}
    return env


async def _sql(env: dict, sql: str, **params):
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        result = await s.execute(text(sql), params)
        rows = result.all() if result.returns_rows else None
        await s.commit()
        return rows


async def _one(env: dict, sql: str, **params):
    return (await _sql(env, sql, **params))[0][0]


async def _sale(env: dict, **kw):
    current_tenant_id.set(env["tenant_id"])
    items = kw.pop("items", None) or [SaleItemCreate(product_id=env["product_id"], qty=D("1"), unit_price=D("100"))]
    async with AsyncSessionLocal() as s:
        return await sales_service.create_sale(
            s, SaleCreate(warehouse_id=env["warehouse_id"], shift_id=env["shift_id"], items=items, **kw), env["cashier_id"])


def _months_back(n: int) -> date:
    d = date.today().replace(day=15)
    for _ in range(n):
        d = (d.replace(day=1) - timedelta(days=1)).replace(day=15)
    return d


# ── FIN-2 ─────────────────────────────────────────────────────────────────────────────────────

async def test_a_new_workspace_has_a_main_safe_and_can_approve_an_expense():
    from app.activities.general.modules.finance.services import expenses
    from app.platform.tenancy.service import create_workspace

    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        tenant, admin = await create_workspace(s, name=f"Fresh {uuid.uuid4().hex[:6]}", sector="retail", scale="small",
                                               admin_username=f"fresh_{uuid.uuid4().hex[:8]}", admin_full_name="مدير",
                                               admin_password_hash=hash_password("Pass12345!"), demo_data=False)
        await s.commit()
        tid, uid = tenant.id, admin.id
    env = {"tenant_id": tid}
    safes = await _sql(env, "SELECT id, name, balance, is_active FROM safes")
    assert len(safes) == 1 and safes[0].name == "الخزينة الرئيسية" and safes[0].balance == 0 and safes[0].is_active
    safe_id = safes[0].id
    await _sql(env, "UPDATE safes SET balance = 100 WHERE id = :s", s=safe_id)
    eid = await _one(env, "INSERT INTO expenses (id, tenant_id, amount, description, status) VALUES (gen_random_uuid(), :t, 40, 'كهرباء', 'draft') RETURNING id",
                     t=tid)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, tid)
        user = await s.get(User, uid)
        row = await expenses.decide(s, eid, True, None, user, safe_id=safe_id)
        await s.commit()
    assert row["status"] == "approved"
    assert await _one(env, "SELECT balance FROM safes WHERE id = :s", s=safe_id) == D("60")


async def test_safes_and_wallets_are_created_edited_and_stopped():
    env = await _ws()
    h = env["h"]
    async with _client() as c:
        safe = (await c.post("/safes", json={"name": "خزنة الفرع", "location": "الدور الأول"}, headers=h["accountant"])).json()
        assert safe["balance"] == "0.00" or float(safe["balance"]) == 0
        # only the field sent changes
        r = await c.put(f"/safes/{safe['id']}", json={"location": "الدور الثاني"}, headers=h["accountant"])
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "خزنة الفرع" and r.json()["location"] == "الدور الثاني"
        assert (await c.put(f"/safes/{uuid.uuid4()}", json={"name": "x"}, headers=h["accountant"])).status_code == 404
        assert (await c.post("/safes", json={"name": "x"}, headers=h["cashier"])).status_code == 403

        # a safe holding money can't be stopped; an empty one can, and comes back
        full = await c.delete(f"/safes/{env['safe_id']}", headers=h["accountant"])
        assert full.status_code == 409 and "رصيد" in full.json()["detail"]
        stopped = await c.delete(f"/safes/{safe['id']}", headers=h["accountant"])
        assert stopped.status_code == 200 and stopped.json()["is_active"] is False
        listed = (await c.get("/safes", headers=h["accountant"])).json()
        assert safe["id"] not in {s["id"] for s in listed}
        everything = (await c.get("/safes", params={"include_inactive": True}, headers=h["accountant"])).json()
        assert safe["id"] in {s["id"] for s in everything}
        dep = await c.post(f"/safes/{safe['id']}/deposit", json={"amount": "5"}, headers=h["admin"])
        assert dep.status_code == 400 and "موقوفة" in dep.json()["detail"]
        assert (await c.post(f"/safes/{safe['id']}/activate", headers=h["accountant"])).json()["is_active"] is True

        # wallets: partial edit, stop only when empty, bring back
        w = await c.put(f"/wallets/{env['wallet_id']}", json={"phone": "01000000000"}, headers=h["accountant"])
        assert w.status_code == 200 and w.json()["name"] == "فودافون كاش" and w.json()["phone"] == "01000000000"
        assert (await c.put(f"/wallets/{uuid.uuid4()}", json={"phone": "1"}, headers=h["accountant"])).status_code == 404
        assert (await c.delete(f"/wallets/{env['wallet_id']}", headers=h["accountant"])).status_code == 204
        assert (await c.post(f"/wallets/{env['wallet_id']}/activate", headers=h["accountant"])).json()["is_active"] is True


# ── FIN-3 ─────────────────────────────────────────────────────────────────────────────────────

async def test_periods_run_from_the_first_activity_and_close_in_order():
    from app.activities.general.modules.finance.services.periods import current_month

    env = await _ws()
    h = env["h"]
    first = _months_back(3)
    await _sql(env, "INSERT INTO expenses (id, tenant_id, amount, description, status, date) "
                    "VALUES (gen_random_uuid(), :t, 10, 'قديم', 'approved', :d)", t=env["tenant_id"], d=first)
    async with _client() as c:
        rows = (await c.get("/periods", headers=h["accountant"])).json()
        months = [r["month"] for r in rows]
        assert months[0] == current_month() and months[-1] == first.strftime("%Y-%m") and len(months) == 4
        assert [r["month"] for r in rows if r["can_close"]] == [first.strftime("%Y-%m")]
        assert rows[0]["current"] and not rows[0]["can_close"]
        later = rows[1]["month"]
        out_of_order = await c.post(f"/periods/{later}/close", headers=h["accountant"])
        assert out_of_order.status_code == 400 and first.strftime("%Y-%m") in out_of_order.json()["detail"]
        assert (await c.post(f"/periods/{current_month()}/close", headers=h["accountant"])).status_code == 400
        assert (await c.post(f"/periods/{first.strftime('%Y-%m')}/close", headers=h["accountant"])).status_code == 200
        rows = (await c.get("/periods", headers=h["accountant"])).json()
        by = {r["month"]: r for r in rows}
        assert by[first.strftime("%Y-%m")]["status"] == "closed" and by[first.strftime("%Y-%m")]["can_reopen"]
        assert by[rows[-2]["month"]]["can_close"]
        assert (await c.get("/periods", headers=h["cashier"])).status_code == 403


# ── FIN-4, FIN-5 ──────────────────────────────────────────────────────────────────────────────

async def test_ledger_totals_cover_the_whole_range_and_payments_are_not_multiplied():
    env = await _ws()
    h = env["h"]
    two_lines = [SaleItemCreate(product_id=env["product_id"], qty=D("1"), unit_price=D("100")),
                 SaleItemCreate(product_id=env["product_id"], qty=D("2"), unit_price=D("50"))]
    # 200 of lines less 20 discount = 180: 100 cash + 80 wallet (two lines × two payments)
    await _sale(env, items=two_lines, discount_amount=D("20"),
                payments=[SplitPaymentItem(method="cash", amount=D("100")),
                          SplitPaymentItem(method="wallet", amount=D("80"), wallet_id=env["wallet_id"])])
    await _sale(env)
    await _sale(env)
    today = date.today().isoformat()
    async with _client() as c:
        r = await c.get("/reports/ledger", params={"from_date": today, "to_date": today, "page_size": 1}, headers=h["admin"])
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["sale_items"]) == 1 and body["pagination"]["sales"]["total"] == 4
        summary = body["summary"]
        assert summary["total_sales"] == 380.0
        assert (summary["cash_sales"], summary["wallet_sales"], summary["credit_sales"]) == (300.0, 80.0, 0.0)

        ws = (await c.get("/wallets/summary", params={"from_date": today, "to_date": today}, headers=h["admin"])).json()
        assert sum(r["invoice_count"] for r in ws) == 3
        assert sum(float(r["total"]) for r in ws) == 380.0

        assert (await c.get("/reports/ledger", params={"from_date": today, "to_date": today}, headers=h["cashier"])).status_code == 403
        assert (await c.get("/reports/ledger", params={"from_date": "x", "to_date": today}, headers=h["admin"])).status_code == 422
        # a branch-limited user can't read another branch
        other = await c.get("/wallets/summary", params={"warehouse_id": str(env["warehouse2_id"])}, headers=h["accountant"])
        assert other.status_code == 403


# ── FIN-6, FIN-8 ──────────────────────────────────────────────────────────────────────────────

async def test_expense_reads_are_typed_permissioned_and_branch_scoped():
    env = await _ws()
    h = env["h"]
    t = env["tenant_id"]
    for wh, label in ((env["warehouse_id"], "فرع ١"), (env["warehouse2_id"], "فرع ٢"), (None, "عام")):
        await _sql(env, "INSERT INTO expenses (id, tenant_id, amount, description, status, warehouse_id, date) "
                        "VALUES (gen_random_uuid(), :t, 10, :d, 'approved', :w, CURRENT_DATE)", t=t, d=label, w=wh)
    today = date.today().isoformat()
    async with _client() as c:
        r = await c.get("/expenses", params={"date_from": today, "date_to": today}, headers=h["admin"])
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 3
        assert (await c.get("/expenses", params={"vendor_id": "nope"}, headers=h["admin"])).status_code == 422
        assert (await c.get("/expenses", params={"date_from": "2026-13-01"}, headers=h["admin"])).status_code == 422
        assert (await c.get("/expenses", params={"status": "paid"}, headers=h["admin"])).status_code == 422
        s = await c.get("/expenses/summary", params={"date_from": today, "date_to": today}, headers=h["admin"])
        assert s.status_code == 200 and s.json()["count"] == 3
        # the accountant answers for the company's money: every branch, though assigned to the first
        mine = (await c.get("/expenses", headers=h["accountant"])).json()
        assert {e["description"] for e in mine["data"]} == {"فرع ١", "فرع ٢", "عام"}
        assert (await c.get("/expenses/summary", headers=h["accountant"])).json()["count"] == 3
        # someone with reports but not finance is limited to their branch (and the company-wide one)
        assert (await c.get("/expenses/summary", headers=h["doctor"])).json()["count"] == 2
        assert (await c.get("/expenses", headers=h["cashier"])).status_code == 403
        assert (await c.get("/expense-vendors", headers=h["cashier"])).status_code == 403
        assert (await c.get(f"/safes/{env['safe_id']}/history", headers=h["cashier"])).status_code == 403
        assert (await c.get(f"/wallets/{env['wallet_id']}/history", headers=h["cashier"])).status_code == 403
        # the cashier still picks a safe or wallet, without seeing what they hold
        safes = (await c.get("/safes", headers=h["cashier"])).json()
        assert safes and all("balance" not in s for s in safes)
        wallets = (await c.get("/wallets", headers=h["cashier"])).json()
        assert wallets and all("balance" not in w for w in wallets)
        assert "balance" in (await c.get("/safes", headers=h["accountant"])).json()[0]
        bad = await c.post("/expenses", json={"amount": "5", "description": "x", "vendor_id": str(uuid.uuid4())},
                           headers=h["admin"])
        assert bad.status_code == 404
        huge = await c.post("/expenses", json={"amount": "1" * 15, "description": "x"}, headers=h["admin"])
        assert huge.status_code == 422


# ── FIN-7, FIN-10, FIN-11 ─────────────────────────────────────────────────────────────────────

async def test_withdrawal_needs_finance_and_a_manager():
    env = await _ws()
    h = env["h"]
    async with _client() as c:
        assert (await c.post(f"/safes/{env['safe_id']}/withdraw", json={"amount": "10"}, headers=h["boss"])).status_code == 403
        assert (await c.post(f"/safes/{env['safe_id']}/withdraw", json={"amount": "10"}, headers=h["accountant"])).status_code == 403
        r = await c.post(f"/safes/{env['safe_id']}/withdraw", json={"amount": "10"}, headers=h["admin"])
        assert r.status_code == 200 and float(r.json()["balance"]) == 990.0


async def test_a_manual_deposit_names_no_shift_and_unknown_references_are_404():
    env = await _ws(accounting=True)
    h = env["h"]
    async with _client() as c:
        r = await c.post(f"/safes/{env['safe_id']}/deposit", json={"amount": "50", "shift_id": str(env["shift_id"])},
                         headers=h["admin"])
        assert r.status_code == 200, r.text
        assert (await c.post(f"/safes/{env['safe_id']}/deposit", json={"amount": "5", "warehouse_id": str(uuid.uuid4())},
                             headers=h["admin"])).status_code == 404
        assert (await c.post(f"/safes/{env['safe_id']}/deposit", json={"amount": "5", "received_by_id": str(uuid.uuid4())},
                             headers=h["admin"])).status_code == 404
        assert (await c.post(f"/safes/{uuid.uuid4()}/deposit", json={"amount": "5"}, headers=h["admin"])).status_code == 404
    entry = await _sql(env, "SELECT id FROM acc_entries WHERE source_type = 'safe_movement' AND event = 'deposit'")
    assert len(entry) == 1
    sides = await _sql(env, "SELECT COALESCE(a.role, a.name), l.credit FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id "
                            "WHERE l.entry_id = :e AND l.credit > 0", e=entry[0][0])
    assert sides[0][0] == "other_income"  # not the shift's drawer: no drawer cash moved
    assert await _one(env, "SELECT count(*) FROM safe_deposits WHERE shift_id IS NOT NULL") == 0


async def test_money_movements_are_idempotent():
    env = await _ws()
    h = env["h"]
    sid, wid = env["safe_id"], env["wallet_id"]
    await _sql(env, "UPDATE payment_wallets SET balance = 500 WHERE id = :w", w=wid)
    key = {"Idempotency-Key": f"dep-{uuid.uuid4().hex}"}
    async with _client() as c:
        first = await c.post(f"/safes/{sid}/deposit", json={"amount": "100"}, headers={**h["admin"], **key})
        again = await c.post(f"/safes/{sid}/deposit", json={"amount": "100"}, headers={**h["admin"], **key})
        assert first.status_code == again.status_code == 200 and first.json()["doc_number"] == again.json()["doc_number"]
        other = await c.post(f"/safes/{sid}/deposit", json={"amount": "101"}, headers={**h["admin"], **key})
        assert other.status_code == 422
        cid = str(uuid.uuid4())
        for _ in range(2):
            assert (await c.post(f"/safes/{sid}/withdraw", json={"amount": "30", "client_id": cid}, headers=h["admin"])).status_code == 200
            assert (await c.post("/safes/transfer", json={"from_wallet_id": str(wid), "to_safe_id": str(sid), "amount": "20",
                                                          "client_id": cid}, headers=h["admin"])).status_code == 200
        assert await _one(env, "SELECT balance FROM safes WHERE id = :s", s=sid) == D("1090")   # 1000 + 100 − 30 + 20
        assert await _one(env, "SELECT balance FROM payment_wallets WHERE id = :w", w=wid) == D("480")
        reset = str(uuid.uuid4())
        assert (await c.post(f"/wallets/{wid}/reset-balance", json={"client_id": reset}, headers=h["admin"])).status_code == 204
        await _sql(env, "UPDATE payment_wallets SET balance = 7 WHERE id = :w", w=wid)  # money came in meanwhile
        assert (await c.post(f"/wallets/{wid}/reset-balance", json={"client_id": reset}, headers=h["admin"])).status_code == 204
    assert await _one(env, "SELECT balance FROM payment_wallets WHERE id = :w", w=wid) == D("7")
    assert await _one(env, "SELECT count(*) FROM safe_transactions WHERE safe_id = :s", s=sid) == 3


# ── FIN-12 ────────────────────────────────────────────────────────────────────────────────────

async def test_categories_are_typed_and_updated_partially():
    env = await _ws()
    h = env["h"]
    async with _client() as c:
        assert (await c.post("/financial-categories", json={"name": "x", "type": "other"}, headers=h["admin"])).status_code == 422
        cat = (await c.post("/financial-categories", json={"name": "إيجار", "type": "expense", "color": "#112233"},
                            headers=h["admin"])).json()
        r = await c.put(f"/financial-categories/{cat['id']}", json={"color": "#445566"}, headers=h["admin"])
        assert r.status_code == 200 and r.json()["name"] == "إيجار" and r.json()["color"] == "#445566"
        assert (await c.put(f"/financial-categories/{uuid.uuid4()}", json={"name": "y"}, headers=h["admin"])).status_code == 404
        assert (await c.delete(f"/financial-categories/{uuid.uuid4()}", headers=h["admin"])).status_code == 404
        assert (await c.put(f"/expenses/{uuid.uuid4()}", json={"notes": "x"}, headers=h["admin"])).status_code == 404
        assert (await c.get("/audit-log", params={"entity_id": "nope"}, headers=h["admin"])).status_code == 422


async def test_another_workspaces_safe_is_not_found():
    env = await _ws()
    mine = env["safe_id"]
    other = await _ws()
    async with _client() as c:
        r = await c.post(f"/safes/{mine}/deposit", json={"amount": "5"}, headers=other["h"]["admin"])
        assert r.status_code == 404
        assert (await c.get(f"/safes/{mine}/history", headers=other["h"]["admin"])).status_code == 404
        assert (await c.post(f"/customers/payments/{uuid.uuid4()}/reverse", json={"reason": "abc"},
                             headers=other["h"]["admin"])).status_code == 404

