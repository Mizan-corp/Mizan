"""The report routes. Every route needs `reports` (the dashboard's today/trend widgets also accept
`pos`); profit, cash flow, debts' aging need `reports:finance`. Each is limited to the branches the
user reaches (scope.py): an empty branch filter means "my branches", never the whole company."""
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.reporting import service as report_service
from app.activities.general.modules.reporting.scope import FINANCE, branch_scope, day_range, today
from app.db.base import get_db
from app.dependencies import get_print_user, require_perm
from app.platform.auth.models.user import User
from app.platform.permissions.access import can
from app.platform.printing.routes import PrintRoute

router = APIRouter(prefix="/reports", tags=["reports"])

SALES = require_perm("reports")
WIDGET = require_perm("reports", "pos")  # the "today's revenue" widget is shown to cashiers too
MONEY = require_perm(FINANCE)


@router.get("/sales/daily")
async def daily_sales(target_date: date | None = None, warehouse_id: uuid.UUID | None = None,
                      db: AsyncSession = Depends(get_db), user: User = Depends(WIDGET)):
    """Net sales of a day (default today, in the workspace's time zone), less its returns."""
    scope = await branch_scope(db, user, warehouse_id)
    return await report_service.daily_sales(db, target_date or today(), scope)


@router.get("/sales/trend")
async def sales_trend(days: int = Query(14, ge=1, le=92), warehouse_id: uuid.UUID | None = None,
                      db: AsyncSession = Depends(get_db), user: User = Depends(WIDGET)):
    """Net sales per day, oldest first (the dashboard's trend widget)."""
    scope = await branch_scope(db, user, warehouse_id)
    return await report_service.sales_trend(db, days, scope)


@router.get("/sales/monthly")
async def monthly_sales(year: int = Query(..., ge=2000, le=2100), month: int = Query(..., ge=1, le=12),
                        warehouse_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                        user: User = Depends(SALES)):
    scope = await branch_scope(db, user, warehouse_id)
    return await report_service.monthly_sales(db, year, month, scope)


@router.get("/sales/top-products")
async def top_products(from_date: date, to_date: date, limit: int = Query(10, ge=1, le=100),
                       warehouse_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                       user: User = Depends(SALES)):
    scope = await branch_scope(db, user, warehouse_id)
    return await report_service.top_products(db, from_date, to_date, scope, limit)


@router.get("/sales/by-cashier")
async def sales_by_cashier(from_date: date, to_date: date, warehouse_id: uuid.UUID | None = None,
                           db: AsyncSession = Depends(get_db), user: User = Depends(SALES)):
    scope = await branch_scope(db, user, warehouse_id)
    return await report_service.sales_by_cashier(db, from_date, to_date, scope)


@router.get("/profit")
async def profit(from_date: date, to_date: date, warehouse_id: uuid.UUID | None = None,
                 db: AsyncSession = Depends(get_db), user: User = Depends(MONEY)):
    scope = await branch_scope(db, user, warehouse_id)
    out = await report_service.profit_report(db, from_date, to_date, scope)
    await db.commit()  # the ledger's chart may just have been copied (accounting/services/chart.py)
    return out


async def inventory_print_report(warehouse_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                                 user: User = Depends(get_print_user)):
    """The branch's stock count sheet, printable (open with a print token, POST /auth/print-token).
    Needs `reports` or `inventory`; costs and the value at cost only with `reports:finance`. In a
    browser tab, errors are an Arabic page (the print system's PrintRoute)."""
    from app.activities.general.modules.reporting.printing import inventory_html

    if not can(user, "reports", "inventory"):
        raise HTTPException(403, "ليس لديك صلاحية طباعة تقرير المخزون")
    await branch_scope(db, user, warehouse_id)
    data = await report_service.inventory_print_report(db, warehouse_id, with_cost=can(user, FINANCE))
    return HTMLResponse(inventory_html(data))


router.add_api_route("/inventory/print", inventory_print_report, methods=["GET"], response_class=HTMLResponse,
                     route_class_override=PrintRoute)


@router.get("/ledger/daily-items")
async def daily_items(target_date: date | None = None, warehouse_id: uuid.UUID | None = None,
                      db: AsyncSession = Depends(get_db), user: User = Depends(SALES)):
    """Daily ledger: each product sold with qty, price, total, returns, and the drawer expenses."""
    scope = await branch_scope(db, user, warehouse_id)
    return await report_service.daily_items(db, target_date or today(), scope)


@router.get("/ledger/periodic")
async def periodic_ledger(period: Literal["weekly", "monthly", "yearly"] = "weekly", warehouse_id: uuid.UUID | None = None,
                          db: AsyncSession = Depends(get_db), user: User = Depends(SALES)):
    """Weekly / monthly / yearly summary: income, returns, expenses, net (the last 52 periods)."""
    scope = await branch_scope(db, user, warehouse_id)
    return await report_service.periodic_ledger(db, period, scope)


@router.get("/cash-flow")
async def cash_flow(from_date: date, to_date: date, warehouse_id: uuid.UUID | None = None,
                    db: AsyncSession = Depends(get_db), user: User = Depends(MONEY)):
    """Money in and out in the period (sales paid, collections, payments, expenses, salaries)."""
    scope = await branch_scope(db, user, warehouse_id)
    return await report_service.cash_flow(db, from_date, to_date, scope)


@router.get("/aging")
async def aging_report(as_of: date | None = None, warehouse_id: uuid.UUID | None = None,
                       db: AsyncSession = Depends(get_db), user: User = Depends(MONEY)):
    """Customers' and suppliers' open debts by age: 0-30 / 30-60 / 60-90 / 90+ days."""
    scope = await branch_scope(db, user, warehouse_id)
    return await report_service.aging_report(db, as_of or today(), scope)


# Custom fields in reports (ADR-006 phase 5): records counted (and sales totalled) by a field's value.
_FIELD_REPORT_TABLES = {"product": "products", "customer": "customers", "supplier": "suppliers", "sale": "sales"}


@router.get("/fields/{record}/{key}")
async def by_custom_field(record: str, key: str,
                          from_date: date | None = None, to_date: date | None = None,
                          warehouse_id: uuid.UUID | None = None,
                          db: AsyncSession = Depends(get_db), user: User = Depends(SALES)):
    """How many records have each value of a custom field. For sales: confirmed sales in the
    user's branches (optionally in a date range) and their net total without VAT, less the returns
    made in the range (counted under their sale's value). Records without a value are grouped as null."""
    from app.framework.fields import fields_for
    from app.framework.hooks import workspace_activity

    if record not in _FIELD_REPORT_TABLES:
        raise HTTPException(404, "سجل غير معروف")
    field = next((f for f in await fields_for(db, record, await workspace_activity(db), include_hidden=True) if f["key"] == key), None)
    if field is None:
        raise HTTPException(404, "حقل غير معروف")
    params: dict = {"k": key}
    if record != "sale":
        rows = (await db.execute(text(f"""
            SELECT extra ->> :k AS value, COUNT(*) AS count
            FROM {_FIELD_REPORT_TABLES[record]} GROUP BY 1 ORDER BY 2 DESC, 1 NULLS LAST LIMIT 200
        """), params)).mappings().all()
        out_rows = [dict(r) for r in rows]
    else:
        scope = await branch_scope(db, user, warehouse_id)
        where = report_service.DOCS + scope.sql("s.warehouse_id", params)
        if from_date or to_date:
            start, end = day_range(from_date or date(2000, 1, 1), to_date or today())
            where += " AND s.created_at >= :start AND s.created_at < :end"
            params.update(start=start, end=end)
        v = await report_service._vat_sql(db)
        rows = (await db.execute(text(f"""
            SELECT COALESCE(o.extra, s.extra) ->> :k AS value,
                   COUNT(*) FILTER (WHERE s.status = 'confirmed') AS count,
                   COALESCE(SUM({report_service.SIGN} * {v['doc']}), 0) AS total
            FROM sales s LEFT JOIN sales o ON o.id = s.return_of
            WHERE {where}
            GROUP BY 1 ORDER BY 2 DESC, 1 NULLS LAST LIMIT 200
        """), params)).mappings().all()
        out_rows = [{"value": r["value"], "count": r["count"], "total": report_service.money(r["total"])} for r in rows]
    return {"record": record, "field": {k: field.get(k) for k in ("key", "label", "type", "options")}, "rows": out_rows}
