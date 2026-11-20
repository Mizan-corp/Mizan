"""The reports (reporting module, production readiness REP-1..7, REP-11).

- Permissions: every report needs `reports` (today's sales widget: `reports` or `pos`); profit, cash
  flow, aging and the company overview need `reports:finance`, which a cashier doesn't hold.
- Branches: a user who doesn't supervise sees only their branches when no branch is picked, and
  gets a 403 for another branch.
- Date ranges include their last day, in the workspace's time zone (Africa/Cairo).
- Sales figures are net of returns and of the invoice discount; profit includes approved expenses
  (payroll's too) and the drawer's expenses, and equals the income statement when accounting is on.
- Top products: confirmed sales less returns, with the field names the screen reads.
- Inventory print: print token, HTML with escaped names, 404 for an unknown branch.
- Bad input is a 4xx.
- Money comes back as decimal strings (REP-15): `n()` reads them.
"""
import io
import os
import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from main import app
from sqlalchemy import text

from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement
from app.activities.general.modules.pos import service as pos_service
from app.activities.general.modules.pos.models import DrawerTxType, Shift
from app.activities.general.modules.reporting import service as report_service
from app.activities.general.modules.reporting.scope import TZ, today
from app.activities.general.modules.sales.schemas import SaleCreate, SaleItemCreate
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


def n(v) -> Decimal:
    """A money figure of an answer (a decimal string) or of the ledger (a float), as a Decimal."""
    return D(str(v))


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _token(user_id, tenant_id, **extra) -> str:
    return create_access_token({"sub": str(user_id), "tid": str(tenant_id), **extra})


def _auth(user_id, tenant_id) -> dict:
    return {"Authorization": "Bearer " + _token(user_id, tenant_id)}


async def _sql(env: dict, sql: str, **params):
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        result = await s.execute(text(sql), params)
        rows = result.all() if result.returns_rows else None
        await s.commit()
        return rows


def _sale(env, warehouse_id, shift_id, qty="1", discount="0") -> SaleCreate:
    return SaleCreate(warehouse_id=warehouse_id, shift_id=shift_id, discount_amount=D(discount),
                      items=[SaleItemCreate(product_id=env["product_id"], qty=D(qty), unit_price=D("100"))])


async def _scenario(accounting: bool = False) -> dict:
    """Two branches. Branch 1 (the cashier's): a sale of 2 at 100 with 20 off the invoice (180) and a
    sale of 1 (100) returned the same day; a drawer expense of 10. Branch 2: a sale of 3 (300).
    Approved company expenses: 50 (rent) and 30 (the month's salaries). Cost 60 a unit.
    Users: a manager (supervises), a cashier on branch 1 (pos, no reports) and a branch-1 clerk with
    `reports` only (no supervise, no reports:finance)."""
    env = await _env(accounting=accounting)
    t = env["tenant_id"]
    wh2 = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Warehouse(id=wh2, tenant_id=t, code=f"W2-{t.hex[:4]}", name="فرع المعادي", is_active=True))
        users = {}
        for key, role, perms in (("manager", "manager", standard_permissions("manager")),
                                 ("cashier", "cashier", standard_permissions("cashier")),
                                 ("clerk", "cashier", [*standard_permissions("cashier"), "reports"])):
            u = User(id=uuid.uuid4(), tenant_id=t, username=f"{key}_{t.hex[:8]}", full_name=key, role=role,
                     password_hash=hash_password("Pass12345!"), permissions=perms, is_active=True,
                     is_manager=key == "manager")
            s.add(u)
            users[key] = u.id
        await s.flush()
        for key in ("cashier", "clerk"):
            await s.execute(user_warehouses.insert().values(user_id=users[key], warehouse_id=env["warehouse_id"]))
        await give_roles(s)
        shift2 = Shift(id=uuid.uuid4(), tenant_id=t, cashier_id=users["manager"], warehouse_id=wh2, status="open",
                       initial_amount=D("0"), started_at=datetime.now(UTC))
        s.add(shift2)
        await s.commit()
    current_tenant_id.set(t)
    async with AsyncSessionLocal() as s:
        await apply_movement(s, product_id=env["product_id"], warehouse_id=wh2, movement_type=MovementType.opening_stock,
                             qty=D("50"), unit_cost=D("60"), created_by=env["cashier_id"])
        await s.commit()
    wh1, shift1 = env["warehouse_id"], env["shift_id"]
    async with AsyncSessionLocal() as s:
        await sales_service.create_sale(s, _sale(env, wh1, shift1, qty="2", discount="20"), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        returned = (await sales_service.create_sale(s, _sale(env, wh1, shift1, qty="1"), env["cashier_id"])).id
    async with AsyncSessionLocal() as s:
        await sales_service.partial_return_sale(s, returned, {"items": [{"product_id": env["product_id"], "qty": 1}]},
                                                env["cashier_id"])
    async with AsyncSessionLocal() as s:
        await sales_service.create_sale(s, _sale(env, wh2, shift2.id, qty="3"), users["manager"])
    async with AsyncSessionLocal() as s:
        await pos_service.add_transaction(s, shift1, DrawerTxType.expense, D("10"), env["cashier_id"], note="شاي")
    for amount, method, notes in (("50", "cash", None), ("30", "payroll", "HR payroll month test")):
        await _sql(env, "INSERT INTO expenses (id, tenant_id, amount, description, date, status, payment_method, notes) "
                        "VALUES (:id, :t, :a, 'مصروف', :d, 'approved', :m, :n)",
                   id=uuid.uuid4(), t=t, a=D(amount), d=today(), m=method, n=notes)
    env.update(warehouse2_id=wh2, shift2_id=shift2.id, users=users, returned_sale=returned)
    return env


def _range(**extra) -> dict:
    d = today().isoformat()
    return {"from_date": d, "to_date": d, **extra}


async def test_profit_needs_the_finance_permission_and_counts_the_last_day():
    """Fails on the old code: a cashier read the profit, and from=to=today returned zeros."""
    env = await _scenario()
    t, u = env["tenant_id"], env["users"]
    async with _client() as c:
        assert (await c.get("/reports/profit", params=_range(), headers=_auth(u["cashier"], t))).status_code == 403
        assert (await c.get("/reports/profit", params=_range(), headers=_auth(u["clerk"], t))).status_code == 403
        for path in ("/reports/cash-flow", "/reports/aging", "/admin/overview"):
            r = await c.get(path, params=_range() if path == "/reports/cash-flow" else None, headers=_auth(u["clerk"], t))
            assert r.status_code == 403, path
        r = await c.get("/reports/profit", params=_range(), headers=_auth(u["manager"], t))
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["source"] == "operations"
    assert p["total_revenue"] == "580.00"  # 180 + 100 + 300, after the invoice discount
    assert p["total_returns"] == "100.00"
    assert p["net_revenue"] == "480.00"
    assert p["total_cogs"] == "300.00"  # (2 + 1 + 3 - 1) × 60
    assert p["gross_profit"] == "180.00"
    assert p["total_expenses"] == "90.00"  # rent 50 + salaries 30 + the drawer's 10
    assert p["net_profit"] == "90.00"


async def test_sales_reports_are_net_of_returns_and_limited_to_the_users_branches():
    """Fails on the old code: no returns taken off, the whole company shown to a branch clerk, the
    last day of a range dropped."""
    env = await _scenario()
    t, u = env["tenant_id"], env["users"]
    async with _client() as c:
        mgr, clerk, cashier = _auth(u["manager"], t), _auth(u["clerk"], t), _auth(u["cashier"], t)
        daily = (await c.get("/reports/sales/daily", headers=mgr)).json()
        assert (daily["total_sales"], daily["gross_sales"], daily["returns_total"], daily["invoice_count"]) == ("480.00", "580.00", "100.00", 3)
        assert daily["total_items"] == 5.0
        # The cashier's widget (pos) and the clerk (reports): their branch only.
        for h in (cashier, clerk):
            mine = (await c.get("/reports/sales/daily", headers=h)).json()
            assert mine["total_sales"] == "180.00" and mine["invoice_count"] == 2
            trend = (await c.get("/reports/sales/trend", params={"days": 3}, headers=h)).json()
            assert trend[-1] == {"date": today().isoformat(), "total_sales": "180.00", "invoice_count": 2}
        assert (await c.get("/reports/sales/daily", params={"warehouse_id": str(env["warehouse2_id"])},
                            headers=clerk)).status_code == 403
        # The cashier holds pos, not reports: the other reports are closed to them.
        assert (await c.get("/reports/sales/by-cashier", params=_range(), headers=cashier)).status_code == 403

        month = (await c.get("/reports/sales/monthly", params={"year": today().year, "month": today().month},
                             headers=clerk)).json()
        assert month["total_sales"] == "180.00"

        rows = (await c.get("/reports/sales/by-cashier", params=_range(), headers=mgr)).json()
        by_name = {r["cashier_name"]: r for r in rows}
        assert by_name["manager"]["total_sales"] == "300.00"
        cashier_row = next(r for r in rows if r["cashier_id"] == str(env["cashier_id"]))
        assert (cashier_row["gross_sales"], cashier_row["returns_total"], cashier_row["total_sales"]) == ("280.00", "100.00", "180.00")
        assert sum(n(r["total_sales"]) for r in rows) == 480

        top = (await c.get("/reports/sales/top-products", params=_range(limit=5), headers=mgr)).json()
        assert top == [{"product_id": str(env["product_id"]), "product_name": "صنف", "unit": top[0]["unit"],
                        "qty": 5.0, "revenue": "480.00"}]
        top1 = (await c.get("/reports/sales/top-products", params=_range(), headers=clerk)).json()
        assert top1[0]["qty"] == 2.0 and top1[0]["revenue"] == "180.00"

        p = (await c.get("/reports/ledger/daily-items", headers=clerk)).json()
        assert [(i["qty"], i["total"], i["returns"]) for i in p["items"]] == [(3.0, "280.00", "100.00")]
        assert p["expenses"] == [{"note": "شاي", "total": "10.00"}]
        periodic = (await c.get("/reports/ledger/periodic", params={"period": "monthly"}, headers=mgr)).json()
        assert (periodic[0]["income"], periodic[0]["returns"], periodic[0]["expenses"]) == ("580.00", "100.00", "90.00")


async def test_a_branch_profit_leaves_out_company_expenses():
    env = await _scenario()
    t, u = env["tenant_id"], env["users"]
    async with _client() as c:
        r = await c.get("/reports/profit", params=_range(warehouse_id=str(env["warehouse_id"])), headers=_auth(u["manager"], t))
    p = r.json()
    assert (p["net_revenue"], p["total_cogs"], p["gross_profit"], p["total_expenses"], p["net_profit"]) == (
        "180.00", "120.00", "60.00", "10.00", "50.00")


async def test_day_boundaries_are_in_cairo_time():
    """A sale at 23:30 Cairo time belongs to that day (21:30 UTC in winter, which UTC midnight
    boundaries already count as the same day; 00:30 Cairo is the previous UTC day)."""
    env = await _scenario()
    t, u = env["tenant_id"], env["users"]
    day = today() - timedelta(days=3)
    early = datetime.combine(day, time(0, 30), tzinfo=TZ)  # the UTC date is the day before
    await _sql(env, "UPDATE sales SET created_at = :at WHERE warehouse_id = :wh", at=early, wh=env["warehouse2_id"])
    async with _client() as c:
        mgr = _auth(u["manager"], t)
        on_day = (await c.get("/reports/sales/daily", params={"target_date": day.isoformat()}, headers=mgr)).json()
        before = (await c.get("/reports/sales/daily", params={"target_date": (day - timedelta(days=1)).isoformat()},
                              headers=mgr)).json()
        trend = (await c.get("/reports/sales/trend", params={"days": 7}, headers=mgr)).json()
    assert on_day["total_sales"] == "300.00"
    assert before["total_sales"] == "0.00"
    assert next(x for x in trend if x["date"] == day.isoformat())["total_sales"] == "300.00"


async def test_profit_matches_the_income_statement_when_accounting_is_on():
    from app.activities.general.modules.accounting.services import reports as acc_reports

    env = await _scenario(accounting=True)
    t, u = env["tenant_id"], env["users"]
    async with _client() as c:
        r = await c.get("/reports/profit", params=_range(), headers=_auth(u["manager"], t))
        r1 = await c.get("/reports/profit", params=_range(warehouse_id=str(env["warehouse_id"])), headers=_auth(u["manager"], t))
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["source"] == "ledger"
    async with AsyncSessionLocal() as s:
        stmt = await acc_reports.income_statement(s, t, today(), today())
        branch = await acc_reports.income_statement(s, t, today(), today(), env["warehouse_id"])
        await s.commit()
    assert n(p["net_profit"]) == n(stmt["net_profit"])
    assert n(p["gross_profit"]) == n(stmt["gross_profit"])
    assert n(p["net_revenue"]) == n(stmt["net_sales"])
    assert n(r1.json()["net_profit"]) == n(branch["net_profit"])
    # Same documents, so the same sales figures as the operational path.
    assert p["net_revenue"] == "480.00" and p["total_cogs"] == "300.00"


async def test_revenue_is_net_of_vat_when_documents_carry_it():
    env = await _scenario()
    async with AsyncSessionLocal() as s:
        if not await report_service.has_column(s, "sales", "tax_amount"):
            pytest.skip("this database has no VAT columns yet (ADR-014 step 6)")
    await _sql(env, "UPDATE sales SET tax_amount = 36.84 WHERE warehouse_id = :wh", wh=env["warehouse2_id"])
    async with _client() as c:
        p = (await c.get("/reports/profit", params=_range(), headers=_auth(env["users"]["manager"], env["tenant_id"]))).json()
        d = (await c.get("/reports/sales/daily", headers=_auth(env["users"]["manager"], env["tenant_id"]))).json()
    assert p["total_revenue"] == "543.16"
    assert d["total_sales"] == "443.16" and d["tax_total"] == "36.84"


async def test_inventory_print_renders_html_with_a_print_token():
    """Fails on the old code: a print token got a 401 and the answer was JSON."""
    env = await _scenario()
    t, u = env["tenant_id"], env["users"]
    await _sql(env, "UPDATE warehouses SET name = '<b>فرع</b>' WHERE id = :id", id=env["warehouse_id"])
    await _sql(env, "UPDATE products SET name = '<script>x</script>' WHERE id = :id", id=env["product_id"])
    async with _client() as c:
        tok = _token(u["manager"], t, scope="print")
        r = await c.get("/reports/inventory/print", params={"warehouse_id": str(env["warehouse_id"]), "token": tok})
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/html")
        assert "&lt;b&gt;فرع&lt;/b&gt;" in r.text and "<b>فرع" not in r.text
        assert "&lt;script&gt;" in r.text and "<script>x" not in r.text
        assert "سعر التكلفة" in r.text
        # A clerk with `reports` prints their branch without costs, not another branch.
        tok = _token(u["clerk"], t, scope="print")
        r = await c.get("/reports/inventory/print", params={"warehouse_id": str(env["warehouse_id"]), "token": tok})
        assert r.status_code == 200 and "سعر التكلفة" not in r.text
        r = await c.get("/reports/inventory/print", params={"warehouse_id": str(env["warehouse2_id"]), "token": tok})
        assert r.status_code == 403
        tok = _token(u["manager"], t, scope="print")
        r = await c.get("/reports/inventory/print", params={"warehouse_id": str(uuid.uuid4()), "token": tok})
        assert r.status_code == 404
        # The cashier holds neither reports nor inventory.
        r = await c.get("/reports/inventory/print", params={"warehouse_id": str(env["warehouse_id"]),
                                                            "token": _token(u["cashier"], t, scope="print")})
        assert r.status_code == 403
        # A session token is not a print token.
        r = await c.get("/reports/inventory/print", params={"warehouse_id": str(env["warehouse_id"])},
                        headers=_auth(u["manager"], t))
        assert r.status_code in (401, 403)


async def test_bad_input_is_a_4xx():
    """Fails on the old code: string ids and dates, month 13 and a negative limit were 500s."""
    env = await _scenario()
    h = _auth(env["users"]["manager"], env["tenant_id"])
    async with _client() as c:
        for path, params in (
            ("/reports/sales/monthly", {"year": 2026, "month": 13}),
            ("/reports/sales/top-products", {**_range(), "limit": -1}),
            ("/reports/sales/top-products", {"from_date": "x", "to_date": "y"}),
            ("/reports/sales/daily", {"warehouse_id": "abc"}),
            ("/reports/profit", {"from_date": "2026-01-01", "to_date": "nope"}),
            ("/reports/ledger/periodic", {"period": "daily"}),
            ("/reports/aging", {"as_of": "soon"}),
            ("/export/sales", {"from_date": "x"}),
        ):
            r = await c.get(path, params=params, headers=h)
            assert r.status_code == 422, (path, r.status_code, r.text[:200])
        r = await c.get("/reports/profit", params={"from_date": "2026-02-01", "to_date": "2026-01-01"}, headers=h)
        assert r.status_code == 400 and "تاريخ" in r.json()["detail"]
        r = await c.get("/reports/sales/daily", params={"warehouse_id": str(uuid.uuid4())}, headers=h)
        assert r.status_code == 404


async def test_cash_flow_aging_and_overview():
    env = await _scenario()
    t, u = env["tenant_id"], env["users"]
    h = _auth(u["manager"], t)
    async with _client() as c:
        cf = (await c.get("/reports/cash-flow", params=_range(), headers=h)).json()
        aging = await c.get("/reports/aging", headers=h)
        overview = (await c.get("/admin/overview", headers=h)).json()
    # Paid sales 580; refund 100; expenses 50 + the drawer's 10 (salaries are counted when paid).
    assert cf["source"] == "operations"
    assert cf["incoming"]["cash_sales"] == "580.00"
    assert cf["outgoing"]["returns_to_customers"] == "100.00"
    assert cf["outgoing"]["expenses"] == "60.00"
    assert cf["outgoing"]["payroll"] == "0.00"
    assert cf["net_cash_flow"] == "420.00"
    lines = {x["key"]: (x["in"], x["out"]) for x in cf["lines"]}
    assert lines["sale"] == ("580.00", "0.00") and lines["sale_return"] == ("0.00", "100.00")
    assert lines["expense"] == ("0.00", "50.00") and lines["drawer_tx"] == ("0.00", "10.00")
    assert aging.status_code == 200 and aging.json()["customers"]["totals"]["total"] == "0.00"
    assert overview["summary"]["total_revenue"] == "480.00"
    assert overview["summary"]["total_profit"] == "180.00"
    assert n(overview["summary"]["total_stock_cost"]) == (100 - 5) * 60


async def test_exports_take_dates_and_write_numbers():
    import openpyxl

    env = await _scenario()
    t, u = env["tenant_id"], env["users"]
    async with _client() as c:
        r = await c.get("/export/sales", params=_range(), headers=_auth(u["manager"], t))
        assert r.status_code == 200, r.text
        ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
        headers = [cell.value for cell in ws[1]]
        assert "رقم الفاتورة" in headers and "الصافي" in headers
        nets = [row[headers.index("الصافي")] for row in ws.iter_rows(min_row=2, values_only=True)]
        assert sorted(nets) == [100.0, 100.0, 180.0, 300.0]
        # The clerk's export is their branch only.
        r = await c.get("/export/sales", params=_range(), headers=_auth(u["clerk"], t))
        ws = openpyxl.load_workbook(io.BytesIO(r.content)).active
        assert ws.max_row - 1 == 3
        # Stock export: costs only with reports:finance.
        r = await c.get("/export/stock", headers=_auth(u["manager"], t))
        assert "قيمة المخزون بالتكلفة" in [cell.value for cell in openpyxl.load_workbook(io.BytesIO(r.content)).active[1]]


async def test_reports_are_isolated_per_workspace():
    a = await _scenario()
    b = await _scenario()
    async with _client() as c:
        r = await c.get("/reports/sales/daily", params={"warehouse_id": str(b["warehouse_id"])},
                        headers=_auth(a["users"]["manager"], a["tenant_id"]))
        assert r.status_code == 404
        r = await c.get("/reports/profit", params=_range(), headers=_auth(a["users"]["manager"], a["tenant_id"]))
        assert r.json()["net_revenue"] == "480.00"
