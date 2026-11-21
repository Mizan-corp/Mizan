"""Reporting, phase C (PRODUCTION_READINESS.md, `reporting`): what phase A left of REP-8, 9, 10, 12, 14, 15.

REP-8  cash flow from the money movements: with accounting, the ledger's money accounts netted per
       document (moves between the company's own accounts are not cash flow), with opening and
       closing balances; without, the documents; both as `lines` keyed like the ledger's sources.
REP-9  the overview's cash in the open drawers is what each shift's close expects, per drawer.
REP-10 aging as of a date ignores what was paid or returned after it.
REP-12 an export without rows still has its header; payment methods are Arabic words.
REP-14 aging is aggregated in the database; a listed customer shows a bounded number of invoices.
REP-15 money is a decimal string.
"""
import io
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.activities.general.modules.reporting.scope import today
from app.activities.general.modules.sales.schemas import SaleCreate, SaleItemCreate
from app.activities.general.modules.sales.services import sales as sales_service
from app.db.base import AsyncSessionLocal
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from tests.test_reporting import _auth, _client, _range, _scenario, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

D = Decimal


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


def _lines(cf: dict) -> dict:
    return {x["key"]: (D(x["in"]), D(x["out"])) for x in cf["lines"]}


# ── REP-8 ────────────────────────────────────────────────────────────────────────────────────

async def test_cash_flow_comes_from_the_ledgers_money_accounts():
    """Old code: the documents only, so money that moved without a sales or expense document (and
    moves between the company's own accounts) couldn't be told apart; no opening or closing cash."""
    env = await _scenario(accounting=True)
    t, u = env["tenant_id"], env["users"]
    h = _auth(u["manager"], t)
    current_tenant_id.set(t)
    async with AsyncSessionLocal() as s:  # 50 paid by wallet into the wallet, then moved to the safe
        await sales_service.create_sale(s, SaleCreate(
            warehouse_id=env["warehouse_id"], shift_id=env["shift_id"], payment_method="wallet", wallet_id=env["wallet_id"],
            items=[SaleItemCreate(product_id=env["product_id"], qty=D("1"), unit_price=D("100"))]), env["cashier_id"])
    async with _client() as c:
        r = await c.post("/safes/transfer", headers=h, json={"from_wallet_id": str(env["wallet_id"]),
                                                              "to_safe_id": str(env["safe_id"]), "amount": "100"})
        assert r.status_code in (200, 201), r.text
        cf = (await c.get("/reports/cash-flow", params=_range(), headers=h)).json()
        branch = (await c.get("/reports/cash-flow", params=_range(warehouse_id=str(env["warehouse_id"])), headers=h)).json()
    assert cf["source"] == "ledger", cf
    lines = _lines(cf)
    # Cash and wallet sales 180 + 100 + 300 + 100; the refund 100; the drawer's expense 10. The
    # wallet → safe move nets to zero and is not a line.
    assert lines["sale"] == (D("680.00"), D("0.00"))
    assert lines["sale_return"] == (D("0.00"), D("100.00"))
    assert lines["drawer_tx"] == (D("0.00"), D("10.00"))
    assert all(k not in lines for k in ("wallet_movement", "safe_movement"))
    assert (cf["total_in"], cf["total_out"], cf["net_cash_flow"]) == ("680.00", "110.00", "570.00")
    assert D(cf["closing_balance"]) - D(cf["opening_balance"]) == D("570.00")
    by_kind = {}
    for a in cf["accounts"]:
        by_kind.setdefault(a["kind"], []).append(a)
    wallet = by_kind["wallet"][0]
    assert (wallet["in"], wallet["out"], wallet["closing"]) == ("100.00", "100.00", "0.00")
    # The branch: its own drawer and the wallet sale made there.
    assert _lines(branch)["sale"] == (D("380.00"), D("0.00"))


async def test_cash_flow_without_the_ledger_has_the_same_lines():
    env = await _scenario()
    async with _client() as c:
        cf = (await c.get("/reports/cash-flow", params=_range(), headers=_auth(env["users"]["manager"], env["tenant_id"]))).json()
    assert cf["source"] == "operations" and cf["opening_balance"] is None
    assert _lines(cf)["sale"] == (D("580.00"), D("0.00"))
    assert (cf["total_in"], cf["total_out"]) == ("580.00", "160.00")  # refund 100, rent 50, drawer 10


# ── REP-9 ────────────────────────────────────────────────────────────────────────────────────

async def test_the_overview_counts_the_drawers_like_the_shift_close():
    """Old code: only the drawers' totals, money as floats."""
    from app.activities.general.modules.pos.service import compute_summary

    env = await _scenario()
    t, u = env["tenant_id"], env["users"]
    async with _client() as c:
        overview = (await c.get("/admin/overview", headers=_auth(u["manager"], t))).json()
    current_tenant_id.set(t)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        expected = sum([(await compute_summary(s, sid))["expected_balance"] for sid in (env["shift_id"], env["shift2_id"])], D(0))
    assert D(overview["summary"]["total_cash_in_drawers"]) == expected
    drawers = {d["name"]: d for d in overview["cash_drawers"]}
    assert D(drawers["فرع المعادي"]["expected"]) == D("300.00")
    assert isinstance(overview["summary"]["total_revenue"], str)  # REP-15


# ── REP-10 / REP-14 ──────────────────────────────────────────────────────────────────────────

async def test_aging_as_of_a_date_ignores_later_payments_and_returns(monkeypatch):
    """Old code: a customer's invoice showed what was paid on it after `as_of` too."""
    from app.activities.general.modules.reporting import service as report_service

    env = await _scenario()
    t, u = env["tenant_id"], env["users"]
    await _sql(env, "UPDATE customers SET credit_limit = 100000 WHERE id = :c", c=env["customer_id"])
    current_tenant_id.set(t)
    ids = []
    for qty in ("1", "2"):
        async with AsyncSessionLocal() as s:
            sale = await sales_service.create_sale(s, SaleCreate(
                warehouse_id=env["warehouse_id"], shift_id=env["shift_id"], customer_id=env["customer_id"], is_credit=True,
                payment_method="credit", items=[SaleItemCreate(product_id=env["product_id"], qty=D(qty), unit_price=D("100"))]),
                env["cashier_id"])
            ids.append(sale.id)
    later = datetime.now(UTC) + timedelta(days=2)
    await _sql(env, "INSERT INTO customer_payments (id, tenant_id, customer_id, sale_id, amount, created_at) "
                    "VALUES (:id, :t, :c, :s, 40, :at)", id=uuid.uuid4(), t=t, c=env["customer_id"], s=ids[0], at=later)
    await _sql(env, "UPDATE sales SET paid_amount = COALESCE(paid_amount, 0) + 40 WHERE id = :s", s=ids[0])
    # A supplier: 300 forty-five days ago, 500 ten days ago, 600 paid today (the oldest first).
    sup = uuid.uuid4()
    await _sql(env, "INSERT INTO suppliers (id, tenant_id, name, balance) VALUES (:id, :t, 'مورد', 200)", id=sup, t=t)
    now = datetime.now(UTC)
    for kind, amount, ago in (("debit", 300, 45), ("debit", 500, 10), ("credit", 600, 0)):
        await _sql(env, "INSERT INTO supplier_transactions (id, tenant_id, supplier_id, type, amount, created_at) "
                        "VALUES (:id, :t, :s, :k, :a, :at)", id=uuid.uuid4(), t=t, s=sup, k=kind, a=amount,
                   at=now - timedelta(days=ago))

    h = _auth(u["manager"], t)
    async with _client() as c:
        now_view = (await c.get("/reports/aging", headers=h)).json()
        later_view = (await c.get("/reports/aging", params={"as_of": (today() + timedelta(days=3)).isoformat()}, headers=h)).json()
        yesterday = (await c.get("/reports/aging", params={"as_of": (today() - timedelta(days=1)).isoformat()}, headers=h)).json()
        monkeypatch.setattr(report_service, "INVOICES_PER_CUSTOMER", 1)
        capped = (await c.get("/reports/aging", headers=h)).json()

    cust = now_view["customers"]
    assert cust["totals"]["total"] == "300.00" and cust["items"][0]["buckets"]["0-30"] == "300.00"
    assert sorted(i["remaining"] for i in cust["items"][0]["invoices"]) == ["100.00", "200.00"]
    assert later_view["customers"]["totals"]["total"] == "260.00"
    assert yesterday["customers"]["totals"]["total"] == "0.00"  # the invoices came today
    supp = {i["name"]: i for i in now_view["suppliers"]["items"]}["مورد"]
    assert (supp["total_debt"], supp["buckets"]["0-30"], supp["buckets"]["30-60"]) == ("200.00", "200.00", "0.00")
    before = {i["name"]: i for i in yesterday["suppliers"]["items"]}["مورد"]
    assert (before["total_debt"], before["buckets"]["0-30"], before["buckets"]["30-60"]) == ("800.00", "500.00", "300.00")
    # A listed customer shows a bounded number of invoices; the debt still covers all of them.
    assert len(capped["customers"]["items"][0]["invoices"]) == 1 and capped["customers"]["items"][0]["total_debt"] == "300.00"


# ── REP-12 ───────────────────────────────────────────────────────────────────────────────────

async def test_exports_keep_their_header_and_speak_arabic():
    """Old code: an export with no rows was a blank sheet; payment methods were English codes."""
    import openpyxl

    env = await _scenario()
    h = _auth(env["users"]["manager"], env["tenant_id"])
    async with _client() as c:
        r = await c.get("/export/expenses", params={"from_date": "2001-01-01", "to_date": "2001-01-31"}, headers=h)
        ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
        assert [cell.value for cell in ws[1]][:3] == ["التاريخ", "البيان", "المبلغ"] and ws.max_row == 1
        r = await c.get("/export/sales", params=_range(), headers=h)
        ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
        headers = [cell.value for cell in ws[1]]
        methods = {row[headers.index("طريقة الدفع")] for row in ws.iter_rows(min_row=2, values_only=True)}
        assert methods == {"نقدي"}
        assert "ضريبة القيمة المضافة" in headers
