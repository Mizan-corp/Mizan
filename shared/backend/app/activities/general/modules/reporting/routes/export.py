"""Excel exports. Columns have Arabic titles (written even when there is no row), money and
quantities are number cells, dates are date cells, statuses and payment methods are Arabic words;
at most EXPORT_LIMIT rows. Sales, stock, expenses and purchases follow the user's branches
(scope.py); stock costs only with `reports:finance`."""
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
    "supplier": "المورد", "total_cost": "إجمالي التكلفة", "tax_amount": "ضريبة القيمة المضافة",
}
STATUSES = {"confirmed": "مؤكدة", "returned": "مرتجع", "draft": "مسودة", "approved": "معتمد", "rejected": "مرفوض",
            "cancelled": "ملغى", "received": "مستلم", "partial": "مستلم جزئيًا", "pending": "قيد الانتظار",
            "tracked": "متتبع", "untracked": "غير متتبع"}
METHODS = {"cash": "نقدي", "card": "بطاقة", "bank": "تحويل بنكي", "cheque": "شيك", "wallet": "محفظة", "credit": "آجل",
           "safe": "نقدي من خزنة", "payroll": "رواتب", "split": "مقسم"}
MONEY_FORMAT = "#,##0.00"
QTY_FORMAT = "#,##0.###"


def _cell(ws, row: int, col: int, val, key: str) -> None:
    if isinstance(val, bool):
        ws.cell(row=row, column=col, value="نعم" if val else "لا")
    elif isinstance(val, (Decimal, float, int)):
        c = ws.cell(row=row, column=col, value=float(val) if isinstance(val, Decimal) else val)
        if key == "qty":
            c.number_format = QTY_FORMAT
        elif not isinstance(val, int):
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
        if key in ("status", "stock_status"):
            text_val = STATUSES.get(text_val, text_val)
        elif key == "payment_method":
            text_val = METHODS.get(text_val, text_val)
        ws.cell(row=row, column=col, value=text_val)


async def _to_excel(rows: list[dict], sheet_name: str = "Sheet1", keys: list[str] | None = None) -> bytes:
    """One sheet, right to left: a header row of Arabic titles (`keys`, else the first row's), then
    the rows. An export with no row still has its header."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.sheet_view.rightToLeft = True
    keys = keys if keys is not None else (list(rows[0].keys()) if rows else [])
    for ci, k in enumerate(keys, 1):
        cell = ws.cell(row=1, column=ci, value=TITLES.get(k, k))
        cell.fill = PatternFill(start_color="1e3a5f", end_color="1e3a5f", fill_type="solid")
        cell.font = Font(bold=True, color="ffffff", size=11)
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = 20
    ws.freeze_panes = "A2"
    for ri, row in enumerate(rows, 2):
        for ci, k in enumerate(keys, 1):
            _cell(ws, ri, ci, row.get(k), k)
    wb.save(buf := io.BytesIO())
    return buf.getvalue()


def _download(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(io.BytesIO(data), media_type=XLSX, headers={"Content-Disposition": f"attachment; filename={filename}"})


async def _sheet(db: AsyncSession, sql: str, params: dict, sheet_name: str, record: str | None = None) -> bytes:
    """The query's rows as a sheet; with `record`, plus one column per custom field of the record."""
    result = await db.execute(text(sql), params)
    keys = list(result.keys())
    rows = [dict(r) for r in result.mappings().fetchall()]
    if record:
        rows, keys = await _with_fields(db, record, rows, keys)
    return await _to_excel(rows, sheet_name, keys)


async def _with_fields(db: AsyncSession, record: str, rows: list[dict], keys: list[str]) -> tuple[list[dict], list[str]]:
    """The rows with one column per custom field of the record (titled by its label), taken from
    the row's `extra` (ADR-006 phase 5: custom fields are usable in reports), and the columns."""
    from app.framework.fields import fields_for
    from app.framework.hooks import workspace_activity

    fields = await fields_for(db, record, await workspace_activity(db))
    keys = [k for k in keys if k != "extra"]
    titles = []
    for f in fields:
        title = f.get("label") or f["key"]
        titles.append((f["key"], title if title not in keys and title not in [t for _, t in titles] else f"{title} ({f['key']})"))
    out = []
    for row in rows:
        extra = row.pop("extra", None) or {}
        for key, title in titles:
            value = extra.get(key)
            row[title] = ("نعم" if value else "لا") if isinstance(value, bool) else value
        out.append(row)
    return out, keys + [t for _, t in titles]


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
    data = await _sheet(db, f"""
        SELECT p.name, p.company, p.unit, p.retail_price, p.wholesale_price{cost},
               c.name as category, s.name as subcategory, p.stock_status, p.extra
        FROM products p
        LEFT JOIN subcategories s ON s.id = p.subcategory_id
        LEFT JOIN categories c ON c.id = s.category_id
        ORDER BY p.name LIMIT :lim
    """, {"lim": EXPORT_LIMIT}, "المنتجات", "product")
    return _download(data, "products.xlsx")


@router.get("/sales")
async def export_sales(from_date: date | None = None, to_date: date | None = None, warehouse_id: uuid.UUID | None = None,
                       db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("reports"))):
    scope = await branch_scope(db, user, warehouse_id)
    params: dict = {"lim": EXPORT_LIMIT}
    where = ("(s.status = 'confirmed' OR (s.status = 'returned' AND s.return_of IS NOT NULL))"
             + scope.sql("s.warehouse_id", params) + _dates("s.created_at", from_date, to_date, params))
    data = await _sheet(db, f"""
        SELECT s.invoice_number, (s.created_at AT TIME ZONE '{TZ_NAME}')::date AS date, c.name as customer,
               s.total, s.discount_amount, s.net_total, COALESCE(s.tax_amount, 0) AS tax_amount, s.paid_amount, s.is_credit,
               s.payment_method, u.full_name as cashier, CAST(s.status AS text) AS status, w.name as warehouse, s.extra
        FROM sales s
        LEFT JOIN customers c ON c.id = s.customer_id
        LEFT JOIN users u ON u.id = s.cashier_id
        LEFT JOIN warehouses w ON w.id = s.warehouse_id
        WHERE {where}
        ORDER BY s.created_at DESC LIMIT :lim
    """, params, "المبيعات", "sale")
    return _download(data, "sales.xlsx")


@router.get("/stock")
async def export_stock(warehouse_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("inventory"))):
    """Each tracked product in each branch, its quantity from the maintained balances
    (`stock_balances`, not a sum over every movement, REP-14)."""
    scope = await branch_scope(db, user, warehouse_id)
    params: dict = {"lim": EXPORT_LIMIT}
    cost = (", COALESCE(NULLIF(p.avg_cost, 0), p.cost_price, 0) AS cost_price, "
            "COALESCE(b.qty, 0) * COALESCE(NULLIF(p.avg_cost, 0), p.cost_price, 0) AS stock_value") if can(user, FINANCE) else ""
    data = await _sheet(db, f"""
        SELECT p.name, p.company, w.name AS warehouse, COALESCE(b.qty, 0) AS qty, p.unit, p.retail_price{cost}, p.extra
        FROM products p CROSS JOIN warehouses w
        LEFT JOIN stock_balances b ON b.product_id = p.id AND b.warehouse_id = w.id
        WHERE p.stock_status = 'tracked'{scope.sql('w.id', params)}
        ORDER BY p.name, w.name LIMIT :lim
    """, params, "المخزون", "product")
    return _download(data, "stock.xlsx")


@router.get("/customers")
async def export_customers(db: AsyncSession = Depends(get_db), _=Depends(require_perm("customers"))):
    require_workspace()
    data = await _sheet(db, """
        SELECT c.name, c.phone, c.balance, c.credit_limit, c.extra FROM customers c ORDER BY c.name LIMIT :lim
    """, {"lim": EXPORT_LIMIT}, "العملاء", "customer")
    return _download(data, "customers.xlsx")


@router.get("/suppliers")
async def export_suppliers(db: AsyncSession = Depends(get_db), _=Depends(require_perm("purchases"))):
    require_workspace()
    data = await _sheet(db, """
        SELECT s.name, s.phone, s.balance, s.extra FROM suppliers s ORDER BY s.name LIMIT :lim
    """, {"lim": EXPORT_LIMIT}, "الموردون", "supplier")
    return _download(data, "suppliers.xlsx")


@router.get("/expenses")
async def export_expenses(from_date: date | None = None, to_date: date | None = None, warehouse_id: uuid.UUID | None = None,
                          db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("finance"))):
    scope = await branch_scope(db, user, warehouse_id)
    params: dict = {"lim": EXPORT_LIMIT}
    where = "true" + scope.sql("e.warehouse_id", params) + _dates("e.date", from_date, to_date, params, local=False)
    data = await _sheet(db, f"""
        SELECT e.date, e.description, e.amount, ev.name as vendor, e.status, e.payment_method, e.is_recurring
        FROM expenses e LEFT JOIN expense_vendors ev ON ev.id = e.vendor_id
        WHERE {where}
        ORDER BY e.date DESC LIMIT :lim
    """, params, "المصروفات")
    return _download(data, "expenses.xlsx")


@router.get("/purchases")
async def export_purchases(from_date: date | None = None, to_date: date | None = None, warehouse_id: uuid.UUID | None = None,
                           db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("purchases"))):
    scope = await branch_scope(db, user, warehouse_id)
    params: dict = {"lim": EXPORT_LIMIT}
    where = "true" + scope.sql("p.warehouse_id", params) + _dates("p.created_at", from_date, to_date, params)
    data = await _sheet(db, f"""
        SELECT p.po_number, (p.created_at AT TIME ZONE '{TZ_NAME}')::date AS date, s.name as supplier,
               COALESCE((SELECT SUM(qty_ordered * unit_cost) FROM purchase_order_items WHERE po_id = p.id), 0) as total_cost,
               CAST(p.status AS text) AS status, w.name as warehouse
        FROM purchase_orders p
        LEFT JOIN suppliers s ON s.id = p.supplier_id
        LEFT JOIN warehouses w ON w.id = p.warehouse_id
        WHERE {where}
        ORDER BY p.created_at DESC LIMIT :lim
    """, params, "المشتريات")
    return _download(data, "purchases.xlsx")
