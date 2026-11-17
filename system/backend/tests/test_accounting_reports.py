"""The accounting reports and the opening entry (ADR-014 D7, D8, D10; step 4 of D12).

- Every report is computed from the ledger tables only: trial balance, income statement, balance
  sheet, general ledger, party statement; each by date range and by branch.
- The reconciliation compares the ledger with the operational balances and flags differences.
- The opening entry is built from today's balances, once, before the first other entry, and not into a
  closed month; the year-end closing moves income and expenses to retained earnings once the
  year's months are closed.
- Permissions (view / settings / close) and tenant isolation hold for every route.
"""
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app
from app.activities.general.modules.accounting.services import chart, closing, opening, posting, reports
from app.activities.general.modules.contacts.models.party import Supplier
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement
from app.activities.general.modules.sales.services import sales as sales_service
from app.core.exceptions import BusinessError
from app.db.base import AsyncSessionLocal
from app.models.registry import load_all_models
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password
from app.platform.permissions.roles import standard_permissions
from app.platform.tenancy.context import bind_tenant, current_tenant_id, install_tenancy_events
from tests.conftest import give_roles
from tests.test_accounting_ledger import _count, _env, _sale, _user

load_all_models()
install_tenancy_events()

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

D = Decimal
TODAY = posting.today()


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _headers(env: dict) -> dict:
    """An accountant (all four accounting permissions), a manager (view) and a cashier (none)."""
    t_id = env["tenant_id"]
    users = {}
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        for role in ("accountant", "manager", "cashier"):
            u = User(id=uuid.uuid4(), tenant_id=t_id, username=f"{role}_{t_id.hex[:8]}", full_name=role, role=role,
                     password_hash=hash_password("Pass12345!"), permissions=standard_permissions(role), is_active=True)
            s.add(u)
            users[role] = u
        await give_roles(s)
        await s.commit()
    current_tenant_id.set(t_id)
    return {role: {"Authorization": "Bearer " + create_access_token(
        {"sub": str(u.id), "role": u.role, "username": u.username, "tid": str(t_id)})} for role, u in users.items()}


async def _sql(env: dict, sql: str, **params):
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        result = await s.execute(text(sql), params)
        rows = result.all() if result.returns_rows else None
        await s.commit()
        return rows


async def _manual(env: dict, on: date, debit_role: str, credit_role: str, amount, warehouse_id=None) -> None:
    async with AsyncSessionLocal() as s:
        dr_acc = (await chart.account_by_role(s, env["tenant_id"], debit_role)).id
        cr_acc = (await chart.account_by_role(s, env["tenant_id"], credit_role)).id
        await posting.post(s, env["tenant_id"], "manual", uuid.uuid4(), "manual", on,
                           [posting.dr(dr_acc, amount), posting.cr(cr_acc, amount)], warehouse_id=warehouse_id)
        await s.commit()


async def _books() -> dict:
    """A workspace whose books started 60 days ago with the opening entry (safe 1000, drawer 1000,
    stock 50 × 60), then: a cash sale of 2 and a credit sale of 1 (price 100, cost 60), a return of 1
    from the cash sale, a receipt of 40 from the customer into the safe, rent of 250 from the safe, a
    sale of 70 in a second branch and 500 of other income 45 days ago (both against other
    receivables, which no operational cache tracks)."""
    from app.activities.general.modules.contacts import service as contacts
    from app.activities.general.modules.finance.services import expenses

    env = await _env()
    t = env["tenant_id"]
    wh2_id = uuid.uuid4()
    async with AsyncSessionLocal() as s:
        s.add(Warehouse(id=wh2_id, tenant_id=t, code=f"W2-{t.hex[:4]}", name="فرع المعادي", is_active=True))
        await s.commit()
    env["warehouse2_id"] = wh2_id
    async with AsyncSessionLocal() as s:
        await opening.create(s, t, TODAY - timedelta(days=60), env["cashier_id"])
        await s.commit()
    async with AsyncSessionLocal() as s:
        env["sale1"] = (await sales_service.create_sale(s, _sale(env, qty="2"), env["cashier_id"])).id
    async with AsyncSessionLocal() as s:
        await sales_service.create_sale(s, _sale(env, qty="1", customer_id=env["customer_id"], is_credit=True), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        await sales_service.partial_return_sale(s, env["sale1"], {"items": [{"product_id": env["product_id"], "qty": 1}]},
                                                env["cashier_id"])
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await contacts.receive_payment(s, env["customer_id"], D("40"), user, safe_id=env["safe_id"])
        await s.commit()
    async with AsyncSessionLocal() as s:
        rent = (await chart.account_by_role(s, t, "rent_expense")).id
        cat = (await s.execute(text("INSERT INTO financial_categories (name, type, account_id) VALUES ('إيجار', 'expense', :a) "
                                    "RETURNING id"), {"a": rent})).scalar_one()
        eid = (await s.execute(text("INSERT INTO expenses (amount, description, category_id, safe_id, payment_method, date, status) "
                                    "VALUES (250, 'إيجار المحل', :c, :s, 'cash', :d, 'draft') RETURNING id"),
                               {"c": cat, "s": env["safe_id"], "d": TODAY})).scalar_one()
        await s.commit()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await expenses.decide(s, eid, True, None, user)
        await s.commit()
    await _manual(env, TODAY, "other_receivables", "sales", 70, warehouse_id=wh2_id)
    await _manual(env, TODAY - timedelta(days=45), "other_receivables", "other_income", 500)
    return env


def _row(report: dict, role: str, key: str = "accounts") -> dict:
    return next(r for r in report[key] if r["role"] == role)


# ── trial balance ─────────────────────────────────────────────────────────────────────────────

async def test_trial_balance_balances_rolls_up_and_filters_by_date():
    env = await _books()
    t = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        tb = await reports.trial_balance(s, t)
        recent = await reports.trial_balance(s, t, date_from=TODAY - timedelta(days=30))
        zero = await reports.trial_balance(s, t, include_zero=True)
    assert tb["balanced"] and tb["totals"]["debit"] == tb["totals"]["credit"]
    assert tb["totals"]["closing_debit"] == tb["totals"]["closing_credit"]
    roles = {r["role"] for r in tb["accounts"]}
    assert "vat_input" not in roles and "inventory" in roles          # no movement: hidden
    assert "vat_input" in {r["role"] for r in zero["accounts"]}       # …unless asked for
    assert len(zero["accounts"]) >= len(chart.load_chart()["accounts"])

    inv = _row(tb, "inventory")
    assert (inv["opening"], inv["debit"], inv["credit"], inv["closing"]) == (0.0, 3060.0, 180.0, 2880.0)
    sales = _row(tb, "sales")
    assert (sales["credit"], sales["closing_credit"], sales["closing_debit"]) == (370.0, 370.0, 0.0)
    # Groups roll their children up: all assets, and the cash group (safe 790 + drawer 1100).
    assets = next(r for r in tb["accounts"] if r["code"] == "1")
    assert assets["closing_debit"] == 5400.0 and assets["level"] == 0 and assets["is_group"]
    assert next(r for r in tb["accounts"] if r["code"] == "1251")["closing"] == 1890.0

    # From 30 days ago: what came before is the opening balance, and the closing balance is the same.
    inv30 = _row(recent, "inventory")
    assert (inv30["opening"], inv30["debit"], inv30["credit"], inv30["closing"]) == (3000.0, 60.0, 180.0, 2880.0)
    assert _row(recent, "other_income")["opening_credit"] == 500.0 and _row(recent, "other_income")["debit"] == 0.0
    assert recent["balanced"] and recent["totals"]["opening_debit"] == recent["totals"]["opening_credit"]
    assert recent["totals"]["closing_debit"] == tb["totals"]["closing_debit"]


# ── income statement ──────────────────────────────────────────────────────────────────────────

async def test_income_statement_figures_by_period_and_branch():
    env = await _books()
    t = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        full = await reports.income_statement(s, t)
        recent = await reports.income_statement(s, t, date_from=TODAY - timedelta(days=30))
        branch1 = await reports.income_statement(s, t, warehouse_id=env["warehouse_id"])
        branch2 = await reports.income_statement(s, t, warehouse_id=env["warehouse2_id"])
    assert full["revenue"]["total"] == 370.0
    assert full["sales_returns"]["total"] == 100.0 and full["net_sales"] == 270.0
    assert full["cogs"]["total"] == 120.0 and full["gross_profit"] == 150.0
    assert [(ln["name_en"], ln["amount"]) for ln in full["operating_expenses"]["lines"]] == [("Rent", 250.0)]
    assert full["operating_profit"] == -100.0
    assert full["other_income"]["total"] == 500.0 and full["other_expenses"]["total"] == 0.0
    assert full["net_profit"] == 400.0
    assert full["revenue"]["lines"][0]["name"] and full["revenue"]["lines"][0]["name_en"] == "Sales"

    # The period: the other income of 45 days ago is out.
    assert recent["other_income"]["total"] == 0.0 and recent["net_profit"] == -100.0
    # Branches: the first has its sale, return and cost (the rent and other income carry no branch).
    assert (branch1["revenue"]["total"], branch1["sales_returns"]["total"], branch1["cogs"]["total"]) == (300.0, 100.0, 120.0)
    assert branch1["gross_profit"] == 80.0 and branch1["net_profit"] == 80.0
    assert branch2["revenue"]["total"] == 70.0 and branch2["net_profit"] == 70.0


# ── balance sheet ─────────────────────────────────────────────────────────────────────────────

async def test_balance_sheet_equation_and_current_year_profit():
    env = await _books()
    t = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        bs = await reports.balance_sheet(s, t)
        earlier = await reports.balance_sheet(s, t, as_of=TODAY - timedelta(days=50))
        branch = await reports.balance_sheet(s, t, warehouse_id=env["warehouse_id"])
    assert bs["balanced"] and bs["difference"] == 0.0
    assert bs["assets"]["total"] == 5400.0 and bs["liabilities"]["total"] == 0.0
    eq = bs["equity"]
    assert eq["accounts_total"] == 5000.0                              # the opening balance equity
    assert eq["prior_years_profit"] + eq["current_year_profit"] == eq["profit_to_date"] == 400.0
    assert eq["total"] == 5400.0 == bs["total_liabilities_and_equity"]
    assert {r["code"] for r in bs["assets"]["accounts"]} >= {"1", "12", "121", "122", "1251"}
    # Before the other income and every document there was only the opening entry.
    assert earlier["balanced"] and earlier["assets"]["total"] == 5000.0 and earlier["equity"]["profit_to_date"] == 0.0
    # A branch sheet leaves out the lines that carry no branch (the safe, the opening equity): it does
    # not balance, and says so and by how much (assets 1100 + 2880 + 100, profit 80).
    assert branch["balanced"] is False and branch["difference"] == 4000.0 and branch["assets"]["total"] == 4080.0


# ── general ledger and party statement ─────────────────────────────────────────────────────────

async def test_general_ledger_running_balance_and_source_links():
    env = await _books()
    t = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        acc = await chart.money_account(s, t, "safe", env["safe_id"])
        gl = await reports.general_ledger(s, t, acc)
        recent = await reports.general_ledger(s, t, acc, date_from=TODAY - timedelta(days=30))
        group = await reports.general_ledger(s, t, (await chart.account_by_role(s, t, "cash_group")).id)
        paged = await reports.general_ledger(s, t, acc, page=2, page_size=2)
        sales = await reports.general_ledger(s, t, (await chart.account_by_role(s, t, "sales")).id)
        with pytest.raises(Exception) as e:
            await reports.general_ledger(s, t, uuid.uuid4())
    assert gl["normal_side"] == "debit" and gl["opening_balance"] == 0.0
    assert [(ln["source_type"], ln["debit"], ln["credit"], ln["balance"]) for ln in gl["lines"]] == [
        ("opening", 1000.0, 0.0, 1000.0), ("customer_payment", 40.0, 0.0, 1040.0), ("expense", 0.0, 250.0, 790.0)]
    assert gl["closing_balance"] == 790.0 and gl["total_debit"] == 1040.0 and gl["total_credit"] == 250.0
    first = gl["lines"][0]
    assert first["event"] == "opening" and first["number"] and first["entry_id"] and first["source_id"] and first["memo"]
    assert gl["lines"][1]["date"] == TODAY
    # From 30 days ago the opening entry is the opening balance.
    assert recent["opening_balance"] == 1000.0 and len(recent["lines"]) == 2 and recent["lines"][-1]["balance"] == 790.0
    # A group account takes its sub-accounts (safe 790 + drawer 1100); a page keeps the running balance.
    assert group["closing_balance"] == 1890.0 and "خزنة — الخزينة الرئيسية" in {ln["account_name"] for ln in group["lines"]}
    assert paged["count"] == 3 and len(paged["lines"]) == 1 and paged["lines"][0]["balance"] == 790.0
    # Credit-normal accounts run in their own direction: sales 370.
    assert sales["normal_side"] == "credit" and sales["lines"][-1]["balance"] == 370.0
    assert "غير موجود" in str(getattr(e.value, "detail", e.value))


async def test_party_statement_matches_the_operational_balance():
    env = await _books()
    t, cid = env["tenant_id"], env["customer_id"]
    async with AsyncSessionLocal() as s:
        st = await reports.party_statement(s, t, "customer", cid)
        later = await reports.party_statement(s, t, "customer", cid, date_from=TODAY + timedelta(days=1))
        branch = await reports.party_statement(s, t, "customer", cid, warehouse_id=env["warehouse2_id"])
        sup = Supplier(id=uuid.uuid4(), tenant_id=t, name="مورد", balance=D("0"))
        s.add(sup)
        await s.flush()
        sup_st = await reports.party_statement(s, t, "supplier", sup.id)
        with pytest.raises(BusinessError):
            await reports.party_statement(s, t, "alien", cid)
        with pytest.raises(Exception) as e:
            await reports.party_statement(s, t, "customer", uuid.uuid4())
    assert st["party"]["name"] == "عميل" and st["meaning"] == "what_they_owe_us"
    assert [(ln["source_type"], ln["debit"], ln["credit"], ln["balance"]) for ln in st["lines"]] == [
        ("sale", 100.0, 0.0, 100.0), ("customer_payment", 0.0, 40.0, 60.0)]
    assert all(ln["party_id"] == cid and ln["party_name"] == "عميل" for ln in st["lines"])
    assert st["closing_balance"] == 60.0 == st["operational_balance"] == st["ledger_balance"]
    assert st["difference"] == 0.0 and st["matches"] is True
    # A period starting later: everything before is the opening balance.
    assert later["opening_balance"] == 60.0 and later["lines"] == [] and later["matches"] is True
    assert branch["lines"] == [] and branch["matches"] is True           # the ledger balance is the whole ledger's
    assert sup_st["meaning"] == "what_we_owe_them" and sup_st["lines"] == [] and sup_st["matches"] is True
    assert "غير موجود" in str(getattr(e.value, "detail", e.value))


# ── reconciliation ────────────────────────────────────────────────────────────────────────────

async def test_reconciliation_agrees_then_flags_a_forced_difference():
    env = await _books()
    t = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        ok = await reports.reconciliation(s, t)
    assert ok["ok"] is True and ok["differences"] == [] and ok["parties"] == []
    keys = {i["key"] for i in ok["items"]}
    assert {"receivables", "payables", "inventory", f"safe:{env['safe_id']}"} <= keys
    assert next(i for i in ok["items"] if i["key"] == "inventory")["ledger"] == 2880.0

    await _sql(env, "UPDATE customers SET balance = balance + 25 WHERE id = :c", c=env["customer_id"])
    await _sql(env, "UPDATE safes SET balance = balance - 10 WHERE id = :s", s=env["safe_id"])
    await _sql(env, "UPDATE payment_wallets SET balance = 15 WHERE id = :w", w=env["wallet_id"])
    await _sql(env, "UPDATE stock_balances SET qty = qty + 1 WHERE product_id = :p AND warehouse_id = :w",
               p=env["product_id"], w=env["warehouse_id"])
    async with AsyncSessionLocal() as s:
        bad = await reports.reconciliation(s, t)
    assert bad["ok"] is False
    diffs = {i["key"]: i["difference"] for i in bad["differences"]}
    assert diffs == {"receivables": 25.0, f"safe:{env['safe_id']}": -10.0, f"wallet:{env['wallet_id']}": 15.0, "inventory": 60.0}
    assert [(p["id"], p["difference"]) for p in bad["parties"]] == [(env["customer_id"], 25.0)]
    # It only flags: nothing was changed.
    async with AsyncSessionLocal() as s:
        assert (await s.execute(text("SELECT balance FROM customers WHERE id = :c"), {"c": env["customer_id"]})).scalar_one() == D("85")


# ── opening entry ─────────────────────────────────────────────────────────────────────────────

async def _opening_env() -> dict:
    """A workspace with balances but no ledger entries: customer owes 300, supplier is owed 200,
    safe 1000, wallet 150, an open drawer of 1000, stock 50 × 60, and a product with stock but no cost."""
    env = await _env()
    t = env["tenant_id"]
    sup_id, free_id = uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as s:
        s.add_all([Supplier(id=sup_id, tenant_id=t, name="مورد الجملة", balance=D("200")),
                   Product(id=free_id, tenant_id=t, name="صنف بلا تكلفة", code=f"F-{t.hex[:6]}", retail_price=D("10"),
                           cost_price=D("0"), stock_status="tracked", is_active=True)])
        await s.flush()
        await apply_movement(s, product_id=free_id, warehouse_id=env["warehouse_id"], movement_type=MovementType.opening_stock,
                             qty=D("5"), created_by=env["cashier_id"])
        await s.commit()
    await _sql(env, "UPDATE customers SET balance = 300 WHERE id = :c", c=env["customer_id"])
    await _sql(env, "UPDATE payment_wallets SET balance = 150 WHERE id = :w", w=env["wallet_id"])
    env.update(supplier_id=sup_id, free_product_id=free_id)
    return env


def _by(lines: list[dict], section: str) -> list[dict]:
    return [ln for ln in lines if ln["section"] == section]


async def test_opening_preview_posts_nothing_and_shows_the_exact_lines():
    env = await _opening_env()
    h = await _headers(env)
    async with _client() as c:
        r = await c.get("/accounting/opening/preview", headers=h["manager"])
        assert r.status_code == 200, r.text
        p = r.json()
        assert (await c.get("/accounting/opening/preview", headers=h["cashier"])).status_code == 403
    assert await _count("SELECT count(*) FROM acc_entries") == 0
    assert p["can_post"] is True and p["blockers"] == [] and p["balanced"] is True
    assert p["date"] == TODAY.isoformat()
    cust, = _by(p["lines"], "customers")
    assert (cust["debit"], cust["credit"], cust["party_type"], cust["party_id"]) == (300.0, 0.0, "customer", str(env["customer_id"]))
    assert cust["account"]["code"] == "122"
    supp, = _by(p["lines"], "suppliers")
    assert (supp["debit"], supp["credit"], supp["party_type"], supp["party_id"]) == (0.0, 200.0, "supplier", str(env["supplier_id"]))
    safe, = _by(p["lines"], "safes")
    assert safe["debit"] == 1000.0 and safe["account"] is None  # its sub-account is created when posted
    assert _by(p["lines"], "wallets")[0]["debit"] == 150.0
    drawer, = _by(p["lines"], "drawers")
    assert drawer["debit"] == 1000.0 and drawer["warehouse_id"] == str(env["warehouse_id"])
    stock, = _by(p["lines"], "inventory")
    assert stock["debit"] == 3000.0 and stock["warehouse_id"] == str(env["warehouse_id"])
    plug, = _by(p["lines"], "equity")
    assert plug["credit"] == 5250.0 and plug["account"]["code"] == "33"
    assert p["total_debit"] == p["total_credit"] == 5450.0
    assert p["equity"] == {"debit": 0.0, "credit": 5250.0}
    assert [(x["name"], x["qty"]) for x in p["skipped_no_cost"]] == [("صنف بلا تكلفة", 5.0)]
    assert p["notes"] and p["opening_entry"] is None


async def test_opening_posts_once_balances_and_can_be_redone_only_after_reversal():
    env = await _opening_env()
    t = env["tenant_id"]
    h = await _headers(env)
    async with _client() as c:
        assert (await c.post("/accounting/opening", json={}, headers=h["manager"])).status_code == 403
        r = await c.post("/accounting/opening", json={"date": TODAY.isoformat()}, headers=h["accountant"])
        assert r.status_code == 201, r.text
        out = r.json()
        again = await c.post("/accounting/opening", json={"date": TODAY.isoformat()}, headers=h["accountant"])
        settings = await c.get("/accounting/settings", headers=h["manager"])
    assert out["entry"]["number"] == "JE-000001" and out["settings"]["start_date"] == TODAY.isoformat()
    assert again.status_code == 400 and "مسجل بالفعل" in again.json()["detail"]
    assert settings.json() == {"fiscal_year_start": 1, "start_date": TODAY.isoformat()}
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_type = 'opening'") == 1

    async with AsyncSessionLocal() as s:
        tb = await reports.trial_balance(s, t)
        rec = await reports.reconciliation(s, t)
        cust = await reports.party_statement(s, t, "customer", env["customer_id"])
        sup = await reports.party_statement(s, t, "supplier", env["supplier_id"])
    assert tb["balanced"] and tb["totals"]["debit"] == tb["totals"]["credit"] == 5450.0
    assert _row(tb, "opening_equity")["closing_credit"] == 5250.0
    assert _row(tb, "payables")["closing_credit"] == 200.0 and _row(tb, "receivables")["closing_debit"] == 300.0
    assert cust["matches"] and cust["closing_balance"] == 300.0 and sup["matches"] and sup["closing_balance"] == 200.0
    assert rec["ok"] is True            # ledger and caches agree right after the opening (drawers aren't compared)
    # The safe, the wallet and the drawer each got their own sub-account.
    assert await _count("SELECT count(*) FROM acc_money_accounts WHERE kind IN ('safe', 'wallet', 'drawer')") == 3

    # A second entry is refused until the first is reversed (the normal reversal), then a new one posts
    # the whole balances again.
    async with AsyncSessionLocal() as s:
        entry, _ = await posting.active_source(s, t, "opening", "opening", "opening")
        await posting.reverse(s, entry, user_id=env["cashier_id"])
        await s.commit()
    async with AsyncSessionLocal() as s:
        net = (await reports.trial_balance(s, t))["totals"]
    assert net["closing_debit"] == net["closing_credit"] == 0.0
    async with _client() as c:
        r = await c.post("/accounting/opening", json={}, headers=h["accountant"])
    assert r.status_code == 201 and r.json()["total_debit"] == 5450.0 and r.json()["entry"]["number"] == "JE-000003"
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_type = 'opening'") == 3


async def test_opening_adds_only_what_the_ledger_lacks():
    env = await _opening_env()
    t = env["tenant_id"]
    # A credit sale of 2 is already posted today: the customer's balance and the stock moved with it.
    async with AsyncSessionLocal() as s:
        await sales_service.create_sale(s, _sale(env, qty="2", customer_id=env["customer_id"], is_credit=True), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        plan = await opening.plan(s, t, TODAY)
    cust, = _by(plan["lines"], "customers")
    assert (cust["operational"], cust["ledger"], cust["debit"]) == (500.0, 200.0, 300.0)   # only the 300 from before
    stock, = _by(plan["lines"], "inventory")
    assert (stock["operational"], stock["ledger"], stock["debit"]) == (2880.0, -120.0, 3000.0)
    assert plan["balanced"]


async def test_opening_is_refused_after_later_entries_a_future_date_and_a_closed_month():
    from app.activities.general.modules.finance.routes import periods

    env = await _env()
    h = await _headers(env)
    await _manual(env, TODAY - timedelta(days=10), "other_receivables", "other_income", 5)
    async with _client() as c:
        late = await c.post("/accounting/opening", json={"date": TODAY.isoformat()}, headers=h["accountant"])
        future = await c.post("/accounting/opening", json={"date": (TODAY + timedelta(days=1)).isoformat()}, headers=h["accountant"])
        preview = await c.get("/accounting/opening/preview", params={"date": TODAY.isoformat()}, headers=h["accountant"])
        on_the_day = await c.post("/accounting/opening", json={"date": (TODAY - timedelta(days=10)).isoformat()},
                                  headers=h["accountant"])
    assert late.status_code == 400 and "أول قيد" in late.json()["detail"]
    assert future.status_code == 400 and "المستقبل" in future.json()["detail"]
    assert preview.json()["can_post"] is False and preview.json()["blockers"]
    assert on_the_day.status_code == 201       # on the first entry's own day is allowed

    env2 = await _env()
    h2 = await _headers(env2)
    last_month_day = TODAY.replace(day=1) - timedelta(days=3)
    async with AsyncSessionLocal() as s:
        user = await _user(s, env2)
        await periods.close_period(last_month_day.strftime("%Y-%m"), db=s, current_user=user)
    async with _client() as c:
        r = await c.post("/accounting/opening", json={"date": last_month_day.isoformat()}, headers=h2["accountant"])
    assert r.status_code == 400 and "مغلقة" in r.json()["detail"]
    assert await _count("SELECT count(*) FROM acc_entries") == 0


# ── year-end closing ──────────────────────────────────────────────────────────────────────────

async def test_year_end_closes_income_and_expenses_into_retained_earnings_once():
    from app.activities.general.modules.finance.routes import periods

    env = await _env()
    t = env["tenant_id"]
    h = await _headers(env)
    await _manual(env, date(2024, 3, 10), "other_receivables", "sales", 1000, warehouse_id=env["warehouse_id"])
    await _manual(env, date(2024, 6, 15), "rent_expense", "other_receivables", 300)
    async with _client() as c:
        early = await c.post("/accounting/year-end", params={"year": 2024}, headers=h["accountant"])
        assert (await c.post("/accounting/year-end", params={"year": 2024}, headers=h["manager"])).status_code == 403
        assert (await c.post("/accounting/year-end", params={"year": 2024}, headers=h["cashier"])).status_code == 403
    assert early.status_code == 400 and "2024-03" in early.json()["detail"]

    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        for month in range(3, 13):
            await periods.close_period(f"2024-{month:02d}", db=s, current_user=user)
    async with _client() as c:
        r = await c.post("/accounting/year-end", params={"year": 2024}, headers=h["accountant"])
        assert r.status_code == 200, r.text
        again = await c.post("/accounting/year-end", params={"year": 2024}, headers=h["accountant"])
        current = await c.post("/accounting/year-end", params={"year": TODAY.year}, headers=h["accountant"])
    out = r.json()
    assert out["to"] == "2024-12-31" and out["net_profit"] == 700.0 and out["entry"]["date"] == "2024-12-31"
    assert again.status_code == 400 and "مقفلة بالفعل" in again.json()["detail"]
    assert current.status_code == 400 and "لم تنتهِ" in current.json()["detail"]
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_type = 'year_end'") == 1

    async with AsyncSessionLocal() as s:
        tb = await reports.trial_balance(s, t, date(2024, 1, 1), date(2024, 12, 31))
        raw = await reports.trial_balance(s, t, date(2024, 1, 1), date(2024, 12, 31), include_closing=False)
        isc = await reports.income_statement(s, t, date(2024, 1, 1), date(2024, 12, 31))
        isc_closed = await reports.income_statement(s, t, date(2024, 1, 1), date(2024, 12, 31), include_closing=True)
        bs = await reports.balance_sheet(s, t, date(2024, 12, 31))
        bs_raw = await reports.balance_sheet(s, t, date(2024, 12, 31), include_closing=False)
        branch = await reports.income_statement(s, t, date(2024, 1, 1), date(2024, 12, 31), warehouse_id=env["warehouse_id"])
        branch_tb = await reports.trial_balance(s, t, warehouse_id=env["warehouse_id"])
    assert tb["balanced"] and _row(tb, "sales")["closing"] == 0.0 and _row(tb, "rent_expense")["closing"] == 0.0
    assert _row(tb, "sales")["debit"] == 1000.0 and _row(tb, "retained_earnings")["closing_credit"] == 700.0
    assert raw["balanced"] and _row(raw, "sales")["closing_credit"] == 1000.0
    assert "retained_earnings" not in {r["role"] for r in raw["accounts"]}
    # The profit of the closed year still shows (the closing entry is left out by default).
    assert (isc["revenue"]["total"], isc["operating_expenses"]["total"], isc["net_profit"]) == (1000.0, 300.0, 700.0)
    assert isc_closed["net_profit"] == 0.0
    assert bs["balanced"] and bs["equity"]["profit_to_date"] == 0.0 and bs["equity"]["accounts_total"] == 700.0
    assert bs_raw["balanced"] and bs_raw["equity"]["profit_to_date"] == 700.0 and bs_raw["equity"]["accounts_total"] == 0.0
    assert branch["net_profit"] == 1000.0 and branch_tb["balanced"]
    assert _row(branch_tb, "retained_earnings")["closing_credit"] == 1000.0   # the profit stays in its branch

    # The months of a closed year can't be reopened until the closing is reversed.
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        with pytest.raises(BusinessError) as e:
            await periods.reopen_period("2024-12", periods.ReopenRequest(reason="تصحيح"), db=s, current_user=user)
        assert "مقفلة بالقيد" in str(e.value.detail)
        await s.rollback()
    async with _client() as c:
        blocked = await c.put("/accounting/settings", json={"fiscal_year_start": 7}, headers=h["accountant"])
        rev = await c.post("/accounting/year-end/reverse", params={"year": 2024}, headers=h["accountant"])
        assert rev.status_code == 200, rev.text
        assert (await c.post("/accounting/year-end/reverse", params={"year": 2024}, headers=h["accountant"])).status_code == 400
        assert (await c.put("/accounting/settings", json={"fiscal_year_start": 7}, headers=h["manager"])).status_code == 403
        changed = await c.put("/accounting/settings", json={"fiscal_year_start": 7}, headers=h["accountant"])
    assert blocked.status_code == 400
    assert rev.json()["entry"]["date"] == "2024-12-31"
    assert changed.status_code == 200 and changed.json()["fiscal_year_start"] == 7
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await periods.reopen_period("2024-12", periods.ReopenRequest(reason="تصحيح"), db=s, current_user=user)
        net = await reports.trial_balance(s, t)
    assert _row(net, "sales")["closing_credit"] == 1000.0 and _row(net, "retained_earnings")["closing"] == 0.0


def test_fiscal_year_dates():
    assert closing.fiscal_year(2024, 1) == (date(2024, 1, 1), date(2024, 12, 31))
    assert closing.fiscal_year(2024, 7) == (date(2024, 7, 1), date(2025, 6, 30))
    assert reports.fiscal_year_start_for(date(2025, 3, 5), 7) == date(2024, 7, 1)
    assert reports.fiscal_year_start_for(date(2025, 8, 5), 7) == date(2025, 7, 1)


# ── permissions and tenant isolation ──────────────────────────────────────────────────────────

async def test_reports_need_view_and_opening_and_closing_need_their_own_permissions():
    env = await _books()
    h = await _headers(env)
    async with AsyncSessionLocal() as s:
        acc = await chart.money_account(s, env["tenant_id"], "safe", env["safe_id"])
    reads = ["/accounting/trial-balance", "/accounting/income-statement", "/accounting/balance-sheet",
             f"/accounting/general-ledger/{acc}", f"/accounting/party-statement/customer/{env['customer_id']}",
             "/accounting/reconciliation", "/accounting/opening/preview", "/accounting/settings"]
    async with _client() as c:
        for path in reads:
            assert (await c.get(path, headers=h["cashier"])).status_code == 403, path
            for who in ("manager", "accountant"):
                assert (await c.get(path, headers=h[who])).status_code == 200, (path, who)
        branch = await c.get("/accounting/trial-balance", params={"warehouse_id": str(env["warehouse2_id"])}, headers=h["manager"])
        assert branch.json()["totals"]["debit"] == 70.0
        r = await c.get("/accounting/trial-balance", params={"from": (TODAY - timedelta(days=30)).isoformat(),
                                                             "include_zero": "true"}, headers=h["manager"])
        assert r.status_code == 200 and r.json()["include_zero"] is True
        # The opening entry and the chart's settings need `accounting:settings`; the year end `accounting:close`.
        assert (await c.post("/accounting/opening", json={}, headers=h["manager"])).status_code == 403
        assert (await c.post("/accounting/year-end", params={"year": 2024}, headers=h["manager"])).status_code == 403
        assert (await c.put("/accounting/settings", json={"fiscal_year_start": 4}, headers=h["manager"])).status_code == 403
        assert (await c.put("/accounting/settings", json={"fiscal_year_start": 13}, headers=h["accountant"])).status_code == 422
        assert (await c.get("/accounting/party-statement/customer/" + str(uuid.uuid4()), headers=h["accountant"])).status_code == 404
        assert (await c.get("/accounting/party-statement/robot/" + str(env["customer_id"]), headers=h["accountant"])).status_code == 400


async def test_every_report_is_isolated_per_workspace():
    env = await _books()
    t = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        acc = await chart.money_account(s, t, "safe", env["safe_id"])
    other = await _env()          # binds the other workspace
    o = other["tenant_id"]
    h = await _headers(other)
    assert o != t
    async with AsyncSessionLocal() as s:
        tb = await reports.trial_balance(s, o)
        inc = await reports.income_statement(s, o)
        bs = await reports.balance_sheet(s, o)
        rec = await reports.reconciliation(s, o)
        # The first workspace's ids are unknown here.
        with pytest.raises(Exception) as e1:
            await reports.general_ledger(s, o, acc)
        with pytest.raises(Exception) as e2:
            await reports.party_statement(s, o, "customer", env["customer_id"])
    assert getattr(e1.value, "status_code", None) == 404 and getattr(e2.value, "status_code", None) == 404
    assert tb["accounts"] == [] and tb["totals"]["debit"] == 0.0 and tb["balanced"]
    assert inc["net_profit"] == 0.0 and inc["revenue"]["lines"] == []
    assert bs["assets"]["total"] == 0.0 and bs["balanced"]
    # The other workspace's own caches show only its own safe, never the first one's.
    assert {i["key"] for i in rec["items"] if ":" in i["key"]} == {f"safe:{other['safe_id']}"}
    assert rec["parties"] == []
    async with _client() as c:
        assert (await c.get(f"/accounting/general-ledger/{acc}", headers=h["accountant"])).status_code == 404
        assert (await c.get(f"/accounting/party-statement/customer/{env['customer_id']}", headers=h["accountant"])).status_code == 404
        assert (await c.get("/accounting/trial-balance", headers=h["accountant"])).json()["accounts"] == []
    # And the first workspace is untouched.
    current_tenant_id.set(t)
    async with AsyncSessionLocal() as s:
        assert (await reports.trial_balance(s, t))["totals"]["debit"] > 0


# ── steps 3 and 4 together ────────────────────────────────────────────────────────────────────

async def test_reconciliation_agrees_after_purchases_payments_returns_and_damage():
    """After the opening entry, the step-3 postings keep the ledger equal to the operational balances:
    a purchase of 10 x 70 with 200 paid, a supplier payment of 150, a return of 4 and 2 units damaged."""
    from tests import test_accounting_postings_2 as p2

    env = await p2._env()
    t, sup = env["tenant_id"], env["supplier_id"]
    async with AsyncSessionLocal() as s:
        await opening.create(s, t, TODAY, env["cashier_id"])
        await s.commit()
    po = await p2._receive(env)
    async with AsyncSessionLocal() as s:
        user = await p2._user(s, env)
        await p2.purchase_service.record_supplier_transaction(s, sup, D("150"), "credit", user, safe_id=env["safe_id"])
        await s.commit()
    async with AsyncSessionLocal() as s:
        user = await p2._user(s, env)
        await p2.purchase_service.create_purchase_return(s, po, p2.PurchaseReturnCreate(
            items=[p2.PurchaseReturnItemIn(product_id=env["product_id"], qty=D("4"))]), user)
    async with AsyncSessionLocal() as s:
        await apply_movement(s, product_id=env["product_id"], warehouse_id=env["warehouse_id"],
                             movement_type=MovementType.damage, qty=D("2"), note="تالف")
        await s.commit()

    async with AsyncSessionLocal() as s:
        rec = await reports.reconciliation(s, t)
        tb = await reports.trial_balance(s, t, TODAY, TODAY)
    items = {i["key"]: i for i in rec["items"]}
    assert rec["ok"] is True and rec["differences"] == [] and rec["parties"] == [], rec["differences"]
    assert items["payables"]["ledger"] == 70.0                      # 700 - 200 - 150 - 280
    assert items[f"safe:{env['safe_id']}"]["ledger"] == 650.0       # 1000 - 200 - 150
    assert abs(items["inventory"]["ledger"] - 3420.0 + 2 * 3420.0 / 56) < 0.02   # 3000 + 700 - 280 - 2 x avg
    assert tb["balanced"] is True
