import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.db.base import get_db
from app.dependencies import require_is_manager, require_open_period, require_perm, verify_warehouse_access
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.sales.models.sale import Sale, SaleItem, SaleStatus
from app.platform.auth.models.user import User
from app.activities.general.modules.sales.schemas import (
    ConfirmQuotationRequest,
    PartialReturnRequest,
    SaleCreate,
    SaleItemUpdate,
    SaleOut,
    SalesPage,
    SalesSummary,
    UpdateSale,
)
from app.activities.general.modules.sales.services import sales as sale_service

router = APIRouter(prefix="/sales", tags=["sales"])

# Reading sales: the sales screen or the POS (SAL-6).
_read = require_perm("sales", "pos")


async def _branches(db: AsyncSession, user: User) -> list[uuid.UUID] | None:
    """The branches whose sales the user sees: all for managers and supervisors (None), else
    the branches they are assigned (SAL-6)."""
    from app.platform.auth.models.user import user_warehouses
    from app.platform.permissions.access import can

    if user.is_manager or can(user, "supervise"):
        return None
    return list((await db.execute(select(user_warehouses.c.warehouse_id)
                                  .where(user_warehouses.c.user_id == user.id))).scalars().all())


async def _sale_in_reach(db: AsyncSession, sale_id: uuid.UUID, user: User) -> Sale:
    """The sale, in this workspace and in a branch the user reaches."""
    sale = (await db.execute(select(Sale).where(Sale.id == sale_id))).scalar_one_or_none()
    if not sale:
        raise NotFoundError("الفاتورة غير موجودة")
    await verify_warehouse_access(db, user, sale.warehouse_id)
    return sale


@router.post("", response_model=SaleOut)
async def create_sale(data: SaleCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("sales", "pos")), _=Depends(require_open_period)):
    if current_user.tenant_id:
        from app.platform.billing.services.plan_gating import check_sales_volume_limit
        await check_sales_volume_limit(db, current_user.tenant_id)
    await verify_warehouse_access(db, current_user, data.warehouse_id)
    sale = await sale_service.create_sale(db, data, current_user.id, actor=current_user)

    # Check stock after sale and notify manager if stock <= reorder_level
    product_ids = [item.product_id for item in data.items if hasattr(item, "product_id")]
    if product_ids and data.warehouse_id:
        try:
            from app.activities.general.modules.inventory.services.stock import check_low_stock_and_notify
            await check_low_stock_and_notify(db, current_user.tenant_id, product_ids, data.warehouse_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed low stock alert check: %s", e)

    return sale


@router.post("/draft", response_model=SaleOut)
async def create_draft(data: SaleCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("sales", "pos"))):
    """Save a draft sale — no stock deduction."""
    await verify_warehouse_access(db, current_user, data.warehouse_id)
    return await sale_service.create_draft_sale(db, data, current_user.id, actor=current_user)


@router.get("/drafts", response_model=list[SaleOut])
async def list_drafts(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0),
                      db: AsyncSession = Depends(get_db), current_user: User = Depends(_read)):
    """Draft sales, newest first, in the user's branches."""
    q = select(Sale).options(selectinload(Sale.items)).where(Sale.status == SaleStatus.draft)
    branches = await _branches(db, current_user)
    if branches is not None:
        q = q.where(Sale.warehouse_id.in_(branches))
    result = await db.execute(q.order_by(Sale.created_at.desc()).limit(limit).offset(offset))
    return result.scalars().all()


@router.put("/{sale_id}/confirm", response_model=SaleOut)
async def confirm_draft(sale_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("sales", "pos"))):
    """Confirm a draft sale — deduct stock, assign invoice number."""
    await _sale_in_reach(db, sale_id, current_user)
    return await sale_service.confirm_draft_sale(db, sale_id, current_user.id, actor=current_user)


def _may_change(user: User, sale: Sale) -> None:
    """Editing or deleting a document nothing was taken or paid for: a quotation with
    `quotations` or `sales`, a draft with `sales` or `pos` (those who make them)."""
    from app.platform.permissions.access import can

    if sale.status == SaleStatus.quotation and not can(user, "quotations", "sales"):
        raise HTTPException(403, "ليس لديك صلاحية تعديل عروض الأسعار")
    if sale.status == SaleStatus.draft and not can(user, "sales", "pos"):
        raise HTTPException(403, "ليس لديك صلاحية تعديل المسودات")


@router.delete("/{sale_id}", status_code=204)
async def delete_sale(sale_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(require_perm("sales", "pos", "quotations"))):
    """Delete a draft or quotation."""
    _may_change(current_user, await _sale_in_reach(db, sale_id, current_user))
    await sale_service.delete_draft_or_quotation(db, sale_id, current_user.id, actor=current_user)


# What the sales screen's tabs show: invoices (sales, returns, cancelled ones) or the documents
# nothing was taken or paid for yet (quotations and drafts).
_KINDS = {"invoices": ("confirmed", "returned", "cancelled"), "quotations": ("quotation", "draft")}


async def _filters(db: AsyncSession, user: User, *, from_date=None, to_date=None, cashier_id=None, warehouse_id=None,
                   status=None, kind=None, product_search=None, search=None) -> list:
    """The WHERE clauses of a sales list or summary (Sale joined to Customer). Days are the
    workspace's (Africa/Cairo), the last one whole; branches are the user's (SAL-6)."""
    from app.activities.general.modules.contacts.models.party import Customer
    from app.platform.tenancy.clock import day_bounds

    where = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        where.append(or_(Sale.invoice_number.ilike(term), Customer.name.ilike(term)))
    branches = await _branches(db, user)
    if branches is not None:
        where.append(Sale.warehouse_id.in_(branches))
    if warehouse_id:
        await verify_warehouse_access(db, user, warehouse_id)
        where.append(Sale.warehouse_id == warehouse_id)
    start, end = day_bounds(from_date, to_date)
    if start is not None:
        where.append(Sale.created_at >= start)
    if end is not None:
        where.append(Sale.created_at < end)
    if cashier_id:
        where.append(Sale.cashier_id == cashier_id)
    if status:
        where.append(Sale.status == status)
    if kind:
        where.append(Sale.status.in_(_KINDS[kind]))
    if product_search and product_search.strip():
        term = f"%{product_search.strip()}%"
        where.append(Sale.id.in_(select(SaleItem.sale_id).join(Product, Product.id == SaleItem.product_id)
                                 .where(Product.name.ilike(term))))
    return where


async def _rows_out(db: AsyncSession, rows) -> list[dict]:
    """The listed sales with their customer, creator and product names (one query each)."""
    user_ids = list({sale.created_by for sale, _ in rows if sale.created_by})
    user_names: dict = {}
    if user_ids:
        urows = await db.execute(text("SELECT id, full_name FROM users WHERE id = ANY(:ids)"), {"ids": user_ids})
        user_names = {r.id: r.full_name for r in urows.fetchall()}
    all_pids = list({i.product_id for s, _ in rows for i in (s.items or [])})
    pnames: dict = {}
    if all_pids:
        prod_rows = await db.execute(text("SELECT id, name FROM products WHERE id = ANY(:ids)"), {"ids": all_pids})
        pnames = {r.id: r.name for r in prod_rows.fetchall()}
    result = []
    for sale, cname in rows:
        d = SaleOut.model_validate(sale).model_dump()
        d["customer_name"] = cname
        d["created_by_name"] = user_names.get(sale.created_by, "")
        for item in d.get("items") or []:
            item["product_name"] = pnames.get(item["product_id"], "")
        result.append(d)
    return result


def _listing(where: list):
    from app.activities.general.modules.contacts.models.party import Customer

    return (select(Sale, Customer.name.label("customer_name")).outerjoin(Customer, Sale.customer_id == Customer.id)
            .where(*where))


@router.get("", response_model=list[SaleOut])
async def list_sales(
    from_date: date | None = None,
    to_date: date | None = None,
    cashier_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    status: SaleStatus | None = None,
    kind: Literal["invoices", "quotations"] | None = None,
    product_search: str | None = Query(None, max_length=200),
    search: str | None = Query(None, max_length=200),
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1, le=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read),
):
    """Sales, newest first, as a plain list (the POS widgets, the SDK). The sales screen uses
    /sales/page, which also gives the total."""
    if page_size is not None:
        limit = page_size
    if page is not None:
        offset = (page - 1) * limit
    where = await _filters(db, current_user, from_date=from_date, to_date=to_date, cashier_id=cashier_id,
                           warehouse_id=warehouse_id, status=status, kind=kind, product_search=product_search,
                           search=search)
    q = (_listing(where).options(selectinload(Sale.items))
         .order_by(Sale.created_at.desc(), Sale.id.desc()).limit(limit).offset(offset))
    return await _rows_out(db, (await db.execute(q)).all())


@router.get("/page", response_model=SalesPage)
async def page_sales(
    from_date: date | None = None,
    to_date: date | None = None,
    cashier_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    status: SaleStatus | None = None,
    kind: Literal["invoices", "quotations"] | None = None,
    product_search: str | None = Query(None, max_length=200),
    search: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read),
):
    """One page of the sales screen with the number of documents the filter matches: every
    filter (the tab, dates, search) is applied on the server before paging (SAL-11)."""
    where = await _filters(db, current_user, from_date=from_date, to_date=to_date, cashier_id=cashier_id,
                           warehouse_id=warehouse_id, status=status, kind=kind, product_search=product_search,
                           search=search)
    from app.activities.general.modules.contacts.models.party import Customer

    total = (await db.execute(select(func.count()).select_from(Sale)
                              .outerjoin(Customer, Sale.customer_id == Customer.id).where(*where))).scalar_one()
    q = (_listing(where).options(selectinload(Sale.items))
         .order_by(Sale.created_at.desc(), Sale.id.desc()).limit(page_size).offset((page - 1) * page_size))
    return {"items": await _rows_out(db, (await db.execute(q)).all()), "total": total, "page": page,
            "page_size": page_size}


@router.get("/summary", response_model=SalesSummary)
async def sales_summary(
    from_date: date | None = None,
    to_date: date | None = None,
    cashier_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    search: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read),
):
    """The figures of the sales screen's cards, counted as the reports count them (ADR-014 D4,
    D6): a document's value is its net_total less its VAT; sales are the confirmed invoices,
    returns the return documents made in the period, taken off. `outstanding` is what is still
    owed on the credit invoices listed (after their returns and payments)."""
    from app.activities.general.modules.contacts.models.party import Customer

    where = await _filters(db, current_user, from_date=from_date, to_date=to_date, cashier_id=cashier_id,
                           warehouse_id=warehouse_id, search=search)
    value = func.coalesce(Sale.net_total, 0) - func.coalesce(Sale.tax_amount, 0)
    confirmed = Sale.status == SaleStatus.confirmed
    is_return = and_(Sale.status == SaleStatus.returned, Sale.return_of.isnot(None))
    owed = func.greatest(func.coalesce(Sale.net_total, 0) - func.coalesce(Sale.returns_total, 0)
                         - func.coalesce(Sale.paid_amount, 0), 0)
    row = (await db.execute(
        select(
            func.count().filter(confirmed).label("invoices"),
            func.count().filter(is_return).label("returns"),
            func.count().filter(Sale.status == SaleStatus.cancelled).label("cancelled"),
            func.count().filter(Sale.status == SaleStatus.quotation).label("quotations"),
            func.count().filter(Sale.status == SaleStatus.draft).label("drafts"),
            func.coalesce(func.sum(value).filter(confirmed), 0).label("sales"),
            func.coalesce(func.sum(value).filter(is_return), 0).label("returned"),
            func.coalesce(func.sum(func.coalesce(Sale.tax_amount, 0)).filter(confirmed), 0).label("tax"),
            func.coalesce(func.sum(func.coalesce(Sale.tax_amount, 0)).filter(is_return), 0).label("tax_returned"),
            func.coalesce(func.sum(owed).filter(and_(confirmed, Sale.is_credit.is_(True))), 0).label("owed"),
        ).select_from(Sale).outerjoin(Customer, Sale.customer_id == Customer.id).where(*where)
    )).one()
    cent = Decimal("0.01")
    return {
        "net_sales": (Decimal(row.sales) - Decimal(row.returned)).quantize(cent),
        "gross_sales": Decimal(row.sales).quantize(cent),
        "returns_total": Decimal(row.returned).quantize(cent),
        "tax_total": (Decimal(row.tax) - Decimal(row.tax_returned)).quantize(cent),
        "outstanding": Decimal(row.owed).quantize(cent),
        "invoice_count": row.invoices, "returns_count": row.returns, "cancelled_count": row.cancelled,
        "quotation_count": row.quotations, "draft_count": row.drafts,
    }


@router.post("/quotations", response_model=SaleOut)
async def create_quotation(data: SaleCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("quotations", "sales"))):
    """إنشاء عرض سعر — لا يُخصم من المخزون."""
    await verify_warehouse_access(db, current_user, data.warehouse_id)
    return await sale_service.create_quotation(db, data, current_user.id, actor=current_user)


@router.post("/{sale_id}/confirm-quotation", response_model=SaleOut)
async def confirm_quotation(sale_id: uuid.UUID, data: ConfirmQuotationRequest | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("quotations", "sales"))):
    """A quotation becomes a confirmed sale; its money goes into the user's own open shift's
    drawer, a safe, a wallet, or the customer's account."""
    await _sale_in_reach(db, sale_id, current_user)
    return await sale_service.confirm_quotation(
        db, sale_id, current_user.id,
        destination=data.destination if data else "drawer",
        safe_id=data.safe_id if data else None,
        wallet_id=data.wallet_id if data else None,
        actor=current_user,
    )


@router.get("/{sale_id}/print")
async def print_sale(sale_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(_read)):
    """بيانات الفاتورة/عرض السعر للطباعة — تشمل بيانات المتجر والعميل والمنتجات."""
    from sqlalchemy import select as sa_select

    from app.activities.general.modules.contacts.models.party import Customer
    from app.activities.general.modules.inventory.models.product import Product
    from app.platform.settings.models import StoreSetting

    await _sale_in_reach(db, sale_id, current_user)
    result = await db.execute(sa_select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id))
    sale = result.scalar_one()

    # Enrich items with product names — single bulk query (avoids N+1)
    product_ids = list({item.product_id for item in sale.items})
    products_map: dict = {}
    if product_ids:
        prod_rows = await db.execute(sa_select(Product).where(Product.id.in_(product_ids)))
        products_map = {p.id: p for p in prod_rows.scalars().all()}

    items_out = []
    for item in sale.items:
        prod = products_map.get(item.product_id)
        items_out.append({
            "product_name": prod.name if prod else str(item.product_id),
            "unit": prod.unit if prod else "",
            "qty": float(item.qty),
            "unit_price": float(item.unit_price),
            "discount": float(item.discount),
            "total": float(item.qty) * float(item.unit_price) - float(item.discount),
            "tax_code": item.tax_code, "tax_rate": float(item.tax_rate or 0), "tax_amount": float(item.tax_amount or 0),
        })

    customer = None
    if sale.customer_id:
        customer = (await db.execute(sa_select(Customer).where(Customer.id == sale.customer_id))).scalar_one_or_none()

    settings_rows = (await db.execute(sa_select(StoreSetting))).scalars().all()
    settings = {r.key: r.value for r in settings_rows}

    subtotal = sum(i["total"] for i in items_out)
    # The stored totals (ADR-014 D6): VAT is never worked out again here.
    total = float(sale.net_total or 0)
    has_vat = any(i.tax_code is not None for i in sale.items)

    return {
        "store": {"name": settings.get("store_name", ""), "address": settings.get("store_address", ""), "phone": settings.get("store_phone", ""), "logo_url": settings.get("logo_url", "")},
        "document_type": "عرض سعر" if sale.status == "quotation" else "فاتورة مبيعات",
        "invoice_number": sale.invoice_number,
        "date": sale.created_at.isoformat(),
        "sale_mode": sale.sale_mode,
        "status": sale.status,
        "customer": {"name": customer.name if customer else "عميل عادي", "phone": customer.phone if customer else ""},
        "items": items_out,
        "subtotal": subtotal,
        "discount": float(sale.discount_amount),
        "total": total,
        "vat": has_vat,
        "tax_amount": float(sale.tax_amount or 0),
        "total_before_vat": round(total - float(sale.tax_amount or 0), 2),
        "tax_number": settings.get("tax_number", "") if has_vat else "",
        "notes": sale.notes or "",
        "created_by_name": (await db.execute(text("SELECT full_name FROM users WHERE id=:id"), {"id": sale.created_by})).scalar() if sale.created_by else "",
    }
@router.get("/{sale_id}")
async def get_sale(sale_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(_read)):
    from sqlalchemy import text as sqlt

    if current_user is not None:  # (tests call the function directly)
        await _sale_in_reach(db, sale_id, current_user)

    from app.activities.general.modules.contacts.models.customer_payment import CustomerPayment
    row = await db.execute(sqlt("""
        SELECT s.*, c.name as customer_name,
                COALESCE(json_agg(json_build_object(
                 'id', si.id, 'product_id', si.product_id, 'product_name', p.name,
                 'qty', si.qty, 'unit_price', si.unit_price, 'unit_cost', si.unit_cost,
                 'discount', si.discount, 'tax_code', si.tax_code, 'tax_rate', si.tax_rate,
                 'tax_amount', si.tax_amount, 'net_amount', si.net_amount
                )) FILTER (WHERE si.id IS NOT NULL), '[]'::json) as items
        FROM sales s
        LEFT JOIN customers c ON c.id = s.customer_id
        LEFT JOIN sale_items si ON si.sale_id = s.id
        LEFT JOIN products p ON p.id = si.product_id
        WHERE s.id = :id
        GROUP BY s.id, c.name
    """), {"id": sale_id})
    sale = row.fetchone()
    if not sale:
        raise NotFoundError("الفاتورة غير موجودة")
    result = dict(sale._mapping)
    # Get payments linked to this sale
    payments = (await db.execute(
        select(CustomerPayment).where(CustomerPayment.sale_id == sale_id).order_by(CustomerPayment.created_at.desc())
    )).scalars().all()
    result["payment_history"] = [{
        "id": str(p.id),
        "amount": float(p.amount),
        "note": p.note,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    } for p in payments]
    # Returns are their own documents (ADR-014 D4): the sale lists them and how much of each
    # product came back; a return names the sale it returns.
    returns = (await db.execute(sqlt(
        "SELECT id, invoice_number, net_total, created_at FROM sales WHERE return_of = :id AND status = 'returned' "
        "ORDER BY created_at"
    ), {"id": sale_id})).fetchall()
    result["returns"] = [{"id": str(r.id), "invoice_number": r.invoice_number, "net_total": float(r.net_total or 0),
                          "created_at": r.created_at.isoformat() if r.created_at else None} for r in returns]
    returned_qty = dict((await db.execute(sqlt(
        "SELECT si.product_id, SUM(si.qty) FROM sale_items si JOIN sales r ON r.id = si.sale_id "
        "WHERE r.return_of = :id AND r.status = 'returned' GROUP BY si.product_id"
    ), {"id": sale_id})).fetchall())
    left = {str(k): float(v) for k, v in returned_qty.items()}
    for item in result["items"]:
        pid = str(item["product_id"])
        taken = min(float(item["qty"]), left.get(pid, 0.0))
        left[pid] = left.get(pid, 0.0) - taken
        item["returned_qty"] = taken
    result["return_of_number"] = (await db.execute(sqlt("SELECT invoice_number FROM sales WHERE id = :id"),
                                                   {"id": result["return_of"]})).scalar() if result.get("return_of") else None
    # returns_total is kept on the sale by every return.
    net_total = float(result.get("net_total", 0))
    paid = float(result.get("paid_amount", 0) or 0)
    returns_total = float(result.get("returns_total", 0) or 0)
    result["returns_total"] = returns_total
    result["remaining"] = round(max(0.0, net_total - returns_total - paid), 2)
    return result


@router.put("/{sale_id}")
async def update_sale(sale_id: uuid.UUID, data: UpdateSale, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(require_perm("sales", "pos", "quotations"))):
    """Edit a quotation or a draft; confirmed documents are cancelled or returned, never edited."""
    _may_change(current_user, await _sale_in_reach(db, sale_id, current_user))
    await sale_service.update_quotation(db, sale_id, data, current_user.id, actor=current_user)
    return {"id": str(sale_id)}


@router.put("/{sale_id}/cancel")
async def cancel_sale(sale_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(require_perm("sales:cancel"))):
    """Cancel a confirmed sale (managers: `sales:cancel`, SAL-7)."""
    await _sale_in_reach(db, sale_id, current_user)
    sale = await sale_service.cancel_sale(db, sale_id, current_user.id, actor=current_user)
    return {"detail": "تم إلغاء الفاتورة", "invoice_number": sale.invoice_number}


@router.post("/{sale_id}/return")
async def return_sale(sale_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(require_perm("sales:return"))):
    """Full return of a confirmed sale; cash comes out of the user's own open shift (SAL-7)."""
    await _sale_in_reach(db, sale_id, current_user)
    return await sale_service.return_sale(db, sale_id, current_user.id, actor=current_user)


@router.post("/{sale_id}/partial-return")
async def partial_return(sale_id: uuid.UUID, data: PartialReturnRequest, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_perm("sales:return"))):
    """مرتجع جزئي — body: {items:[{product_id,qty}], shift_id?}"""
    await _sale_in_reach(db, sale_id, current_user)
    return await sale_service.partial_return_sale(db, sale_id, data.model_dump(), current_user.id, actor=current_user)


@router.put("/{sale_id}/items/{item_id}")
async def update_sale_item_qty(
    sale_id: uuid.UUID,
    item_id: uuid.UUID,
    data: SaleItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_is_manager)
):
    """Refused (409): a confirmed sale is corrected with a return, not edited (ADR-014 D4)."""
    return await sale_service.update_sale_item_qty(db, sale_id, item_id, data, current_user.id, current_user.full_name)


@router.delete("/{sale_id}/items/{item_id}")
async def delete_sale_item(
    sale_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_is_manager)
):
    """Refused (409): removing a line from a confirmed sale is a partial return (ADR-014 D4)."""
    return await sale_service.delete_sale_item(db, sale_id, item_id, current_user.id)
