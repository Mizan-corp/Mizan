import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_perm, verify_warehouse_access
from app.platform.auth.models.user import User
from app.modules.general.reporting import service as report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/sales/daily")
async def daily_sales(target_date: date = Query(default_factory=date.today), warehouse_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await verify_warehouse_access(db, current_user, uuid.UUID(warehouse_id) if warehouse_id else None)
    return await report_service.daily_sales(db, target_date, warehouse_id=warehouse_id)


@router.get("/sales/trend")
async def sales_trend(days: int = Query(14, ge=1, le=92), warehouse_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Net sales per day, oldest first (the dashboard's trend widget)."""
    await verify_warehouse_access(db, current_user, uuid.UUID(warehouse_id) if warehouse_id else None)
    return await report_service.sales_trend(db, days, warehouse_id=warehouse_id)


@router.get("/sales/monthly")
async def monthly_sales(year: int, month: int, warehouse_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await verify_warehouse_access(db, current_user, uuid.UUID(warehouse_id) if warehouse_id else None)
    return await report_service.monthly_sales(db, year, month, warehouse_id=warehouse_id)


@router.get("/sales/top-products")
async def top_products(from_date: str, to_date: str, limit: int = 10, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    return await report_service.top_products(db, from_date, to_date, limit)


@router.get("/sales/by-cashier")
async def sales_by_cashier(from_date: str, to_date: str, warehouse_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await verify_warehouse_access(db, current_user, uuid.UUID(warehouse_id) if warehouse_id else None)
    return await report_service.sales_by_cashier(db, from_date, to_date, warehouse_id=warehouse_id)


@router.get("/profit")
async def profit(from_date: str, to_date: str, warehouse_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await verify_warehouse_access(db, current_user, uuid.UUID(warehouse_id) if warehouse_id else None)
    return await report_service.profit_report(db, from_date, to_date, warehouse_id=warehouse_id)


@router.get("/inventory/print")
async def inventory_print_report(warehouse_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """تقرير المخزون الكامل للطباعة."""
    await verify_warehouse_access(db, current_user, uuid.UUID(warehouse_id))
    return await report_service.inventory_print_report(db, warehouse_id)


@router.get("/ledger/daily-items")
async def daily_items(target_date: date = Query(default_factory=date.today), warehouse_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Daily ledger: each product sold with qty, price, total, returns, expenses."""
    await verify_warehouse_access(db, current_user, uuid.UUID(warehouse_id) if warehouse_id else None)
    return await report_service.daily_items(db, target_date, warehouse_id=warehouse_id)


@router.get("/ledger/periodic")
async def periodic_ledger(period: str = "weekly", warehouse_id: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Weekly / monthly / yearly summary: income, expenses, net."""
    await verify_warehouse_access(db, current_user, uuid.UUID(warehouse_id) if warehouse_id else None)
    return await report_service.periodic_ledger(db, period, warehouse_id=warehouse_id)


@router.get("/cash-flow")
async def cash_flow(
    from_date: str = Query(...),
    to_date: str = Query(...),
    warehouse_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Formal cash flow: incoming (sales, collections) vs outgoing (purchases, expenses, payroll)."""
    await verify_warehouse_access(db, current_user, uuid.UUID(warehouse_id) if warehouse_id else None)
    return await report_service.cash_flow(db, from_date, to_date, warehouse_id=warehouse_id)


@router.get("/aging")
async def aging_report(
    as_of: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Aging report: customer and supplier debts split into 0-30 / 30-60 / 60-90 / 90+ day buckets."""
    return await report_service.aging_report(db, as_of=as_of)


# Custom fields in reports (ADR-006 phase 5): records counted (and sales totalled) by a field's value.
_FIELD_REPORT_TABLES = {"product": "products", "customer": "customers", "supplier": "suppliers", "sale": "sales"}


@router.get("/fields/{record}/{key}")
async def by_custom_field(record: str, key: str, from_date: date | None = None, to_date: date | None = None,
                          db: AsyncSession = Depends(get_db), _=Depends(require_perm("reports"))):
    """How many records have each value of a custom field; for sales, their net total too
    (confirmed sales, optionally in a date range). Records without a value are grouped as null."""
    from fastapi import HTTPException
    from sqlalchemy import text

    from app.framework.fields import fields_for
    from app.framework.hooks import workspace_activity

    table = _FIELD_REPORT_TABLES.get(record)
    if table is None:
        raise HTTPException(404, "سجل غير معروف")
    field = next((f for f in await fields_for(db, record, await workspace_activity(db), include_hidden=True) if f["key"] == key), None)
    if field is None:
        raise HTTPException(404, "حقل غير معروف")
    where, params = ["true"], {"k": key}
    if record == "sale":
        where.append("status = 'confirmed'")
        if from_date:
            where.append("created_at >= CAST(:fd AS date)")
            params["fd"] = from_date
        if to_date:
            where.append("created_at < CAST(:td AS date) + 1")
            params["td"] = to_date
    total = ", COALESCE(SUM(net_total), 0) AS total" if record == "sale" else ""
    rows = (await db.execute(text(f"""
        SELECT extra ->> :k AS value, COUNT(*) AS count{total}
        FROM {table} WHERE {' AND '.join(where)}
        GROUP BY 1 ORDER BY 2 DESC, 1 NULLS LAST LIMIT 200
    """), params)).mappings().all()
    return {"record": record, "field": {k: field.get(k) for k in ("key", "label", "type", "options")},
            "rows": [dict(r) for r in rows]}
