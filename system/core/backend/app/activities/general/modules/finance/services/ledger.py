"""The daily ledger (/reports/ledger): the period's sale lines, returns and drawer movements, one
page at a time, with totals over the whole period (SQL aggregates, never the page's rows).

Days are the workspace's days (Africa/Cairo): a period runs from the first day's midnight to the
midnight after the last day."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.tenancy import clock

ZERO = Decimal("0")


def day_bounds(from_date: date | None, to_date: date | None) -> tuple[datetime | None, datetime | None]:
    """[start, end) of the days from `from_date` to `to_date` included, in the workspace's time zone."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, "تاريخ البداية بعد تاريخ النهاية")
    return clock.day_bounds(from_date, to_date)


def _branch(alias: str, branches: list[uuid.UUID] | None) -> tuple[str, dict]:
    if branches is None:
        return "", {}
    return f"AND {alias}.warehouse_id = ANY(:whs)", {"whs": branches}


SALE_LINES = """
    SELECT si.id, si.sale_id, p.name AS product_name, p.unit, si.qty, si.unit_price,
           (si.qty * si.unit_price - si.discount) AS line_total,
           COALESCE(s.payment_method, 'cash') AS payment_method, pw.name AS wallet_name,
           s.invoice_number, s.created_at, c.name AS customer_name
    FROM sale_items si
    JOIN sales s ON s.id = si.sale_id
    JOIN products p ON p.id = si.product_id
    LEFT JOIN customers c ON c.id = s.customer_id
    LEFT JOIN payment_wallets pw ON pw.id = s.wallet_id
    WHERE s.status = :status AND s.created_at >= :start AND s.created_at < :end {wh}
    ORDER BY s.created_at, si.id
    OFFSET :offset LIMIT :limit
"""

DRAWER_ROWS = """
    SELECT dt.id, dt.type, dt.amount, dt.note, dt.created_at, pw.name AS wallet_name, dt.payment_method
    FROM drawer_transactions dt
    JOIN shifts sh ON sh.id = dt.shift_id
    LEFT JOIN payment_wallets pw ON pw.id = dt.wallet_id
    WHERE dt.type IN ('expense','deposit','withdrawal') AND dt.cancelled_at IS NULL
      AND dt.created_at >= :start AND dt.created_at < :end {wh}
    ORDER BY dt.created_at, dt.id
    OFFSET :offset LIMIT :limit
"""

# Per invoice: its lines (pre-aggregated) less the invoice discount, and its payments (pre-aggregated
# apart, so lines and payments never multiply each other).
INVOICE_TOTALS = """
    WITH inv AS (
        SELECT s.id, s.status, s.wallet_id,
               (COALESCE(s.is_credit, false) OR COALESCE(s.payment_method, 'cash') = 'credit') AS on_credit,
               COALESCE(it.lines, 0) - COALESCE(s.discount_amount, 0) AS net,
               COALESCE(it.n, 0) AS n_lines,
               pay.n AS n_payments, pay.cash, pay.wallet, pay.credit
        FROM sales s
        LEFT JOIN (
            SELECT si.sale_id, SUM(si.qty * si.unit_price - si.discount) AS lines, COUNT(*) AS n
            FROM sale_items si JOIN sales s2 ON s2.id = si.sale_id
            WHERE s2.status IN ('confirmed', 'returned') AND s2.created_at >= :start AND s2.created_at < :end
            GROUP BY si.sale_id
        ) it ON it.sale_id = s.id
        LEFT JOIN (
            SELECT sp.sale_id, COUNT(*) AS n,
                   SUM(sp.amount) FILTER (WHERE sp.method = 'cash') AS cash,
                   SUM(sp.amount) FILTER (WHERE sp.wallet_id IS NOT NULL) AS wallet,
                   SUM(sp.amount) FILTER (WHERE sp.method = 'credit') AS credit
            FROM sale_payments sp JOIN sales s3 ON s3.id = sp.sale_id
            WHERE s3.status = 'confirmed' AND s3.created_at >= :start AND s3.created_at < :end
            GROUP BY sp.sale_id
        ) pay ON pay.sale_id = s.id
        WHERE s.status IN ('confirmed', 'returned') AND s.created_at >= :start AND s.created_at < :end {wh}
    )
    SELECT
        COALESCE(SUM(net) FILTER (WHERE status = 'confirmed'), 0) AS total_sales,
        COALESCE(SUM(n_lines) FILTER (WHERE status = 'confirmed'), 0) AS sale_lines,
        COALESCE(SUM(net) FILTER (WHERE status = 'returned'), 0) AS total_returns,
        COALESCE(SUM(n_lines) FILTER (WHERE status = 'returned'), 0) AS return_lines,
        COALESCE(SUM(CASE WHEN n_payments > 0 THEN COALESCE(cash, 0)
                          WHEN wallet_id IS NULL AND NOT on_credit THEN net ELSE 0 END)
                 FILTER (WHERE status = 'confirmed'), 0) AS cash_sales,
        COALESCE(SUM(CASE WHEN n_payments > 0 THEN COALESCE(wallet, 0) WHEN wallet_id IS NOT NULL THEN net ELSE 0 END)
                 FILTER (WHERE status = 'confirmed'), 0) AS wallet_sales,
        COALESCE(SUM(CASE WHEN n_payments > 0 THEN COALESCE(credit, 0)
                          WHEN wallet_id IS NULL AND on_credit THEN net ELSE 0 END)
                 FILTER (WHERE status = 'confirmed'), 0) AS credit_sales
    FROM inv
"""

DRAWER_TOTALS = """
    SELECT
        COUNT(*) FILTER (WHERE dt.type IN ('expense','deposit','withdrawal')) AS n_movements,
        COALESCE(SUM(dt.amount) FILTER (WHERE dt.type IN ('expense','withdrawal')), 0) AS total_expenses,
        COALESCE(SUM(dt.amount) FILTER (WHERE dt.type = 'deposit'), 0) AS total_deposits,
        COALESCE(SUM(dt.amount) FILTER (WHERE dt.type IN ('expense','withdrawal') AND {cash}), 0) AS cash_expenses,
        COALESCE(SUM(dt.amount) FILTER (WHERE dt.type = 'deposit' AND {cash}), 0) AS cash_deposits,
        COALESCE(SUM(dt.amount) FILTER (WHERE dt.type = 'sale' AND {cash}), 0) AS drawer_sales,
        COALESCE(SUM(dt.amount) FILTER (WHERE dt.type = 'return_' AND {cash}), 0) AS drawer_returns
    FROM drawer_transactions dt
    JOIN shifts sh ON sh.id = dt.shift_id
    WHERE dt.cancelled_at IS NULL AND dt.created_at >= :start AND dt.created_at < :end {wh}
""".replace("{cash}", "(dt.wallet_id IS NULL AND COALESCE(NULLIF(dt.payment_method, ''), 'cash') = 'cash')")

TX_AR = {"expense": "خوارج", "deposit": "دواخل", "withdrawal": "سحب"}


def _pages(total: int, size: int) -> int:
    return (total + size - 1) // size


def _f(v) -> float:
    return float(v or 0)


def _sale_line(d: dict, entry_type: str) -> dict:
    out = {
        "item_id": str(d["id"]), "sale_id": str(d["sale_id"]), "product_name": d["product_name"], "unit": d["unit"],
        "qty": _f(d["qty"]), "unit_price": _f(d["unit_price"]), "total": _f(d["line_total"]),
        "invoice_number": d["invoice_number"], "customer": d["customer_name"] or "عميل عادي",
        "date": d["created_at"].isoformat(), "entry_type": entry_type,
    }
    if entry_type == "sale":
        out["payment_method"] = d["wallet_name"] or ("نقدي" if d["payment_method"] == "cash" else d["payment_method"])
    return out


async def get_ledger(db: AsyncSession, from_date: date, to_date: date, branches: list[uuid.UUID] | None = None,
                     page: int = 1, page_size: int = 100, warehouse_id: uuid.UUID | None = None) -> dict[str, Any]:
    start, end = day_bounds(from_date, to_date)
    offset = (page - 1) * page_size
    wh_s, wh_p = _branch("s", branches)
    wh_t, _ = _branch("sh", branches)
    params = {"start": start, "end": end, **wh_p}
    page_params = {**params, "offset": offset, "limit": page_size}

    sales_rows = (await db.execute(text(SALE_LINES.format(wh=wh_s)), {**page_params, "status": "confirmed"})).mappings().all()
    return_rows = (await db.execute(text(SALE_LINES.format(wh=wh_s)), {**page_params, "status": "returned"})).mappings().all()
    tx_rows = (await db.execute(text(DRAWER_ROWS.format(wh=wh_t)), page_params)).mappings().all()
    inv = (await db.execute(text(INVOICE_TOTALS.format(wh=wh_s)), params)).mappings().one()
    drw = (await db.execute(text(DRAWER_TOTALS.format(wh=wh_t)), params)).mappings().one()

    expenses = []
    for d in tx_rows:
        pm = d["wallet_name"] or ("نقدي" if (d["payment_method"] or "cash") == "cash" else d["payment_method"])
        expenses.append({"tx_id": str(d["id"]), "type_ar": TX_AR.get(d["type"], d["type"]), "note": d["note"] or "",
                         "amount": _f(d["amount"]), "payment_method": pm, "date": d["created_at"].isoformat(),
                         "entry_type": d["type"]})

    # Opening balance of one branch: what the last shift closed before the period left in the drawer.
    opening = ZERO
    if warehouse_id:
        left = await db.scalar(text("""
            SELECT COALESCE(next_day_drawer, closing_balance, 0) FROM shifts
            WHERE warehouse_id = :wh AND status = 'closed' AND closed_at < :start
            ORDER BY closed_at DESC LIMIT 1
        """), {"wh": warehouse_id, "start": start})
        if left is None:
            left = await db.scalar(text("""
                SELECT initial_amount FROM shifts WHERE warehouse_id = :wh AND started_at >= :start AND started_at < :end
                ORDER BY started_at ASC LIMIT 1
            """), {"wh": warehouse_id, "start": start, "end": end})
        opening = Decimal(str(left or 0))

    total_sales, total_returns = Decimal(inv["total_sales"]), Decimal(inv["total_returns"])
    total_expenses, total_deposits = Decimal(drw["total_expenses"]), Decimal(drw["total_deposits"])
    net = total_sales - total_returns - total_expenses
    net_with_deposits = net + total_deposits
    cash_closing = (opening + Decimal(drw["drawer_sales"]) - Decimal(drw["drawer_returns"])
                    + Decimal(drw["cash_deposits"]) - Decimal(drw["cash_expenses"]))
    n_sales, n_returns, n_tx = int(inv["sale_lines"]), int(inv["return_lines"]), int(drw["n_movements"])

    return {
        "sale_items": [_sale_line(dict(d), "sale") for d in sales_rows],
        "returns": [_sale_line(dict(d), "return") for d in return_rows],
        "expenses": expenses,
        "summary": {
            "opening_balance": _f(opening),
            "total_sales": _f(total_sales),
            "cash_sales": _f(inv["cash_sales"]),
            "wallet_sales": _f(inv["wallet_sales"]),
            "credit_sales": _f(inv["credit_sales"]),
            "total_returns": _f(total_returns),
            "total_expenses": _f(total_expenses),
            "total_deposits": _f(total_deposits),
            "total_revenue_delivery": 0.0,
            "net": _f(net),
            "net_with_deposits": _f(net_with_deposits),
            "closing": _f(opening + net_with_deposits),
            "cash_closing": _f(cash_closing),
        },
        "pagination": {
            "sales": {"total": n_sales, "page": page, "size": page_size, "pages": _pages(n_sales, page_size)},
            "returns": {"total": n_returns, "page": page, "size": page_size, "pages": _pages(n_returns, page_size)},
            "expenses": {"total": n_tx, "page": page, "size": page_size, "pages": _pages(n_tx, page_size)},
        },
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
    }
