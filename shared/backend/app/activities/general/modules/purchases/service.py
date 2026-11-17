"""Purchase service — business logic for purchase orders, receiving, supplier prices."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError
from app.core.pagination import Page
from app.framework.events import notify
from app.activities.general.modules.inventory.models.product import Product, Subcategory
from app.activities.general.modules.purchases.models.purchase import POStatus, PurchaseOrder, PurchaseOrderItem
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.purchases.models.supplier_price import SupplierPrice
from app.platform.auth.models.user import User
from app.activities.general.modules.inventory.schemas.stock import StockMovementCreate
from app.activities.general.modules.purchases.schemas.supplier_price import (
    SupplierPriceOut,
)
from app.activities.general.modules.inventory.services.stock import record_movement

# ── Purchase Suggestions ────────────────────────────────────────────────────

async def get_purchase_suggestions(db: AsyncSession) -> list[dict[str, Any]]:
    """Products where total stock across all warehouses <= reorder_point."""
    rows = await db.execute(text("""
        SELECT
            p.id, p.name, p.barcode as sku, p.cost_price, p.reorder_point, p.reorder_qty,
            COALESCE(SUM(CASE WHEN sm.movement_type IN ('purchase','transfer_in','adjustment_in','return_in','opening_stock')
                              THEN sm.qty ELSE 0 END)
                     - SUM(CASE WHEN sm.movement_type IN ('sale','transfer_out','adjustment_out','damage','return_out')
                              THEN sm.qty ELSE 0 END), 0) AS total_stock,
            p.unit
        FROM products p
        LEFT JOIN stock_movements sm ON sm.product_id = p.id
        WHERE p.is_active = true AND p.reorder_point > 0
        GROUP BY p.id
        HAVING COALESCE(SUM(CASE WHEN sm.movement_type IN ('purchase','transfer_in','adjustment_in','return_in','opening_stock')
                                  THEN sm.qty ELSE 0 END)
                       - SUM(CASE WHEN sm.movement_type IN ('sale','transfer_out','adjustment_out','damage','return_out')
                                  THEN sm.qty ELSE 0 END), 0) <= p.reorder_point
        ORDER BY total_stock ASC
    """))
    return [dict(r._mapping) for r in rows.fetchall()]


# ── Purchase Orders CRUD ────────────────────────────────────────────────────

# An order's total from its lines: what was received once it is received, what was ordered before.
_TOTAL_SQL = """ROUND(COALESCE((SELECT SUM(CASE WHEN po.status IN ('received', 'partial') THEN i.qty_received
                                                 ELSE i.qty_ordered END * i.unit_cost)
                               FROM purchase_order_items i WHERE i.po_id = po.id), 0), 2)"""


FINANCE_NEEDED = "دفع مبلغ للمورد أو استلام مبلغ منه في خزنة أو محفظة يتطلب صلاحية المالية"


async def order_warehouse(db: AsyncSession, po_id: uuid.UUID) -> tuple[uuid.UUID, Decimal]:
    """An order's warehouse and the amount it says is paid on receipt (for the routes' checks)."""
    row = (await db.execute(text("SELECT warehouse_id, amount_paid FROM purchase_orders WHERE id = :id"),
                            {"id": po_id})).first()
    if not row:
        raise NotFoundError("أمر الشراء غير موجود")
    return row.warehouse_id, Decimal(str(row.amount_paid or 0))


async def _check_refs(db: AsyncSession, *, warehouse_id=None, supplier_id=None, product_ids=()) -> None:
    """The order's warehouse (active), supplier and products exist in this workspace: unknown ids are a
    404, not a foreign-key error."""
    if warehouse_id is not None and not await db.scalar(
            text("SELECT 1 FROM warehouses WHERE id = :id AND is_active"), {"id": warehouse_id}):
        raise NotFoundError("المخزن غير موجود أو موقوف")
    if supplier_id is not None and not await db.scalar(text("SELECT 1 FROM suppliers WHERE id = :id"), {"id": supplier_id}):
        raise NotFoundError("المورد غير موجود")
    ids = list({*product_ids})
    if ids:
        found = (await db.execute(text("SELECT id FROM products WHERE id = ANY(:ids)"), {"ids": ids})).scalars().all()
        if len(set(found)) != len(ids):
            raise NotFoundError("صنف غير موجود")


async def list_purchases(db: AsyncSession, page: int = 1, page_size: int = 50) -> Page:
    base_sql = """
        FROM purchase_orders po
        LEFT JOIN suppliers s ON s.id = po.supplier_id
        LEFT JOIN warehouses w ON w.id = po.warehouse_id
        LEFT JOIN users u ON u.id = po.created_by
    """
    total = (await db.execute(text("SELECT COUNT(*) " + base_sql))).scalar()
    rows = await db.execute(text("""
        SELECT po.*, s.name as supplier_name, w.name as warehouse_name,
               u.full_name as created_by_name, """ + _TOTAL_SQL + """ AS total
    """ + base_sql + " ORDER BY po.created_at DESC OFFSET :offset LIMIT :limit"),
        {"offset": (page - 1) * page_size, "limit": page_size},
    )
    items = [dict(r._mapping) for r in rows.fetchall()]
    return Page(items=items, total=total, page=page, size=page_size, pages=max(1, (total + page_size - 1) // page_size))


async def get_purchase(db: AsyncSession, po_id: uuid.UUID) -> dict[str, Any]:
    po_row = await db.execute(text("""
        SELECT po.*, s.name as supplier_name, w.name as warehouse_name, """ + _TOTAL_SQL + """ AS total
        FROM purchase_orders po
        LEFT JOIN suppliers s ON s.id = po.supplier_id
        LEFT JOIN warehouses w ON w.id = po.warehouse_id
        WHERE po.id = :id
    """), {"id": po_id})
    po = po_row.fetchone()
    if not po:
        raise NotFoundError()
    items_row = await db.execute(text("""
        SELECT poi.*, p.name as product_name, p.barcode as sku, p.cost_price as current_cost
        FROM purchase_order_items poi
        JOIN products p ON p.id = poi.product_id
        WHERE poi.po_id = :po_id
    """), {"po_id": po_id})
    return {**dict(po._mapping), "items": [dict(r._mapping) for r in items_row.fetchall()]}


async def create_purchase(
    db: AsyncSession,
    data: Any,
    current_user: User,
) -> dict[str, Any]:
    from sqlalchemy import text as _text
    await _check_refs(db, warehouse_id=data.warehouse_id, supplier_id=data.supplier_id,
                      product_ids=[i.product_id for i in data.items])
    seq = (await db.execute(_text("SELECT nextval('purchase_seq')"))).scalar()
    po_number = f"PO-{seq:06d}"
    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=data.supplier_id,
        warehouse_id=data.warehouse_id,
        created_by=current_user.id,
        notes=data.notes,
    )
    db.add(po)
    await db.flush()
    if data.safe_id and data.wallet_id:
        from app.activities.general.modules.finance.services.payments import ONE_SOURCE

        raise HTTPException(400, ONE_SOURCE)
    if data.amount_paid or data.received_by_name or data.safe_id or data.wallet_id:
        await db.execute(_text(
            "UPDATE purchase_orders SET amount_paid=:ap, received_by_name=:rbn, safe_id=:sid, wallet_id=:wid WHERE id=:id"
        ), {"ap": data.amount_paid or 0, "rbn": data.received_by_name or "", "sid": data.safe_id,
            "wid": data.wallet_id, "id": po.id})
    for item in data.items:
        db.add(PurchaseOrderItem(
            po_id=po.id,
            product_id=item.product_id,
            qty_ordered=item.qty,
            unit_cost=item.unit_cost,
            notes=item.notes,
        ))
    await db.commit()
    await db.refresh(po)
    return {"id": str(po.id), "po_number": po.po_number, "status": po.status}


async def update_purchase(
    db: AsyncSession,
    po_id: uuid.UUID,
    data: Any,
    current_user: User,
) -> dict[str, bool]:
    """Update draft PO items/supplier before receiving."""
    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))
    po = result.scalar_one_or_none()
    if not po:
        raise NotFoundError()
    if po.status != POStatus.draft:
        raise BusinessError("لا يُعدَّل إلا أمر شراء في حالة المسودة")
    await _check_refs(db, supplier_id=data.supplier_id,
                      product_ids=[i.product_id for i in data.items or []])

    if data.supplier_id is not None:
        po.supplier_id = data.supplier_id
    if data.notes is not None:
        po.notes = data.notes

    if data.items is not None:
        await db.execute(text("DELETE FROM purchase_order_items WHERE po_id=:id"), {"id": po_id})
        for item in data.items:
            db.add(PurchaseOrderItem(
                po_id=po.id,
                product_id=item.product_id,
                qty_ordered=item.qty,
                unit_cost=item.unit_cost,
                notes=item.notes,
            ))
    await db.commit()
    return {"ok": True}


async def receive_purchase(
    db: AsyncSession,
    po_id: uuid.UUID,
    data: Any,
    current_user: User,
) -> dict[str, str]:
    """Receive PO. Optionally pass overridden items with actual received qty/cost."""
    result = await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id).with_for_update())
    po = result.scalar_one_or_none()
    if not po:
        raise NotFoundError()
    if po.status == POStatus.received:
        raise BusinessError("أمر الشراء مستلم بالفعل")
    if po.status == POStatus.cancelled:
        raise BusinessError("أمر الشراء ملغي")

    items = (await db.execute(select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po_id))).scalars().all()

    overrides = {str(i.product_id): {k: v for k, v in (('qty_received', i.qty_received), ('unit_cost', i.unit_cost),
                                                       ('batch_number', i.batch_number), ('expiry_date', i.expiry_date))
                                     if v is not None} for i in data.items}

    for item in items:
        override = overrides.get(str(item.product_id), {})
        qty = Decimal(str(override.get("qty_received", item.qty_ordered)))
        cost = Decimal(str(override.get("unit_cost", item.unit_cost)))

        # Record stock movement
        mv = StockMovementCreate(
            product_id=item.product_id,
            warehouse_id=po.warehouse_id,
            movement_type=MovementType.purchase,
            qty=qty,
            unit_cost=cost,
            batch_number=override.get("batch_number"),
            expiry_date=override.get("expiry_date"),
        )
        await record_movement(db, mv, current_user.id, ref_id=po.id, ref_type="purchase", purchase_id=po.id)
        item.qty_received = qty
        item.unit_cost = cost

        # Update product cost_price + record history
        old_cost_row = await db.execute(text("SELECT cost_price FROM products WHERE id=:id"), {"id": item.product_id})
        old_cost = old_cost_row.scalar()
        await db.execute(text("UPDATE products SET cost_price=:cost WHERE id=:id"), {"cost": cost, "id": item.product_id})
        await db.execute(text("""
            INSERT INTO purchase_price_history (product_id, po_id, supplier_id, old_cost, new_cost)
            VALUES (:pid, :po_id, :sid, :old, :new)
        """), {"pid": item.product_id, "po_id": po_id, "sid": po.supplier_id, "old": old_cost, "new": cost})

    po.status = POStatus.received
    po.received_at = datetime.now(UTC)

    total_cost = sum(
        (Decimal(str(overrides.get(str(item.product_id), {}).get("unit_cost", item.unit_cost))) *
         Decimal(str(overrides.get(str(item.product_id), {}).get("qty_received", item.qty_ordered))))
        for item in items
    ) or Decimal("0")
    total_cost = total_cost.quantize(Decimal("0.01"))

    # What is paid now, and where it comes from (ADR-014 D4): the receipt may override what the
    # order said. The money leaves the safe or wallet; neither may go below zero.
    if data.amount_paid is not None:
        po.amount_paid = data.amount_paid
    if data.safe_id or data.wallet_id:
        po.safe_id, po.wallet_id = data.safe_id, data.wallet_id
    amount_paid = Decimal(str(po.amount_paid or 0))
    if amount_paid > total_cost:
        raise HTTPException(400, f"المبلغ المدفوع ({amount_paid} ج.م) أكبر من إجمالي الفاتورة ({total_cost} ج.م)")
    if amount_paid > 0:
        from app.activities.general.modules.finance.services import payments

        payments.check_source(po.safe_id, po.wallet_id, "حدد الخزنة أو المحفظة التي دُفع منها المبلغ المدفوع عند الاستلام")
        await payments.money_out(db, amount_paid, safe_id=po.safe_id, wallet_id=po.wallet_id, ref_type="purchase",
                                 ref_id=po.id, note=f"دفعة مشتريات {po.po_number}", user_id=current_user.id)

    if po.supplier_id:
        await db.execute(text("SELECT 1 FROM suppliers WHERE id = :sid FOR UPDATE"), {"sid": po.supplier_id})
        # The full invoice as a debit (we owe them), the payment as a credit.
        await db.execute(text("""
            INSERT INTO supplier_transactions (id, supplier_id, amount, type, reference_doc, notes, purchase_id, created_by)
            VALUES (gen_random_uuid(), :sid, :amt, 'debit', :ref, 'فاتورة مشتريات', :po, :uid)
        """), {"sid": po.supplier_id, "amt": total_cost, "ref": po.po_number, "po": po.id, "uid": current_user.id})
        if amount_paid > 0:
            await db.execute(text("""
                INSERT INTO supplier_transactions
                    (id, supplier_id, amount, type, reference_doc, notes, purchase_id, created_by, method, safe_id, wallet_id)
                VALUES (gen_random_uuid(), :sid, :amt, 'credit', :ref, 'دفعة عند الاستلام', :po, :uid, :method, :safe, :wallet)
            """), {"sid": po.supplier_id, "amt": amount_paid, "ref": po.po_number, "po": po.id, "uid": current_user.id,
                   "method": "wallet" if po.wallet_id else "cash", "safe": po.safe_id, "wallet": po.wallet_id})
        await db.execute(text(
            "UPDATE suppliers SET balance = balance + :remaining WHERE id = :sid"
        ), {"remaining": total_cost - amount_paid, "sid": po.supplier_id})

    # Archive the purchase invoice
    from app.platform.archive.models import ArchivedDocument, DocType
    supplier_name = (await db.execute(text("SELECT name FROM suppliers WHERE id=:id"), {"id": po.supplier_id})).scalar() if po.supplier_id else None
    total_received = float(total_cost)
    db.add(ArchivedDocument(
        doc_number=po.po_number,
        doc_type=DocType.purchase_invoice,
        amount=total_received,
        ref_id=po.id,
        created_by=current_user.id,
        metadata_={
            "supplier": supplier_name or "",
            "warehouse_id": str(po.warehouse_id),
            "items_count": len(items),
            "received_by": getattr(po, "received_by_name", "") or "",
            "amount_paid": float(po.amount_paid or 0),
            "remaining": round(total_received - float(po.amount_paid or 0), 2),
        }
    ))

    # The ledger posts the receipt (and what was paid with it) in this transaction (ADR-014 D3).
    await notify("purchase.received", db, user_id=current_user.id, purchase={
        "id": po.id, "tenant_id": po.tenant_id, "po_number": po.po_number, "supplier_id": po.supplier_id,
        "warehouse_id": po.warehouse_id, "total": total_cost, "amount_paid": amount_paid,
        "safe_id": po.safe_id if amount_paid > 0 else None, "wallet_id": po.wallet_id if amount_paid > 0 else None})
    await db.commit()
    return {"detail": "Received", "po_number": po.po_number}


async def record_supplier_transaction(db: AsyncSession, supplier_id: uuid.UUID, amount: Decimal, tx_type: str, user, *,
                                     reference_doc: str | None = None, notes: str | None = None,
                                     method: str | None = None, safe_id: uuid.UUID | None = None,
                                     wallet_id: uuid.UUID | None = None) -> dict[str, Any]:
    """A movement on a supplier's account. A debit is an amount we owe (an invoice entered by hand,
    an opening balance) and moves no money. A credit is a payment to the supplier: it must say which
    safe or wallet paid it, and the money leaves that safe or wallet (ADR-014 D4). Callers commit."""
    from app.activities.general.modules.finance.services import payments

    if tx_type not in ("debit", "credit"):
        raise HTTPException(400, "نوع الحركة يجب أن يكون debit أو credit")
    amount = Decimal(str(amount))
    if amount <= 0:
        raise HTTPException(400, "المبلغ يجب أن يكون أكبر من 0")
    supplier = (await db.execute(text("SELECT id, name FROM suppliers WHERE id = :id FOR UPDATE"), {"id": supplier_id})).first()
    if not supplier:
        raise NotFoundError()
    if tx_type == "credit":
        payments.check_source(safe_id, wallet_id, "حدد الخزنة أو المحفظة التي دُفع منها المبلغ للمورد")
        method = payments.method_of(safe_id, wallet_id, method)
    else:
        method, safe_id, wallet_id = None, None, None
    row = (await db.execute(text("""
        INSERT INTO supplier_transactions (id, supplier_id, amount, type, reference_doc, notes, method, safe_id, wallet_id, created_by)
        VALUES (gen_random_uuid(), :sid, :amount, :type, :ref, :notes, :method, :safe, :wallet, :uid)
        RETURNING *
    """), {"sid": supplier_id, "amount": amount, "type": tx_type, "ref": reference_doc, "notes": notes,
           "method": method, "safe": safe_id, "wallet": wallet_id, "uid": user.id})).mappings().one()
    if tx_type == "credit":
        await payments.money_out(db, amount, safe_id=safe_id, wallet_id=wallet_id, ref_type="supplier_payment",
                                 ref_id=row["id"], note=f"دفعة للمورد {supplier.name}" + (f" — {notes}" if notes else ""),
                                 user_id=user.id)
    delta = amount if tx_type == "debit" else -amount
    await db.execute(text("UPDATE suppliers SET balance = balance + :delta WHERE id = :id"), {"delta": delta, "id": supplier_id})
    # A payment or a manual charge on the supplier's account (ADR-014 D3): the ledger posts it here.
    await notify("supplier.payment" if tx_type == "credit" else "supplier.charge", db, transaction=dict(row),
                 user_id=user.id)
    return dict(row)


async def get_price_history(db: AsyncSession, product_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = await db.execute(text("""
        SELECT pph.*, s.name as supplier_name, po.po_number
        FROM purchase_price_history pph
        LEFT JOIN suppliers s ON s.id = pph.supplier_id
        LEFT JOIN purchase_orders po ON po.id = pph.po_id
        WHERE pph.product_id = :pid
        ORDER BY pph.created_at DESC LIMIT 50
    """), {"pid": product_id})
    return [dict(r._mapping) for r in rows.fetchall()]


async def upload_invoice_image(
    db: AsyncSession,
    po_id: uuid.UUID,
    file_content: bytes,
    filename: str,
    content_type: str,
) -> str:

    ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"}
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024

    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(400, "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, GIF, WebP, PDF")
    if len(file_content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "حجم الملف يتجاوز 10 ميجابايت")
    if not await db.scalar(text("SELECT 1 FROM purchase_orders WHERE id=:id"), {"id": po_id}):
        raise HTTPException(404, "أمر الشراء غير موجود")
    from app.framework import files

    url = await files.store(db, file_content, kind="po_invoice", owner_id=str(po_id),
                            filename=filename or "invoice.jpg", content_type=content_type)
    await db.execute(text("UPDATE purchase_orders SET invoice_image_url=:url WHERE id=:id"), {"url": url, "id": po_id})
    await db.commit()
    return url


async def quick_add_product(
    db: AsyncSession,
    data: Any,
    current_user: User,
) -> dict[str, Any]:
    """Create a new product inline during purchase entry."""
    # If subcategory_id is provided, use it
    if data.subcategory_id:
        sub = await db.scalar(select(Subcategory).where(Subcategory.id == data.subcategory_id))
        if not sub:
            raise BusinessError("التصنيف الفرعي غير موجود")
    else:
        # Try to find a default subcategory named "عام" or "متنوع"
        sub = await db.scalar(
            select(Subcategory).where(
                or_(
                    Subcategory.name.ilike("عام"),
                    Subcategory.name.ilike("متنوع"),
                    Subcategory.name.ilike("general"),
                    Subcategory.name.ilike("miscellaneous")
                )
            ).limit(1)
        )
        # If no default found, use first subcategory
        if not sub:
            sub = await db.scalar(select(Subcategory).limit(1))
            if not sub:
                raise BusinessError("لا توجد تصنيفات — أضف تصنيف أولاً")

    p = Product(
        name=data.name,
        unit=data.unit or "عدد",
        cost_price=float(data.cost_price or 0),
        retail_price=float(data.retail_price or 0),
        wholesale_price=float(data.wholesale_price or 0),
        company=data.company or "",
        subcategory_id=sub.id,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {
        "id": str(p.id),
        "name": p.name,
        "unit": p.unit,
        "cost_price": float(p.cost_price),
        "retail_price": float(p.retail_price),
        "wholesale_price": float(p.wholesale_price),
        "barcode": p.barcode,
    }


# ── Supplier Prices ────────────────────────────────────────────────────────

async def get_product_supplier_prices(db: AsyncSession, product_id: uuid.UUID) -> dict[str, Any]:
    """Get all supplier prices for a product with comparison."""
    prod_uuid = uuid.UUID(str(product_id))
    prod = await db.scalar(select(Product).where(Product.id == prod_uuid))
    if not prod:
        raise NotFoundError()

    rows = await db.execute(
        text(
            """
            SELECT sp.id, sp.supplier_id, sp.product_id, sp.price, sp.currency, sp.min_qty,
                   sp.last_purchase_date, sp.notes, sp.is_active, sp.created_at, sp.updated_at,
                   s.name AS supplier_name
            FROM supplier_prices sp
            JOIN suppliers s ON s.id = sp.supplier_id
            WHERE sp.product_id = :pid AND sp.is_active = true
            ORDER BY sp.price ASC
            """
        ),
        {"pid": prod_uuid},
    )

    suppliers = [dict(r._mapping) for r in rows.fetchall()]
    return {
        "product_id": prod_uuid,
        "product_name": prod.name,
        "suppliers": suppliers,
    }


async def create_supplier_price(
    db: AsyncSession,
    data: Any,
    current_user: User,
) -> SupplierPriceOut:
    """Create or update supplier price."""
    await _check_refs(db, supplier_id=data.supplier_id, product_ids=[data.product_id])
    stmt = pg_insert(SupplierPrice).values(**data.model_dump())
    stmt = stmt.on_conflict_do_update(
        constraint="uq_supplier_product",
        set_={
            "price": data.price,
            "currency": data.currency,
            "min_qty": data.min_qty,
            "notes": data.notes,
            "is_active": True,
        }
    )
    await db.execute(stmt)
    await db.commit()
    existing = await db.scalar(
        select(SupplierPrice).where(
            SupplierPrice.supplier_id == data.supplier_id,
            SupplierPrice.product_id == data.product_id
        )
    )
    return existing


async def update_supplier_price(
    db: AsyncSession,
    price_id: uuid.UUID,
    data: Any,
) -> SupplierPriceOut:
    """Update supplier price."""
    sp = await db.scalar(select(SupplierPrice).where(SupplierPrice.id == price_id))
    if not sp:
        raise NotFoundError()

    for k, v in data.model_dump(exclude_none=True).items():
        setattr(sp, k, v)

    await db.commit()
    await db.refresh(sp)
    return sp


async def delete_supplier_price(
    db: AsyncSession,
    price_id: uuid.UUID,
) -> None:
    """Soft-delete supplier price."""
    sp = await db.scalar(select(SupplierPrice).where(SupplierPrice.id == price_id))
    if not sp:
        raise NotFoundError()

    sp.is_active = False
    await db.commit()


# ── Purchase returns (ADR-014 D3, step 3) ───────────────────────────────────

async def _po_quantities(db: AsyncSession, po_id: uuid.UUID) -> dict[uuid.UUID, dict[str, Decimal]]:
    """Per product of a purchase order: what was received, its average cost on that order, and what
    has already gone back to the supplier."""
    received = (await db.execute(text("""
        SELECT product_id, SUM(qty_received) AS qty, SUM(qty_received * unit_cost) AS value
        FROM purchase_order_items WHERE po_id = :po GROUP BY product_id
    """), {"po": po_id})).all()
    returned = {r.product_id: Decimal(str(r.qty)) for r in (await db.execute(text("""
        SELECT i.product_id, SUM(i.qty) AS qty FROM purchase_return_items i
        JOIN purchase_returns r ON r.id = i.return_id WHERE r.po_id = :po GROUP BY i.product_id
    """), {"po": po_id})).all()}
    out = {}
    for r in received:
        qty = Decimal(str(r.qty or 0))
        cost = (Decimal(str(r.value or 0)) / qty).quantize(Decimal("0.01")) if qty > 0 else Decimal("0")
        out[r.product_id] = {"received": qty, "returned": returned.get(r.product_id, Decimal("0")), "unit_cost": cost}
    return out


async def list_purchase_returns(db: AsyncSession, po_id: uuid.UUID) -> dict[str, Any]:
    """The returns of a purchase order, and per product how much can still be returned."""
    if not await db.scalar(text("SELECT 1 FROM purchase_orders WHERE id = :id"), {"id": po_id}):
        raise NotFoundError()
    rets = (await db.execute(text(
        "SELECT * FROM purchase_returns WHERE po_id = :po ORDER BY created_at DESC"), {"po": po_id})).mappings().all()
    items = (await db.execute(text("""
        SELECT i.*, p.name AS product_name FROM purchase_return_items i JOIN products p ON p.id = i.product_id
        WHERE i.return_id = ANY(:ids)
    """), {"ids": [r["id"] for r in rets]})).mappings().all()
    names = {r["id"]: r["product_name"] for r in (await db.execute(text(
        "SELECT p.id, p.name AS product_name FROM products p WHERE p.id IN "
        "(SELECT product_id FROM purchase_order_items WHERE po_id = :po)"), {"po": po_id})).mappings().all()}
    quantities = await _po_quantities(db, po_id)
    return {
        "returns": [{**dict(r), "items": [dict(i) for i in items if i["return_id"] == r["id"]]} for r in rets],
        "returnable": [{"product_id": pid, "product_name": names.get(pid), "unit_cost": q["unit_cost"],
                        "received": q["received"], "returned": q["returned"],
                        "returnable": max(Decimal("0"), q["received"] - q["returned"])}
                       for pid, q in quantities.items()],
    }


async def create_purchase_return(db: AsyncSession, po_id: uuid.UUID, data: Any, current_user: User) -> dict[str, Any]:
    """Send goods of a received purchase order back to the supplier. Each line leaves the warehouse at
    the cost it came in at (movement return_out) and cannot exceed what was received and not yet
    returned. What the goods were worth lowers the supplier's balance, except the part the supplier
    pays back now into a safe or wallet (`refund_amount`). Callers commit through this function."""
    from app.activities.general.modules.finance.services import payments
    from app.activities.general.modules.inventory.services.stock import apply_movement, get_balance
    from app.activities.general.modules.purchases.models.purchase_return import PurchaseReturn, PurchaseReturnItem

    po = (await db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id).with_for_update())).scalar_one_or_none()
    if not po:
        raise NotFoundError()
    if po.status != POStatus.received:
        raise BusinessError("لا يمكن إرجاع بضاعة من أمر شراء لم يُستلم بعد")

    wanted: dict[uuid.UUID, Decimal] = {}
    for item in data.items:
        wanted[item.product_id] = wanted.get(item.product_id, Decimal("0")) + Decimal(str(item.qty))
    quantities = await _po_quantities(db, po_id)
    lines = []
    for product_id, qty in sorted(wanted.items(), key=lambda kv: str(kv[0])):
        q = quantities.get(product_id)
        if q is None:
            raise HTTPException(400, "الصنف ليس ضمن أمر الشراء هذا")
        left = q["received"] - q["returned"]
        if qty > left:
            raise HTTPException(400, f"الكمية المرتجعة ({qty}) أكبر من المتاح للإرجاع ({left}) من هذا الصنف")
        lines.append((product_id, qty, q["unit_cost"], (qty * q["unit_cost"]).quantize(Decimal("0.01"))))
    total = sum((ln[3] for ln in lines), Decimal("0"))

    refund = Decimal(str(data.refund_amount or 0))
    if refund > total:
        raise HTTPException(400, f"المبلغ المستردّ ({refund} ج.م) أكبر من قيمة المرتجع ({total} ج.م)")
    if not po.supplier_id and refund != total:
        raise HTTPException(400, "أمر شراء بلا مورد: يجب أن يُسترد كامل قيمة المرتجع نقداً في خزنة أو محفظة")
    if refund > 0:
        payments.check_source(data.safe_id, data.wallet_id, "حدد الخزنة أو المحفظة التي استُلم فيها المبلغ المستردّ")
    else:
        data.safe_id = data.wallet_id = None

    # Products first, then balances: the same lock order as a receipt (see inventory stock._movement_cost).
    await db.execute(text("SELECT id FROM products WHERE id = ANY(:ids) ORDER BY id FOR UPDATE"),
                     {"ids": [ln[0] for ln in lines]})
    for product_id, qty, _, _ in lines:
        balance = await get_balance(db, product_id, po.warehouse_id, for_update=True)
        if balance < qty:
            name = await db.scalar(text("SELECT name FROM products WHERE id = :id"), {"id": product_id})
            raise HTTPException(400, f"رصيد «{name}» في المخزن ({balance}) أقل من الكمية المرتجعة ({qty})")

    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"purchase_returns:{po.tenant_id}"})
    last = await db.scalar(text(
        "SELECT COALESCE(MAX(CAST(substring(return_number FROM 5) AS integer)), 0) FROM purchase_returns "
        "WHERE tenant_id = :t AND return_number ~ '^PRT-[0-9]+$'"), {"t": po.tenant_id})
    ret = PurchaseReturn(return_number=f"PRT-{int(last) + 1:06d}", po_id=po.id, supplier_id=po.supplier_id,
                         warehouse_id=po.warehouse_id, total=total, refund_amount=refund, safe_id=data.safe_id,
                         wallet_id=data.wallet_id, notes=data.notes, created_by=current_user.id)
    db.add(ret)
    await db.flush()
    for product_id, qty, cost, _ in lines:
        db.add(PurchaseReturnItem(return_id=ret.id, product_id=product_id, qty=qty, unit_cost=cost))
        await apply_movement(db, product_id=product_id, warehouse_id=po.warehouse_id,
                             movement_type=MovementType.return_out, qty=qty, unit_cost=cost,
                             created_by=current_user.id, ref_id=ret.id, ref_type="purchase_return",
                             purchase_id=po.id, note=f"مرتجع مشتريات {ret.return_number} — {po.po_number}")
    if refund > 0:
        await payments.money_in(db, refund, safe_id=data.safe_id, wallet_id=data.wallet_id, ref_type="purchase_return",
                                ref_id=ret.id, note=f"استرداد من مورد — مرتجع {ret.return_number}", user_id=current_user.id)
    owed_less = total - refund
    if po.supplier_id and owed_less > 0:
        await db.execute(text("SELECT 1 FROM suppliers WHERE id = :sid FOR UPDATE"), {"sid": po.supplier_id})
        await db.execute(text("""
            INSERT INTO supplier_transactions (id, supplier_id, amount, type, reference_doc, notes, purchase_id, created_by)
            VALUES (gen_random_uuid(), :sid, :amt, 'credit', :ref, 'مرتجع مشتريات', :po, :uid)
        """), {"sid": po.supplier_id, "amt": owed_less, "ref": ret.return_number, "po": po.id, "uid": current_user.id})
        await db.execute(text("UPDATE suppliers SET balance = balance - :amt WHERE id = :sid"),
                         {"amt": owed_less, "sid": po.supplier_id})
    await notify("purchase.returned", db, user_id=current_user.id, purchase_return={
        "id": ret.id, "tenant_id": ret.tenant_id, "return_number": ret.return_number, "supplier_id": ret.supplier_id,
        "warehouse_id": ret.warehouse_id, "total": total, "refund_amount": refund, "safe_id": ret.safe_id,
        "wallet_id": ret.wallet_id})
    await db.commit()
    return {"id": str(ret.id), "return_number": ret.return_number, "total": total, "refund_amount": refund,
            "supplier_balance_change": -owed_less if po.supplier_id else Decimal("0")}
