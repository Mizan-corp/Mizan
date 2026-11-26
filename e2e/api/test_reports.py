"""reports module: sales reports (net of returns and discounts), profit, top products, by cashier,
inventory print (print token, HTML), daily and periodic ledger, cash flow, aging, admin overview,
permissions and bad input. Each test sells in its own new branch, so the figures are exact.
(`/reports/ledger` is the finance module's cash ledger, not a report of this module.)"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from conftest import admin_api, cashier_api, ensure_shift, owner_api, product, wh  # noqa: F401


def _today() -> str:
    # The reports bucket sales by the workspace clock (Africa/Cairo, tenancy/clock.py),
    # not the runner's: after 22:00 UTC Cairo is already on the next day, so a UTC
    # date.today() here queried yesterday's lines and missed tonight's sales.
    return datetime.now(ZoneInfo("Africa/Cairo")).date().isoformat()


def _sell(api, reg, product, wh, qty: int, discount: str = "0") -> dict:
    s = api.ok(api.post("/sales", json={
        "warehouse_id": wh["id"], "discount_amount": discount,
        "items": [{"product_id": product["id"], "qty": qty, "unit_price": "100", "unit_cost": "70", "discount": "0"}],
    }))
    reg.add("sale", s["id"])
    return s


def _scenario(api, reg, product, wh) -> None:
    """In the branch: 2 × 100 with 20 off the invoice (180), and 1 × 100 returned (net 0)."""
    ensure_shift(api, reg, wh["id"])  # cash goes into the seller's open shift in the branch
    _sell(api, reg, product, wh, 2, "20")
    s = _sell(api, reg, product, wh, 1)
    api.ok(api.post(f"/sales/{s['id']}/partial-return", json={"items": [{"product_id": product["id"], "qty": 1}]}))


def test_sales_reports_figures(admin_api, owner_api, reg, product, wh):
    _scenario(admin_api, reg, product, wh)
    p = {"warehouse_id": wh["id"]}
    daily = owner_api.ok(owner_api.get("/reports/sales/daily", params=p))
    # Money comes as decimal strings (REP-15).
    assert (daily["total_sales"], daily["gross_sales"], daily["returns_total"], daily["invoice_count"]) == ("180.00", "280.00", "100.00", 2)

    today = date.today()
    monthly = owner_api.ok(owner_api.get("/reports/sales/monthly", params={**p, "year": today.year, "month": today.month}))
    assert monthly["total_sales"] == "180.00"

    trend = owner_api.ok(owner_api.get("/reports/sales/trend", params={**p, "days": 2}))
    assert trend[-1]["date"] == _today() and trend[-1]["total_sales"] == "180.00"

    rng = {**p, "from_date": _today(), "to_date": _today()}
    top = owner_api.ok(owner_api.get("/reports/sales/top-products", params=rng))
    assert [(t["product_id"], t["qty"], t["revenue"]) for t in top] == [(product["id"], 2, "180.00")]

    rows = owner_api.ok(owner_api.get("/reports/sales/by-cashier", params=rng))
    assert sum(float(r["total_sales"]) for r in rows) == 180

    profit = owner_api.ok(owner_api.get("/reports/profit", params=rng))
    assert profit["net_revenue"] == "180.00" and profit["total_returns"] == "100.00"
    assert float(profit["gross_profit"]) == round(float(profit["net_revenue"]) - float(profit["total_cogs"]), 2)
    assert profit["source"] in ("ledger", "operations")


def test_inventory_print_with_a_print_token(owner_api, wh):
    token = owner_api.ok(owner_api.post("/auth/print-token", json={}))["token"]
    r = owner_api.client.get("/reports/inventory/print", params={"warehouse_id": wh["id"], "token": token})
    assert r.status_code == 200, r.text[:300]
    assert r.headers["content-type"].startswith("text/html")
    assert wh["name"] in r.text
    token = owner_api.ok(owner_api.post("/auth/print-token", json={}))["token"]
    r = owner_api.client.get("/reports/inventory/print",
                             params={"warehouse_id": "00000000-0000-0000-0000-000000000000", "token": token})
    assert r.status_code == 404


def test_ledger_reports(admin_api, owner_api, reg, product, wh):
    _scenario(admin_api, reg, product, wh)
    items = owner_api.ok(owner_api.get("/reports/ledger/daily-items", params={"warehouse_id": wh["id"]}))
    assert [(i["qty"], i["total"], i["returns"]) for i in items["items"]] == [(3, "280.00", "100.00")]
    periodic = owner_api.ok(owner_api.get("/reports/ledger/periodic", params={"warehouse_id": wh["id"], "period": "monthly"}))
    assert periodic[0]["income"] == "280.00" and periodic[0]["returns"] == "100.00"


def test_cash_flow_aging_and_overview(admin_api, owner_api, reg, product, wh):
    _scenario(admin_api, reg, product, wh)
    cf = owner_api.ok(owner_api.get("/reports/cash-flow",
                                    params={"warehouse_id": wh["id"], "from_date": _today(), "to_date": _today()}))
    # From the ledger's money accounts or the documents, the same lines (REP-8).
    lines = {x["key"]: (float(x["in"]), float(x["out"])) for x in cf["lines"]}
    assert cf["source"] in ("ledger", "operations")
    assert lines["sale"] == (280, 0) and lines["sale_return"] == (0, 100)
    aging = owner_api.ok(owner_api.get("/reports/aging"))
    assert set(aging) >= {"as_of", "customers", "suppliers"}
    overview = owner_api.ok(owner_api.get("/admin/overview"))
    branch = next(b for b in overview["branches"] if b["id"] == wh["id"])
    assert branch["revenue"] == "180.00" and branch["invoice_count"] == 2


def test_permissions(cashier_api):
    rng = {"from_date": _today(), "to_date": _today()}
    for path, params in (("/reports/profit", rng), ("/reports/cash-flow", rng), ("/reports/aging", None),
                         ("/admin/overview", None), ("/reports/sales/by-cashier", rng), ("/reports/sales/top-products", rng)):
        assert cashier_api.get(path, params=params).status_code == 403, path
    # The dashboard's "today's revenue" widget is open to cashiers (their own branches).
    assert cashier_api.get("/reports/sales/daily").status_code == 200


def test_bad_input_is_4xx(owner_api):
    assert owner_api.get("/reports/sales/monthly", params={"year": 2026, "month": 13}).status_code == 422
    assert owner_api.get("/reports/sales/top-products",
                         params={"from_date": _today(), "to_date": _today(), "limit": -1}).status_code == 422
    assert owner_api.get("/reports/profit", params={"from_date": "x", "to_date": "y"}).status_code == 422
    assert owner_api.get("/reports/sales/daily", params={"warehouse_id": "abc"}).status_code == 422
    r = owner_api.get("/reports/profit", params={"from_date": "2026-02-01", "to_date": "2026-01-01"})
    assert r.status_code == 400
