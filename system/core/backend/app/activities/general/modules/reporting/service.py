"""The reports. Every query runs while the workspace is bound (RLS) and takes a branch scope
(`scope.py`) and whole days in the workspace's time zone.

Sales figures (ADR-014 D4):
- A document's value is its `net_total` (after line and invoice discounts) less its VAT when the
  documents carry VAT (`sales.tax_amount`, ADR-014 D6; `_vat_sql`). Sales are the confirmed
  documents; returns are the return documents (`status = 'returned'` with `return_of`), dated when
  they were made, and are taken off. Old full returns (the sale itself marked `returned`, before
  D4) are neither a sale nor a return, as their totals already cancel out.
- Per line (top products, the daily items): the line's value after its own discount and its share
  of the invoice discount, or the stored `sale_items.net_amount` (without VAT) when there is one.

Profit: from the ledger when the workspace has the accounting module and the ledger covers the
period (the same figures as the income statement), otherwise from the documents (see
`_profit_from_operations`).
"""
import calendar
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.reporting.scope import TZ_NAME, Scope, day_range, day_start, today

D = Decimal
ZERO = D("0")
CENT = D("0.01")

DOCS = "(s.status = 'confirmed' OR (s.status = 'returned' AND s.return_of IS NOT NULL))"
SIGN = "(CASE WHEN s.status = 'confirmed' THEN 1 ELSE -1 END)"
LOCAL_DAY = f"(s.created_at AT TIME ZONE '{TZ_NAME}')::date"


def money(v) -> str:
    """Money in an answer: a decimal string rounded to the piastre ("1234.50"), never a float (REP-15)."""
    return str(D(str(v or 0)).quantize(CENT, rounding=ROUND_HALF_UP))


def qty(v) -> float:
    return float(D(str(v or 0)))


# ── VAT columns (ADR-014 D6) ──────────────────────────────────────────────────────────────────
# Step 6 adds sales.tax_amount, sale_items.net_amount and expenses.tax_amount. Until those columns
# exist the documents hold no VAT and their totals are used as they are.

_present: set[str] = set()


async def has_column(db: AsyncSession, table: str, column: str) -> bool:
    key = f"{table}.{column}"
    if key in _present:
        return True
    found = (await db.execute(text(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() "
        "AND table_name = :t AND column_name = :c"), {"t": table, "c": column})).first() is not None
    if found:
        _present.add(key)
    return found


async def _vat_sql(db: AsyncSession) -> dict[str, str]:
    """SQL for a sale document's value and VAT (alias `s`), a line's value (alias `si`) and an
    expense's amount without VAT (alias `e`)."""
    doc_tax = "COALESCE(s.tax_amount, 0)" if await has_column(db, "sales", "tax_amount") else "0"
    base = "(si.qty * si.unit_price - COALESCE(si.discount, 0))"
    shared = (f"(CASE WHEN SUM({base}) OVER (PARTITION BY s.id) = 0 THEN 0 ELSE {base} - "
              f"COALESCE(s.discount_amount, 0) * {base} / SUM({base}) OVER (PARTITION BY s.id) END)")
    line = f"COALESCE(si.net_amount, {shared})" if await has_column(db, "sale_items", "net_amount") else shared
    exp_tax = "COALESCE(e.tax_amount, 0)" if await has_column(db, "expenses", "tax_amount") else "0"
    return {"doc_tax": doc_tax, "doc": f"(COALESCE(s.net_total, 0) - {doc_tax})", "line": line,
            "expense": f"(e.amount - {exp_tax})"}


async def _lines_cte(db: AsyncSession, scope: Scope, params: dict) -> str:
    """The lines of the sales and returns made in [:start, :end): sign, qty, cost and value."""
    v = await _vat_sql(db)
    return f"""lines AS (
        SELECT s.id AS sale_id, s.cashier_id, si.product_id, si.unit_price, {SIGN} AS sign, si.qty,
               si.qty * COALESCE(si.unit_cost, 0) AS cost, {v['line']} AS value
        FROM sale_items si JOIN sales s ON s.id = si.sale_id
        WHERE {DOCS} AND s.created_at >= :start AND s.created_at < :end{scope.sql('s.warehouse_id', params)}
    )"""


# ── sales ─────────────────────────────────────────────────────────────────────────────────────

async def _sales_totals(db: AsyncSession, start: datetime, end: datetime, scope: Scope) -> dict:
    v = await _vat_sql(db)
    params: dict = {"start": start, "end": end}
    row = (await db.execute(text(f"""
        SELECT COUNT(*) FILTER (WHERE s.status = 'confirmed') AS invoices,
               COUNT(*) FILTER (WHERE s.status = 'returned') AS returns,
               COALESCE(SUM({v['doc']}) FILTER (WHERE s.status = 'confirmed'), 0) AS sales,
               COALESCE(SUM({v['doc']}) FILTER (WHERE s.status = 'returned'), 0) AS returned,
               COALESCE(SUM({SIGN} * {v['doc_tax']}), 0) AS tax
        FROM sales s
        WHERE {DOCS} AND s.created_at >= :start AND s.created_at < :end{scope.sql('s.warehouse_id', params)}
    """), params)).one()
    return {"total_sales": money(row.sales - row.returned), "gross_sales": money(row.sales),
            "returns_total": money(row.returned), "tax_total": money(row.tax),
            "invoice_count": row.invoices, "returns_count": row.returns, "warehouse_ids": scope.out()}


async def daily_sales(db: AsyncSession, target_date: date, scope: Scope) -> dict:
    start, end = day_range(target_date, target_date)
    out = await _sales_totals(db, start, end, scope)
    params: dict = {"start": start, "end": end}
    items = (await db.execute(text(f"""
        SELECT COALESCE(SUM({SIGN} * si.qty), 0) FROM sale_items si JOIN sales s ON s.id = si.sale_id
        WHERE {DOCS} AND s.created_at >= :start AND s.created_at < :end{scope.sql('s.warehouse_id', params)}
    """), params)).scalar_one()
    return {"date": target_date.isoformat(), **out, "total_items": qty(items)}


async def sales_trend(db: AsyncSession, days: int, scope: Scope) -> list[dict]:
    """Net sales (less returns) per day for the last `days` days, oldest first, zero days included."""
    last = today()
    first = last - timedelta(days=days - 1)
    v = await _vat_sql(db)
    params: dict = {"start": day_start(first), "end": day_start(last + timedelta(days=1))}
    rows = (await db.execute(text(f"""
        SELECT {LOCAL_DAY} AS day, COALESCE(SUM({SIGN} * {v['doc']}), 0) AS total,
               COUNT(*) FILTER (WHERE s.status = 'confirmed') AS invoices
        FROM sales s
        WHERE {DOCS} AND s.created_at >= :start AND s.created_at < :end{scope.sql('s.warehouse_id', params)}
        GROUP BY 1
    """), params)).all()
    by_day = {r.day: (r.total, r.invoices) for r in rows}
    out = []
    for i in range(days):
        d = first + timedelta(days=i)
        total, count = by_day.get(d, (ZERO, 0))
        out.append({"date": d.isoformat(), "total_sales": money(total), "invoice_count": count})
    return out


async def monthly_sales(db: AsyncSession, year: int, month: int, scope: Scope) -> dict:
    last_day = calendar.monthrange(year, month)[1]
    start, end = day_range(date(year, month, 1), date(year, month, last_day))
    return {"year": year, "month": month, **await _sales_totals(db, start, end, scope)}


async def top_products(db: AsyncSession, date_from: date, date_to: date, scope: Scope, limit: int = 10) -> list[dict]:
    """Products by net revenue in the period: sold less returned, quantity and value."""
    start, end = day_range(date_from, date_to)
    params: dict = {"start": start, "end": end, "lim": limit}
    cte = await _lines_cte(db, scope, params)
    rows = (await db.execute(text(f"""
        WITH {cte}
        SELECT p.id, p.name, p.unit, SUM(l.sign * l.qty) AS qty, SUM(l.sign * l.value) AS revenue
        FROM lines l JOIN products p ON p.id = l.product_id
        GROUP BY p.id, p.name, p.unit
        HAVING SUM(l.sign * l.qty) <> 0 OR SUM(l.sign * l.value) <> 0
        ORDER BY revenue DESC, p.name
        LIMIT :lim
    """), params)).all()
    return [{"product_id": str(r.id), "product_name": r.name, "unit": r.unit, "qty": qty(r.qty),
             "revenue": money(r.revenue)} for r in rows]


async def sales_by_cashier(db: AsyncSession, date_from: date, date_to: date, scope: Scope) -> list[dict[str, Any]]:
    """Per cashier: their invoices' value after every discount, less the returns they made, so the
    rows add up to the period's net sales."""
    start, end = day_range(date_from, date_to)
    v = await _vat_sql(db)
    params: dict = {"start": start, "end": end}
    rows = (await db.execute(text(f"""
        SELECT u.id, u.full_name,
               COUNT(*) FILTER (WHERE s.status = 'confirmed') AS invoices,
               COALESCE(SUM({v['doc']}) FILTER (WHERE s.status = 'confirmed'), 0) AS sales,
               COALESCE(SUM({v['doc']}) FILTER (WHERE s.status = 'returned'), 0) AS returned
        FROM sales s JOIN users u ON u.id = s.cashier_id
        WHERE {DOCS} AND s.created_at >= :start AND s.created_at < :end{scope.sql('s.warehouse_id', params)}
        GROUP BY u.id, u.full_name
        ORDER BY COALESCE(SUM({SIGN} * {v['doc']}), 0) DESC, u.full_name
    """), params)).all()
    return [{"cashier_id": str(r.id), "cashier_name": r.full_name, "invoice_count": r.invoices,
             "gross_sales": money(r.sales), "returns_total": money(r.returned), "total_sales": money(r.sales - r.returned)}
            for r in rows]


# ── profit ────────────────────────────────────────────────────────────────────────────────────

async def _ledger_start(db: AsyncSession, tenant_id: uuid.UUID) -> date | None:
    """The first day the ledger is complete from: the opening entry's date (accounting settings),
    else the first entry's. None while nothing is posted."""
    from app.activities.general.modules.accounting.services import settings as acc_settings

    start = (await acc_settings.get(db, tenant_id))["start_date"]
    if start:
        return start
    return (await db.execute(text("SELECT MIN(date) FROM acc_entries WHERE tenant_id = :t"), {"t": tenant_id})).scalar()


async def profit_report(db: AsyncSession, date_from: date, date_to: date, scope: Scope) -> dict:
    from app.framework.activation import get_active_modules
    from app.platform.tenancy.context import current_tenant_id

    day_range(date_from, date_to)  # validates the range
    tenant_id = current_tenant_id.get()
    ledger_start = None
    if "accounting" in await get_active_modules(db):
        ledger_start = await _ledger_start(db, tenant_id)
        if ledger_start is not None and date_from >= ledger_start:
            out = await _profit_from_ledger(db, tenant_id, date_from, date_to, scope)
            return {**out, "source": "ledger", "ledger_start": ledger_start.isoformat()}
    out = await _profit_from_operations(db, date_from, date_to, scope)
    return {**out, "source": "operations", "ledger_start": ledger_start.isoformat() if ledger_start else None}


def _margins(out: dict, net_revenue: Decimal, gross: Decimal, net: Decimal) -> dict:
    out["gross_margin"] = round(float(gross / net_revenue * 100), 1) if net_revenue > 0 else 0
    out["net_margin"] = round(float(net / net_revenue * 100), 1) if net_revenue > 0 else 0
    return out


async def _profit_from_ledger(db: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date, scope: Scope) -> dict:
    """The income statement's figures (accounting/services/reports.py), summed over the branches of
    the scope. A branch report leaves out lines with no branch (as the income statement does)."""
    from app.activities.general.modules.accounting.services import reports as acc_reports

    targets = [None] if scope.everything else list(scope.warehouses or ())
    totals = dict.fromkeys(("revenue", "sales_returns", "cogs", "operating_expenses", "other_income", "other_expenses"), ZERO)
    expense_lines: dict[str, Decimal] = {}
    for wh in targets:
        stmt = await acc_reports.income_statement(db, tenant_id, date_from, date_to, wh)
        for key in totals:
            totals[key] += D(str(stmt[key]["total"]))
        for key in ("operating_expenses", "other_expenses"):
            for line in stmt[key]["lines"]:
                expense_lines[line["name"]] = expense_lines.get(line["name"], ZERO) + D(str(line["amount"]))
    net_revenue = totals["revenue"] - totals["sales_returns"]
    gross = net_revenue - totals["cogs"]
    expenses = totals["operating_expenses"] + totals["other_expenses"]
    net = gross - expenses + totals["other_income"]
    out = {"from_date": date_from.isoformat(), "to_date": date_to.isoformat(), "warehouse_ids": scope.out(),
           "total_revenue": money(totals["revenue"]), "total_returns": money(totals["sales_returns"]),
           "net_revenue": money(net_revenue), "total_cogs": money(totals["cogs"]), "gross_profit": money(gross),
           "total_expenses": money(expenses), "other_income": money(totals["other_income"]),
           "expenses_detail": [{"note": k, "amount": money(v)} for k, v in sorted(expense_lines.items(), key=lambda kv: -kv[1])],
           "net_profit": money(net)}
    return _margins(out, net_revenue, gross, net)


async def _profit_from_operations(db: AsyncSession, date_from: date, date_to: date, scope: Scope) -> dict:
    """From the documents, by the ledger's rules (ADR-014 D3) so both agree where they can:
    - revenue: confirmed sales' value without VAT; returns: the return documents';
    - cost: the lines' unit cost (the average cost when sold), less the returned lines';
    - expenses: approved expenses dated in the period (payroll's approved salaries expense
      included), without their VAT, plus expense and withdrawal rows entered by hand in the
      drawers; deposits entered by hand in a drawer are other income. Expenses and drawer rows are
      separate records (an expense is paid from a safe or wallet, a drawer row from the drawer), so
      nothing is counted twice. A branch report leaves out expenses with no branch.
    Not included (the ledger has them): shift shortages and surpluses, safe withdrawals and wallet
    resets entered by hand."""
    start, end = day_range(date_from, date_to)
    v = await _vat_sql(db)
    params: dict = {"start": start, "end": end}
    docs = (await db.execute(text(f"""
        SELECT COALESCE(SUM({v['doc']}) FILTER (WHERE s.status = 'confirmed'), 0) AS sales,
               COALESCE(SUM({v['doc']}) FILTER (WHERE s.status = 'returned'), 0) AS returned
        FROM sales s
        WHERE {DOCS} AND s.created_at >= :start AND s.created_at < :end{scope.sql('s.warehouse_id', params)}
    """), params)).one()
    params = {"start": start, "end": end}
    cogs = (await db.execute(text(f"""
        SELECT COALESCE(SUM({SIGN} * si.qty * COALESCE(si.unit_cost, 0)), 0)
        FROM sale_items si JOIN sales s ON s.id = si.sale_id
        WHERE {DOCS} AND s.created_at >= :start AND s.created_at < :end{scope.sql('s.warehouse_id', params)}
    """), params)).scalar_one()

    params = {"df": date_from, "dt": date_to}
    expense_rows = (await db.execute(text(f"""
        SELECT COALESCE(fc.name, 'مصروفات أخرى') AS note, SUM({v['expense']}) AS total
        FROM expenses e LEFT JOIN financial_categories fc ON fc.id = e.category_id
        WHERE e.status = 'approved' AND e.date >= :df AND e.date <= :dt{scope.sql('e.warehouse_id', params)}
        GROUP BY 1
    """), params)).all()
    params = {"start": start, "end": end}
    drawer_rows = (await db.execute(text(f"""
        SELECT CAST(dt.type AS text) AS kind, COALESCE(fc.name, NULLIF(dt.note, ''),
               CASE WHEN CAST(dt.type AS text) = 'withdrawal' THEN 'مسحوبات من الدرج' ELSE 'مصروف من الدرج' END) AS note,
               SUM(dt.amount) AS total
        FROM drawer_transactions dt JOIN shifts sh ON sh.id = dt.shift_id
        LEFT JOIN financial_categories fc ON fc.id = dt.category_id
        WHERE CAST(dt.type AS text) IN ('expense', 'withdrawal', 'deposit') AND dt.cancelled_at IS NULL
          AND dt.ref_id IS NULL AND dt.customer_payment_id IS NULL
          AND dt.created_at >= :start AND dt.created_at < :end{scope.sql('sh.warehouse_id', params)}
        GROUP BY 1, 2
    """), params)).all()

    detail: dict[str, Decimal] = {}
    for r in expense_rows:
        detail[r.note] = detail.get(r.note, ZERO) + D(r.total)
    other_income = ZERO
    for r in drawer_rows:
        if r.kind == "deposit":
            other_income += D(r.total)
        else:
            detail[r.note] = detail.get(r.note, ZERO) + D(r.total)
    expenses = sum(detail.values(), ZERO)

    net_revenue = D(docs.sales) - D(docs.returned)
    gross = net_revenue - D(cogs)
    net = gross - expenses + other_income
    out = {"from_date": date_from.isoformat(), "to_date": date_to.isoformat(), "warehouse_ids": scope.out(),
           "total_revenue": money(docs.sales), "total_returns": money(docs.returned), "net_revenue": money(net_revenue),
           "total_cogs": money(cogs), "gross_profit": money(gross), "total_expenses": money(expenses),
           "other_income": money(other_income),
           "expenses_detail": [{"note": k, "amount": money(v)} for k, v in sorted(detail.items(), key=lambda kv: -kv[1])],
           "net_profit": money(net)}
    return _margins(out, net_revenue, gross, net)


# ── inventory print ───────────────────────────────────────────────────────────────────────────

async def inventory_print_report(db: AsyncSession, warehouse_id: uuid.UUID, with_cost: bool) -> dict[str, Any]:
    """Every active product with its quantity in the branch (from its movements); with `with_cost`,
    valued at its average cost (its listed cost while it has none), as the ledger values stock."""
    from app.activities.general.modules.inventory.models.stock import IN_TYPES

    wh = (await db.execute(text("SELECT name FROM warehouses WHERE id = :id"), {"id": warehouse_id})).scalar_one()
    rows = (await db.execute(text("""
        WITH bal AS (
            SELECT product_id, SUM(CASE WHEN CAST(movement_type AS text) = ANY(:ins) THEN qty ELSE -qty END) AS qty
            FROM stock_movements WHERE warehouse_id = :wh GROUP BY product_id
        )
        SELECT p.name, p.unit, COALESCE(c.name, 'بدون تصنيف') AS category, COALESCE(sc.name, '') AS subcategory,
               COALESCE(bal.qty, 0) AS qty, COALESCE(NULLIF(p.avg_cost, 0), p.cost_price, 0) AS cost,
               COALESCE(p.retail_price, 0) AS retail
        FROM products p
        LEFT JOIN subcategories sc ON sc.id = p.subcategory_id
        LEFT JOIN categories c ON c.id = sc.category_id
        LEFT JOIN bal ON bal.product_id = p.id
        WHERE p.is_active
        ORDER BY NULLIF(c.code, '') NULLS LAST, c.name NULLS LAST, NULLIF(sc.code, '') NULLS LAST, sc.name,
                 NULLIF(p.code, '') NULLS LAST, p.name
    """), {"wh": warehouse_id, "ins": list(IN_TYPES)})).all()
    settings = {r.key: r.value for r in (await db.execute(text("SELECT key, value FROM store_settings"))).all()}

    items, total_cost, total_retail = [], ZERO, ZERO
    for r in rows:
        q = D(r.qty)
        retail_value = q * D(r.retail)
        total_retail += retail_value
        item = {"category": r.category, "subcategory": r.subcategory, "name": r.name, "unit": r.unit, "qty": qty(q),
                "retail_price": money(r.retail), "retail_value": money(retail_value)}
        if with_cost:
            cost_value = q * D(r.cost)
            total_cost += cost_value
            item.update(cost_price=money(r.cost), cost_value=money(cost_value))
        items.append(item)
    summary = {"total_products": len(items), "total_retail_value": money(total_retail)}
    if with_cost:
        summary["total_cost_value"] = money(total_cost)
    return {
        "store": {"name": settings.get("store_name", ""), "address": settings.get("store_address", ""),
                  "phone": settings.get("store_phone", "")},
        "warehouse": wh, "generated_at": datetime.now(UTC).isoformat(), "with_cost": with_cost,
        "items": items, "summary": summary,
    }


# ── daily ledger items ────────────────────────────────────────────────────────────────────────

async def daily_items(db: AsyncSession, target_date: date, scope: Scope) -> dict[str, Any]:
    """The day's products: sold per price (quantity and value after every discount), the value
    returned that day per product, and the drawer expenses entered by hand."""
    start, end = day_range(target_date, target_date)
    params: dict = {"start": start, "end": end}
    cte = await _lines_cte(db, scope, params)
    sold = (await db.execute(text(f"""
        WITH {cte}
        SELECT l.product_id, p.name, p.unit, l.unit_price AS price,
               COALESCE(SUM(l.qty) FILTER (WHERE l.sign > 0), 0) AS qty,
               COALESCE(SUM(l.value) FILTER (WHERE l.sign > 0), 0) AS total,
               COALESCE(SUM(l.value) FILTER (WHERE l.sign < 0), 0) AS returns
        FROM lines l JOIN products p ON p.id = l.product_id
        GROUP BY l.product_id, p.name, p.unit, l.unit_price
        ORDER BY total DESC, p.name
    """), params)).all()
    returns_by_product: dict = {}
    for r in sold:
        returns_by_product[r.product_id] = returns_by_product.get(r.product_id, ZERO) + D(r.returns)
    items, seen = [], set()
    for r in sold:
        if r.qty == 0 and r.total == 0:
            continue  # only returned at this price: added to the product's row below
        first = r.product_id not in seen
        seen.add(r.product_id)
        items.append({"product_id": str(r.product_id), "name": r.name, "unit": r.unit, "price": money(r.price),
                      "qty": qty(r.qty), "total": money(r.total),
                      "returns": money(returns_by_product[r.product_id] if first else ZERO)})
    for r in sold:
        if r.product_id not in seen:  # returned today, not sold today
            seen.add(r.product_id)
            items.append({"product_id": str(r.product_id), "name": r.name, "unit": r.unit, "price": money(r.price),
                          "qty": 0.0, "total": money(ZERO), "returns": money(returns_by_product[r.product_id])})
    params = {"start": start, "end": end}
    expenses = (await db.execute(text(f"""
        SELECT COALESCE(NULLIF(dt.note, ''), 'مصروف') AS note, SUM(dt.amount) AS total
        FROM drawer_transactions dt JOIN shifts sh ON sh.id = dt.shift_id
        WHERE CAST(dt.type AS text) = 'expense' AND dt.cancelled_at IS NULL
          AND dt.created_at >= :start AND dt.created_at < :end{scope.sql('sh.warehouse_id', params)}
        GROUP BY 1 ORDER BY 2 DESC
    """), params)).all()
    return {"date": target_date.isoformat(), "warehouse_ids": scope.out(), "items": items,
            "expenses": [{"note": r.note, "total": money(r.total)} for r in expenses]}


# ── periodic ledger ───────────────────────────────────────────────────────────────────────────

PERIODS = {"weekly": ("week", 'IYYY-"W"IW'), "monthly": ("month", "YYYY-MM"), "yearly": ("year", "YYYY")}
PERIOD_COUNT = 52


def _periods_since(period: str) -> date:
    t = today()
    if period == "weekly":
        return t - timedelta(days=t.weekday()) - timedelta(weeks=PERIOD_COUNT - 1)
    if period == "monthly":
        months = t.year * 12 + t.month - 1 - (PERIOD_COUNT - 1)
        return date(months // 12, months % 12 + 1, 1)
    return date(t.year - (PERIOD_COUNT - 1), 1, 1)


async def periodic_ledger(db: AsyncSession, period: str, scope: Scope) -> list[dict[str, Any]]:
    """The last 52 weeks / months / years, newest first: sales, returns (both without VAT, after
    every discount), expenses (approved expenses and drawer expenses) and the net."""
    trunc, label = PERIODS[period]
    since = _periods_since(period)
    v = await _vat_sql(db)
    params: dict = {"since": day_start(since)}
    local = f"(s.created_at AT TIME ZONE '{TZ_NAME}')"
    sales = (await db.execute(text(f"""
        SELECT TO_CHAR(DATE_TRUNC('{trunc}', {local}), '{label}') AS period, MIN({local}) AS first,
               COALESCE(SUM({v['doc']}) FILTER (WHERE s.status = 'confirmed'), 0) AS income,
               COALESCE(SUM({v['doc']}) FILTER (WHERE s.status = 'returned'), 0) AS returns
        FROM sales s
        WHERE {DOCS} AND s.created_at >= :since{scope.sql('s.warehouse_id', params)}
        GROUP BY 1
    """), params)).all()
    params = {"since": day_start(since)}
    dlocal = f"(dt.created_at AT TIME ZONE '{TZ_NAME}')"
    drawer = (await db.execute(text(f"""
        SELECT TO_CHAR(DATE_TRUNC('{trunc}', {dlocal}), '{label}') AS period, MIN({dlocal}) AS first, SUM(dt.amount) AS total
        FROM drawer_transactions dt JOIN shifts sh ON sh.id = dt.shift_id
        WHERE CAST(dt.type AS text) = 'expense' AND dt.cancelled_at IS NULL
          AND dt.created_at >= :since{scope.sql('sh.warehouse_id', params)}
        GROUP BY 1
    """), params)).all()
    params = {"since_d": since}
    approved = (await db.execute(text(f"""
        SELECT TO_CHAR(DATE_TRUNC('{trunc}', CAST(e.date AS timestamp)), '{label}') AS period,
               MIN(CAST(e.date AS timestamp)) AS first, SUM({v['expense']}) AS total
        FROM expenses e
        WHERE e.status = 'approved' AND e.date >= :since_d{scope.sql('e.warehouse_id', params)}
        GROUP BY 1
    """), params)).all()
    table: dict[str, dict] = {}
    for r in sales:
        table.setdefault(r.period, {"first": r.first, "income": ZERO, "returns": ZERO, "expenses": ZERO})
        table[r.period].update(income=D(r.income), returns=D(r.returns))
    for r in [*drawer, *approved]:
        row = table.setdefault(r.period, {"first": r.first, "income": ZERO, "returns": ZERO, "expenses": ZERO})
        row["expenses"] += D(r.total)
        row["first"] = min(row["first"], r.first)
    ordered = sorted(table.items(), key=lambda kv: kv[1]["first"], reverse=True)
    return [{"period": p, "income": money(r["income"]), "returns": money(r["returns"]), "expenses": money(r["expenses"]),
             "net": money(r["income"] - r["returns"] - r["expenses"])} for p, r in ordered]


# ── cash flow ─────────────────────────────────────────────────────────────────────────────────

async def cash_flow(db: AsyncSession, date_from: date, date_to: date, scope: Scope) -> dict[str, Any]:
    """Money that came in and went out in the period, by what moved it (REP-8). From the ledger's
    money accounts when the workspace has accounting and the ledger covers the period
    (`source: "ledger"`), otherwise from the documents (`source: "operations"`). Each `lines` row is
    a kind of document, keyed like the ledger's sources (sale, sale_return, customer_payment,
    expense, supplier_tx, payroll, hr_advance, drawer_tx, safe_movement…): what came in, what went
    out, the net."""
    from app.framework.activation import get_active_modules
    from app.platform.tenancy.context import current_tenant_id

    day_range(date_from, date_to)  # validates the range
    tenant_id = current_tenant_id.get()
    ledger_start = None
    if "accounting" in await get_active_modules(db):
        ledger_start = await _ledger_start(db, tenant_id)
        if ledger_start is not None and date_from >= ledger_start:
            out = await _cash_flow_from_ledger(db, tenant_id, date_from, date_to, scope)
            return {**out, "source": "ledger", "ledger_start": ledger_start.isoformat()}
    out = await _cash_flow_from_operations(db, date_from, date_to, scope)
    return {**out, "source": "operations", "ledger_start": ledger_start.isoformat() if ledger_start else None}


def _flow_lines(rows: dict[str, tuple[Decimal, Decimal]]) -> tuple[list[dict], Decimal, Decimal]:
    lines = [{"key": k, "in": money(i), "out": money(o), "net": money(i - o)}
             for k, (i, o) in sorted(rows.items(), key=lambda kv: -(kv[1][0] + kv[1][1])) if i or o]
    return lines, sum((i for i, _ in rows.values()), ZERO), sum((o for _, o in rows.values()), ZERO)


async def _cash_flow_from_ledger(db: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date,
                                 scope: Scope) -> dict[str, Any]:
    """The money accounts' lines (every safe, bank account, wallet and drawer, `acc_money_accounts`),
    netted per document: a document that brought money in (a sale) is an inflow, one that took it
    out (an expense) an outflow, and one that only moved it between the company's own accounts (a
    revenue delivery, a wallet emptied into a safe) nets to zero and isn't cash flow. A document and
    its reversal in the same period cancel out. The opening entry is the opening balance, not a
    flow. A branch report covers the lines of the branch (a safe without a branch is left out)."""
    params: dict = {"t": tenant_id, "df": date_from, "dt": date_to}
    branch = scope.sql("l.warehouse_id", params)
    rows = (await db.execute(text(f"""
        WITH moves AS (
            SELECT e.source_type, e.source_id, SUM(l.debit - l.credit) AS net
            FROM acc_lines l
            JOIN acc_entries e ON e.id = l.entry_id
            JOIN acc_money_accounts m ON m.account_id = l.account_id AND m.tenant_id = e.tenant_id
            WHERE e.tenant_id = :t AND e.date >= :df AND e.date <= :dt AND e.source_type <> 'opening'{branch}
            GROUP BY e.source_type, e.source_id
        )
        SELECT source_type, COALESCE(SUM(net) FILTER (WHERE net > 0), 0) AS incoming,
               COALESCE(-SUM(net) FILTER (WHERE net < 0), 0) AS outgoing
        FROM moves GROUP BY source_type
    """), params)).all()
    lines, total_in, total_out = _flow_lines({r.source_type: (D(r.incoming), D(r.outgoing)) for r in rows})

    params = {"t": tenant_id, "df": date_from, "dt": date_to}
    branch = scope.sql("l.warehouse_id", params)
    accounts = (await db.execute(text(f"""
        SELECT a.code, a.name, m.kind,
               COALESCE(SUM(l.debit - l.credit) FILTER (WHERE e.date < :df OR e.source_type = 'opening'), 0) AS opening,
               COALESCE(SUM(l.debit) FILTER (WHERE e.date >= :df AND e.source_type <> 'opening'), 0) AS incoming,
               COALESCE(SUM(l.credit) FILTER (WHERE e.date >= :df AND e.source_type <> 'opening'), 0) AS outgoing
        FROM acc_lines l
        JOIN acc_entries e ON e.id = l.entry_id
        JOIN acc_money_accounts m ON m.account_id = l.account_id AND m.tenant_id = e.tenant_id
        JOIN acc_accounts a ON a.id = l.account_id
        WHERE e.tenant_id = :t AND e.date <= :dt{branch}
        GROUP BY a.code, a.name, m.kind
        ORDER BY a.code
    """), params)).all()
    opening = sum((D(r.opening) for r in accounts), ZERO)
    return {
        "from_date": date_from.isoformat(), "to_date": date_to.isoformat(), "warehouse_ids": scope.out(),
        "lines": lines, "total_in": money(total_in), "total_out": money(total_out),
        "net_cash_flow": money(total_in - total_out),
        "opening_balance": money(opening), "closing_balance": money(opening + total_in - total_out),
        "accounts": [{"code": r.code, "name": r.name, "kind": r.kind, "opening": money(r.opening), "in": money(r.incoming),
                      "out": money(r.outgoing), "closing": money(D(r.opening) + D(r.incoming) - D(r.outgoing))}
                     for r in accounts],
    }


async def _cash_flow_from_operations(db: AsyncSession, date_from: date, date_to: date, scope: Scope) -> dict[str, Any]:
    """From the documents, each counted once:
    in: sales paid other than on credit (per payment method), customers' payments, purchase returns
    refunded by suppliers, deposits entered by hand in the drawers;
    out: refunds of sales returns, payments to suppliers (on receipt and later), approved expenses
    other than salaries, salaries paid, advances paid to employees (less those cancelled), drawer
    expenses and withdrawals entered by hand.
    Moves between the company's own drawers, safes and wallets are not cash flow. Customers' and
    suppliers' payments, purchase refunds, salaries and advances have no branch: they appear only in
    the report of every branch. Not here (the ledger has them): safe deposits and withdrawals and
    wallet resets entered by hand."""
    start, end = day_range(date_from, date_to)
    v = await _vat_sql(db)
    whole = scope.everything

    async def scalar(sql: str, params: dict) -> Decimal:
        return D((await db.execute(text(sql), params)).scalar() or 0)

    params: dict = {"start": start, "end": end}
    by_method = (await db.execute(text(f"""
        SELECT sp.method, CAST(s.status AS text) AS status, COALESCE(SUM(sp.amount), 0) AS total
        FROM sale_payments sp JOIN sales s ON s.id = sp.sale_id
        WHERE {DOCS} AND sp.method <> 'credit' AND s.created_at >= :start AND s.created_at < :end
              {scope.sql('s.warehouse_id', params)}
        GROUP BY 1, 2
    """), params)).all()
    sales_in = {r.method: D(r.total) for r in by_method if r.status == "confirmed"}
    refunds_out = sum((D(r.total) for r in by_method if r.status == "returned"), ZERO)
    params = {"start": start, "end": end}
    credit_sales = await scalar(f"""
        SELECT COALESCE(SUM(sp.amount), 0) FROM sale_payments sp JOIN sales s ON s.id = sp.sale_id
        WHERE s.status = 'confirmed' AND sp.method = 'credit' AND s.created_at >= :start AND s.created_at < :end
              {scope.sql('s.warehouse_id', params)}""", params)

    params = {"start": start, "end": end}
    drawer = {r.kind: D(r.total) for r in (await db.execute(text(f"""
        SELECT CAST(dt.type AS text) AS kind, COALESCE(SUM(dt.amount), 0) AS total
        FROM drawer_transactions dt JOIN shifts sh ON sh.id = dt.shift_id
        WHERE CAST(dt.type AS text) IN ('deposit', 'expense', 'withdrawal') AND dt.cancelled_at IS NULL
          AND dt.ref_id IS NULL AND dt.customer_payment_id IS NULL
          AND dt.created_at >= :start AND dt.created_at < :end{scope.sql('sh.warehouse_id', params)}
        GROUP BY 1"""), params)).all()}

    p = {"start": start, "end": end}
    customer_payments = await scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM customer_payments WHERE created_at >= :start AND created_at < :end", p) if whole else ZERO
    supplier_payments = await scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM supplier_transactions WHERE type = 'credit' "
        "AND created_at >= :start AND created_at < :end", p) if whole else ZERO
    purchase_refunds = await scalar(
        "SELECT COALESCE(SUM(refund_amount), 0) FROM purchase_returns WHERE created_at >= :start AND created_at < :end", p) if whole else ZERO
    payroll_paid = await scalar(
        "SELECT COALESCE(SUM(paid_amount), 0) FROM hr_payroll_periods WHERE status = 'paid' "
        "AND paid_at >= :start AND paid_at < :end", p) if whole else ZERO
    # Advances paid out of a safe or wallet (a carried advance moved no cash), less the cancelled.
    advances_paid = await scalar("""
        SELECT COALESCE(SUM(amount) FILTER (WHERE created_at >= :start AND created_at < :end), 0)
             - COALESCE(SUM(amount) FILTER (WHERE status = 'cancelled' AND cancelled_at >= :start AND cancelled_at < :end), 0)
        FROM hr_advances WHERE (safe_id IS NOT NULL OR wallet_id IS NOT NULL)""", p) if whole else ZERO
    params = {"df": date_from, "dt": date_to, "payroll_note": "HR payroll month%"}
    expenses_out = await scalar(f"""
        SELECT COALESCE(SUM(e.amount), 0) FROM expenses e
        WHERE e.status = 'approved' AND e.date >= :df AND e.date <= :dt
          AND COALESCE(e.payment_method, '') <> 'payroll' AND COALESCE(e.notes, '') NOT LIKE :payroll_note
          {scope.sql('e.warehouse_id', params)}""", params)

    sales_paid = sum(sales_in.values(), ZERO)
    drawer_out = drawer.get("expense", ZERO) + drawer.get("withdrawal", ZERO)
    flows = {
        "sale": (sales_paid, ZERO), "sale_return": (ZERO, refunds_out), "customer_payment": (customer_payments, ZERO),
        "purchase_return": (purchase_refunds, ZERO), "drawer_tx": (drawer.get("deposit", ZERO), drawer_out),
        "supplier_tx": (ZERO, supplier_payments), "expense": (ZERO, expenses_out), "payroll": (ZERO, payroll_paid),
        "hr_advance": (max(ZERO, -advances_paid), max(ZERO, advances_paid)),
    }
    lines, total_in, total_out = _flow_lines(flows)

    # The figures under their former names, for the callers that read them.
    incoming = {
        "cash_sales": money(sales_paid), "sales_by_method": {k: money(val) for k, val in sorted(sales_in.items())},
        "credit_sales": money(credit_sales), "customer_payments": money(customer_payments),
        "purchase_refunds": money(purchase_refunds), "drawer_deposits": money(drawer.get("deposit", ZERO)),
        "total_incoming": money(total_in),
    }
    outgoing = {
        "supplier_payments": money(supplier_payments), "expenses": money(expenses_out + drawer_out),
        "payroll": money(payroll_paid), "advances": money(max(ZERO, advances_paid)),
        "returns_to_customers": money(refunds_out), "total_outgoing": money(total_out),
    }

    params = {"df": date_from, "dt": date_to}
    cat_rows = (await db.execute(text(f"""
        SELECT COALESCE(fc.name, 'مصروفات أخرى') AS name, fc.color, SUM({v['expense']}) AS total
        FROM expenses e LEFT JOIN financial_categories fc ON fc.id = e.category_id
        WHERE e.status = 'approved' AND e.date >= :df AND e.date <= :dt{scope.sql('e.warehouse_id', params)}
        GROUP BY 1, 2 ORDER BY 3 DESC
    """), params)).all()
    params = {"start": start, "end": end}
    wh_rows = (await db.execute(text(f"""
        SELECT w.name, COALESCE(SUM({SIGN} * {v['doc']}), 0) AS total
        FROM sales s JOIN warehouses w ON w.id = s.warehouse_id
        WHERE {DOCS} AND s.created_at >= :start AND s.created_at < :end{scope.sql('s.warehouse_id', params)}
        GROUP BY w.name ORDER BY 2 DESC
    """), params)).all()
    return {
        "from_date": date_from.isoformat(), "to_date": date_to.isoformat(), "warehouse_ids": scope.out(),
        "lines": lines, "total_in": money(total_in), "total_out": money(total_out),
        "net_cash_flow": money(total_in - total_out), "opening_balance": None, "closing_balance": None, "accounts": [],
        "incoming": incoming, "outgoing": outgoing, "sales_by_method": incoming["sales_by_method"],
        "details": {
            "expenses_by_category": [{"name": r.name, "color": r.color, "amount": money(r.total)} for r in cat_rows],
            "sales_by_warehouse": [{"warehouse": r.name, "amount": money(r.total)} for r in wh_rows],
        },
    }


# ── aging ─────────────────────────────────────────────────────────────────────────────────────

BUCKETS = ("0-30", "30-60", "60-90", "90+")
AGING_LIMIT = 500  # parties listed (the totals cover every party)
INVOICES_PER_CUSTOMER = 50  # a listed customer's open invoices shown, oldest first
BUCKET_SQL = """CASE WHEN CAST(:as_of AS date) - {day} < 30 THEN '0-30' WHEN CAST(:as_of AS date) - {day} < 60 THEN '30-60'
                     WHEN CAST(:as_of AS date) - {day} < 90 THEN '60-90' ELSE '90+' END"""


def _bucket(as_of: date, on: date) -> str:
    days = (as_of - on).days
    if days < 30:
        return "0-30"
    if days < 60:
        return "30-60"
    if days < 90:
        return "60-90"
    return "90+"


async def aging_report(db: AsyncSession, as_of: date, scope: Scope) -> dict[str, Any]:
    """What customers owe on credit invoices, and what we owe suppliers, by age at `as_of`, as it
    stood that day (REP-10): later documents don't count.
    - Customers: each credit invoice issued by `as_of` and what was still open on it then: its net
      total, less what was paid on it by then (at the sale, and the receipts against it dated by
      `as_of`) and the returns made by then; aged by the invoice's date.
    - Suppliers: invoices and payments up to `as_of`; payments settle the oldest invoices first, and
      what is left of each invoice is aged by its date. Suppliers have no branch: they appear only in
      the report of every branch.
    Aggregated in the database (REP-14): the totals cover every party, the first AGING_LIMIT parties
    (by debt) are listed, each customer with up to INVOICES_PER_CUSTOMER open invoices."""
    end = day_start(as_of + timedelta(days=1))
    params: dict = {"end": end, "as_of": as_of}
    branch = scope.sql("s.warehouse_id", params)
    open_invoices = f"""
        WITH inv AS (
            SELECT s.id, s.customer_id, s.invoice_number, {LOCAL_DAY} AS day, COALESCE(s.net_total, 0) AS total,
                   COALESCE(s.net_total, 0)
                   - (COALESCE(s.paid_amount, 0) - COALESCE((SELECT SUM(cp.amount) FROM customer_payments cp
                                                          WHERE cp.sale_id = s.id AND cp.created_at >= :end), 0))
                   - (COALESCE(s.returns_total, 0) - COALESCE((SELECT SUM(r.net_total) FROM sales r
                                                            WHERE r.return_of = s.id AND r.status = 'returned'
                                                              AND r.created_at >= :end), 0)) AS remaining
            FROM sales s
            WHERE s.is_credit AND s.customer_id IS NOT NULL AND s.status = 'confirmed' AND s.created_at < :end{branch}
        ), open AS (SELECT * FROM inv WHERE remaining > 0.005)
    """
    cust_rows = (await db.execute(text(f"""
        {open_invoices}
        SELECT c.id, c.name, {BUCKET_SQL.format(day='o.day')} AS bucket, SUM(o.remaining) AS amount
        FROM open o JOIN customers c ON c.id = o.customer_id
        GROUP BY c.id, c.name, 3
    """), params)).all()
    customers = _parties(cust_rows)
    listed = [c["id"] for c in customers[:AGING_LIMIT]]
    if listed:
        inv_rows = (await db.execute(text(f"""
            {open_invoices}
            SELECT customer_id, invoice_number, day, total, remaining FROM (
                SELECT o.*, ROW_NUMBER() OVER (PARTITION BY o.customer_id ORDER BY o.day, o.invoice_number) AS n
                FROM open o WHERE o.customer_id = ANY(:ids)
            ) x WHERE n <= :per ORDER BY customer_id, day
        """), {**params, "ids": listed, "per": INVOICES_PER_CUSTOMER})).all()
        by_id = {c["id"]: c for c in customers}
        for r in inv_rows:
            by_id[r.customer_id]["invoices"].append({"invoice": r.invoice_number, "date": r.day.isoformat(),
                                                     "total": money(r.total), "remaining": money(r.remaining),
                                                     "bucket": _bucket(as_of, r.day)})

    suppliers: list[dict] = []
    if scope.everything:
        supp_rows = (await db.execute(text(f"""
            WITH tx AS (
                SELECT st.supplier_id, st.type, st.amount, st.id, st.created_at,
                       (st.created_at AT TIME ZONE '{TZ_NAME}')::date AS day
                FROM supplier_transactions st WHERE st.created_at < :end
            ), paid AS (
                SELECT supplier_id, SUM(amount) AS paid FROM tx WHERE type <> 'debit' GROUP BY supplier_id
            ), inv AS (
                SELECT tx.supplier_id, tx.day, tx.amount,
                       SUM(tx.amount) OVER (PARTITION BY tx.supplier_id ORDER BY tx.created_at, tx.id) AS running
                FROM tx WHERE tx.type = 'debit'
            ), open AS (
                -- Payments settle the oldest invoices first: what is left of an invoice is what the
                -- running total of invoices up to it exceeds the payments by, at most its amount.
                SELECT inv.supplier_id, inv.day,
                       LEAST(inv.amount, inv.running - COALESCE(paid.paid, 0)) AS remaining
                FROM inv LEFT JOIN paid ON paid.supplier_id = inv.supplier_id
            )
            SELECT s.id, s.name, {BUCKET_SQL.format(day='o.day')} AS bucket, SUM(o.remaining) AS amount
            FROM open o JOIN suppliers s ON s.id = o.supplier_id
            WHERE o.remaining > 0.005
            GROUP BY s.id, s.name, 3
        """), params)).all()
        suppliers = _parties(supp_rows, invoices=False)

    return {"as_of": as_of.isoformat(), "warehouse_ids": scope.out(),
            "customers": {"items": _finish(customers[:AGING_LIMIT]), "totals": _totals(customers), "count": len(customers)},
            "suppliers": {"items": _finish(suppliers[:AGING_LIMIT]), "totals": _totals(suppliers), "count": len(suppliers),
                          "included": scope.everything}}


def _parties(rows, invoices: bool = True) -> list[dict]:
    """Rows of (id, name, bucket, amount) as one entry per party, the largest debt first."""
    out: dict = {}
    for r in rows:
        p = out.setdefault(r.id, {"id": r.id, "name": r.name, "total_debt": ZERO, "buckets": dict.fromkeys(BUCKETS, ZERO),
                                  **({"invoices": []} if invoices else {})})
        p["buckets"][r.bucket] += D(r.amount)
        p["total_debt"] += D(r.amount)
    return sorted(out.values(), key=lambda p: (-p["total_debt"], p["name"] or ""))


def _totals(items: list[dict]) -> dict:
    out = {b: money(sum((i["buckets"][b] for i in items), ZERO)) for b in BUCKETS}
    out["total"] = money(sum((i["total_debt"] for i in items), ZERO))
    return out


def _finish(items: list[dict]) -> list[dict]:
    return [{**i, "id": str(i["id"]), "total_debt": money(i["total_debt"]),
             "buckets": {b: money(v) for b, v in i["buckets"].items()}} for i in items]
