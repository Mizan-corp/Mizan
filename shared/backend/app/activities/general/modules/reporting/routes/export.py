"""Excel exports. Columns have Arabic titles, money and quantities are number cells and dates are
date cells; at most EXPORT_LIMIT rows. Sales, stock, expenses and purchases follow the user's
branches (scope.py); stock costs only with `reports:finance`."""
import io
import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.reporting.scope import FINANCE, TZ, TZ_NAME, branch_scope, day_range, require_workspace
from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.auth.models.user import User
from app.platform.permissions.access import can

router = APIRouter(prefix="/export", tags=["export"])

EXPORT_LIMIT = 50000
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

TITLES = {
    "name": "الاسم", "company": "الشركة", "unit": "الوحدة", "retail_price": "سعر البيع", "wholesale_price": "سعر الجملة",
    "cost_price": "سعر التكلفة", "category": "التصنيف", "subcategory": "التصنيف الفرعي", "stock_status": "تتبع المخزون",
    "invoice_number": "رقم الفاتورة", "date": "التاريخ", "customer": "العميل", "total": "الإجمالي",
    "discount_amount": "خصم الفاتورة", "net_total": "الصافي", "paid_amount": "المدفوع", "is_credit": "آجل",
    "payment_method": "طريقة الدفع", "cashier": "الكاشير", "status": "الحالة", "warehouse": "الفرع", "qty": "الكمية",
    "stock_value": "قيمة المخزون بالتكلفة", "phone": "الهاتف", "balance": "الرصيد", "credit_limit": "حد الائتمان",
    "description": "البيان", "amount": "المبلغ", "vendor": "المورد", "is_recurring": "متكرر", "po_number": "رقم أمر الشراء",
    "supplier": "المورد", "total_cost": "إجمالي التكلفة",
}
STATUSES = {"confirmed": "مؤكدة", "returned": "مرتجع", "draft": "مسودة", "approved": "معتمد", "rejected": "مرفوض",
            "cancelled": "ملغى", "received": "مستلم", "partial": "مستلم جزئيًا", "pending": "قيد الانتظار",
            "tracked": "متتبع", "untracked": "غير متتبع"}
MONEY_FORMAT = "#,##0.00"


def _cell(ws, row: int, col: int, val, key: str) -> None:
    if isinstance(val, bool):
        ws.cell(row=row, column=col, value="نعم" if val else "لا")
    elif isinstance(val, (Decimal, float, int)):
        c = ws.cell(row=row, column=col, value=float(val) if isinstance(val, Decimal) else val)
        if key != "qty" and not isinstance(val, int):
            c.number_format = MONEY_FORMAT
    elif isinstance(val, datetime):
        c = ws.cell(row=row, column=col, value=val.astimezone(TZ).replace(tzinfo=None) if val.tzinfo else val)
        c.number_format = "yyyy-mm-dd hh:mm"
    elif isinstance(val, date):
        ws.cell(row=row, column=col, value=val).number_format = "yyyy-mm-dd"
    elif val is None:
        ws.cell(row=row, column=col, value="")
    else:
        val = getattr(val, "value", val)
        text_val = str(val)
        ws.cell(row=row, column=col, value=STATUSES.get(text_val, text_val) if key in ("status", "stock_status") else text_val)


async def _to_excel(rows: list[dict], sheet_name: str = "Sheet1") -> bytes:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.sheet_view.rightToLeft = True
    if rows:
        keys = list(rows[0].keys())
        for ci, k in enumerate(keys, 1):
            cell = ws.cell(row=1, column=ci, value=TITLES.get(k, k))
            cell.fill = PatternFill(start_color="1e3a5f", end_color="1e3a5f", fill_type="solid")
            cell.font = Font(bold=True, color="ffffff", size=11)
            cell.alignment = Alignment(horizontal="center")
            ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = 20
        for ri, row in enumerate(rows, 2):
            for ci, k in enumerate(keys, 1):
                _cell(ws, ri, ci, row[k], k)
    wb.save(buf := io.BytesIO())
    return buf.getvalue()


def _download(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(io.BytesIO(data), media_type=XLSX, headers={"Content-Disposition": f"attachment; filename={filename}"})


async def _with_fields(db: AsyncSession, record: str, rows) -> list[dict]:
    """The rows with one column per custom field of the record (titled by its label), taken from
    the row's `extra` (ADR-006 phase 5: custom fields are usable in reports)."""
    from app.framework.fields import fields_for
    from app.framework.hooks import workspace_activity

    fields = await fields_for(db, record, await workspace_activity(db))
    out = []
    for r in rows:
        row = dict(r)
        extra = row.pop("extra", None) or {}
        for f in fields:
            title = f.get("label") or f["key"]
            value = extra.get(f["key"])
            row[title if title not in row else f"{title} ({f['key']})"] = ("نعم" if value else "لا") if isinstance(value, bool) else value
        out.append(row)
    return out


def _dates(column: str, from_date: date | None, to_date: date | None, params: dict, local: bool = True) -> str:
    """A date filter on a timestamp column (whole days in the workspace's time zone) or a date column."""
    if not (from_date or to_date):
        return ""
    if local:
        start, end = day_range(from_date or date(2000, 1, 1), to_date or datetime.now(TZ).date())
        params.update(fd=start, td=end)
        return f" AND {column} >= :fd AND {column} < :td"
    sql = ""
    if from_date:
        sql += f" AND {column} >= :fd"
        params["fd"] = from_date
    if to_date:
        sql += f" AND {column} <= :td"
        params["td"] = to_date
    if from_date and to_date:
        day_range(from_date, to_date)
    return sql


@router.get("/products")
async def export_products(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("inventory"))):
    """The product list; the cost price only with `reports:finance` (as the stock export)."""
    require_workspace()
    cost = ", p.cost_price" if can(user, FINANCE) else ""
    rows = (await db.execute(text(f"""
        SELECT p.name, p.company, p.unit, p.retail_price, p.wholesale_price{cost},
               c.name as category, s.name as subcategory, p.stock_status, p.extra
        FROM products p
        LEFT JOIN subcategories s ON s.id = p.subcategory_id
        LEFT JOIN categories c ON c.id = s.category_id
        ORDER BY p.name LIMIT :lim
    """), {"lim": EXPORT_LIMIT})).mappings().fetchall()
    return _download(await _to_excel(await _with_fields(db, "product", rows), "المنتجات"), "products.xlsx")


@router.get("/sales")
async def export_sales(from_date: date | None = None, to_date: date | None = None, warehouse_id: uuid.UUID | None = None,
                       db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("reports"))):
    scope = await branch_scope(db, user, warehouse_id)
    params: dict = {"lim": EXPORT_LIMIT}
    where = ("(s.status = 'confirmed' OR (s.status = 'returned' AND s.return_of IS NOT NULL))"
             + scope.sql("s.warehouse_id", params) + _dates("s.created_at", from_date, to_date, params))
    rows = (await db.execute(text(f"""
        SELECT s.invoice_number, (s.created_at AT TIME ZONE '{TZ_NAME}')::date AS date, c.name as customer,
               s.total, s.discount_amount, s.net_total, s.paid_amount, s.is_credit,
               s.payment_method, u.full_name as cashier, CAST(s.status AS text) AS status, w.name as warehouse, s.extra
        FROM sales s
        LEFT JOIN customers c ON c.id = s.customer_id
        LEFT JOIN users u ON u.id = s.cashier_id
        LEFT JOIN warehouses w ON w.id = s.warehouse_id
        WHERE {where}
        ORDER BY s.created_at DESC LIMIT :lim
    """), params)).mappings().fetchall()
    return _download(await _to_excel(await _with_fields(db, "sale", rows), "المبيعات"), "sales.xlsx")


@router.get("/stock")
async def export_stock(warehouse_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("inventory"))):
    from app.activities.general.modules.inventory.models.stock import IN_TYPES

    scope = await branch_scope(db, user, warehouse_id)
    params: dict = {"lim": EXPORT_LIMIT, "ins": list(IN_TYPES)}
    cost = (", COALESCE(NULLIF(p.avg_cost, 0), p.cost_price, 0) AS cost_price, "
            "COALESCE(b.qty, 0) * COALESCE(NULLIF(p.avg_cost, 0), p.cost_price, 0) AS stock_value") if can(user, FINANCE) else ""
    rows = (await db.execute(text(f"""
        WITH b AS (
            SELECT product_id, warehouse_id,
                   SUM(CASE WHEN CAST(movement_type AS text) = ANY(:ins) THEN qty ELSE -qty END) AS qty
            FROM stock_movements GROUP BY product_id, warehouse_id
        )
        SELECT p.name, p.company, w.name AS warehouse, COALESCE(b.qty, 0) AS qty, p.unit, p.retail_price{cost}, p.extra
        FROM products p CROSS JOIN warehouses w
        LEFT JOIN b ON b.product_id = p.id AND b.warehouse_id = w.id
        WHERE p.stock_status = 'tracked'{scope.sql('w.id', params)}
        ORDER BY p.name, w.name LIMIT :lim
    """), params)).mappings().fetchall()
    return _download(await _to_excel(await _with_fields(db, "product", rows), "المخزون"), "stock.xlsx")


@router.get("/customers")
async def export_customers(db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers"))):
    require_workspace()
    rows = (await db.execute(text("""
        SELECT c.name, c.phone, c.balance, c.credit_limit, c.extra FROM customers c ORDER BY c.name LIMIT :lim
    """), {"lim": EXPORT_LIMIT})).mappings().fetchall()
    return _download(await _to_excel(await _with_fields(db, "customer", rows), "العملاء"), "customers.xlsx")


@router.get("/suppliers")
async def export_suppliers(db: AsyncSession = Depends(get_db), _=Depends(require_perm("purchases"))):
    require_workspace()
    rows = (await db.execute(text("""
        SELECT s.name, s.phone, s.balance, s.extra FROM suppliers s ORDER BY s.name LIMIT :lim
    """), {"lim": EXPORT_LIMIT})).mappings().fetchall()
    return _download(await _to_excel(await _with_fields(db, "supplier", rows), "الموردون"), "suppliers.xlsx")


@router.get("/expenses")
async def export_expenses(from_date: date | None = None, to_date: date | None = None, warehouse_id: uuid.UUID | None = None,
                          db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("finance"))):
    scope = await branch_scope(db, user, warehouse_id)
    params: dict = {"lim": EXPORT_LIMIT}
    where = "true" + scope.sql("e.warehouse_id", params) + _dates("e.date", from_date, to_date, params, local=False)
    rows = (await db.execute(text(f"""
        SELECT e.date, e.description, e.amount, ev.name as vendor, e.status, e.payment_method, e.is_recurring
        FROM expenses e LEFT JOIN expense_vendors ev ON ev.id = e.vendor_id
        WHERE {where}
        ORDER BY e.date DESC LIMIT :lim
    """), params)).mappings().fetchall()
    return _download(await _to_excel([dict(r) for r in rows], "المصروفات"), "expenses.xlsx")


@router.get("/purchases")
async def export_purchases(from_date: date | None = None, to_date: date | None = None, warehouse_id: uuid.UUID | None = None,
                           db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("purchases"))):
    scope = await branch_scope(db, user, warehouse_id)
    params: dict = {"lim": EXPORT_LIMIT}
    where = "true" + scope.sql("p.warehouse_id", params) + _dates("p.created_at", from_date, to_date, params)
    rows = (await db.execute(text(f"""
        SELECT p.po_number, (p.created_at AT TIME ZONE '{TZ_NAME}')::date AS date, s.name as supplier,
               COALESCE((SELECT SUM(qty_ordered * unit_cost) FROM purchase_order_items WHERE po_id = p.id), 0) as total_cost,
               CAST(p.status AS text) AS status, w.name as warehouse
        FROM purchase_orders p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        LEFT JOIN warehouses w ON w.id = p.warehouse_id
        WHERE {where}
        ORDER BY p.created_at DESC LIMIT :lim
    """), params)).mappings().fetchall()
    return _download(await _to_excel([dict(r) for r in rows], "المشتريات"), "purchases.xlsx")
