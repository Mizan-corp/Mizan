"""Stock operations: dispatch (warehouse to showroom) and stock request (a document only). Each is
archived; a dispatch moves stock and can be cancelled, which moves it back. Goods from a supplier
are received through a purchase order (the purchases module: supplier, payable and the ledger's
purchase.received), not here. Callers commit.

Numbers (DSP-000001, REQ-000001) count per workspace (PLAT-6, app/platform/archive/numbering.py),
in the document's transaction: a document that fails gives its number back."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType, StockMovement
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement, get_balance
from app.activities.general.modules.operations.schemas import DispatchRequest, OperationItem, StockRequestRequest
from app.dependencies import verify_warehouse_access
from app.platform.archive.models import ArchivedDocument, DocType
from app.platform.audit.service import log as audit_log

DOC_TYPES = (DocType.dispatch_order, DocType.goods_receipt, DocType.stock_request)


async def _doc_number(db: AsyncSession, prefix: str) -> str:
    """The workspace's next DSP / REQ number, under a row lock on its counter."""
    from app.platform.archive.numbering import next_number

    return await next_number(db, prefix)


def _qty_text(q) -> str:
    return f"{Decimal(str(q)).normalize():f}"


async def _warehouse(db: AsyncSession, warehouse_id: uuid.UUID) -> Warehouse:
    wh = (await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))).scalar_one_or_none()
    if not wh:
        raise HTTPException(404, "المخزن غير موجود")
    return wh


async def _products(db: AsyncSession, items: list[OperationItem]) -> dict[uuid.UUID, Product]:
    ids = {i.product_id for i in items}
    found = {p.id: p for p in (await db.execute(select(Product).where(Product.id.in_(ids)))).scalars()}
    if missing := ids - set(found):
        raise HTTPException(404, f"صنف غير موجود ({len(missing)})")
    return found


def _archive(db: AsyncSession, doc_type: DocType, doc_number: str, amount: Decimal, metadata: dict,
             created_by: uuid.UUID, ref_id: uuid.UUID) -> ArchivedDocument:
    doc = ArchivedDocument(doc_number=doc_number, doc_type=doc_type, amount=amount, metadata_=metadata,
                           ref_id=ref_id, created_by=created_by)
    db.add(doc)
    return doc


async def dispatch(db: AsyncSession, data: DispatchRequest, user) -> dict:
    """إذن صرف: move goods from one warehouse to another (both must be warehouses the user works in)."""
    from_wh, to_wh = await _warehouse(db, data.from_warehouse_id), await _warehouse(db, data.to_warehouse_id)
    await verify_warehouse_access(db, user, from_wh.id)
    await verify_warehouse_access(db, user, to_wh.id)
    products = await _products(db, data.items)
    doc_number, ref_id = await _doc_number(db, "DSP"), uuid.uuid4()
    total_qty, items_detail = Decimal("0"), []
    for item in data.items:
        prod = products[item.product_id]
        balance = await get_balance(db, item.product_id, data.from_warehouse_id, for_update=True)
        if balance < item.qty:
            raise HTTPException(400, f"رصيد غير كافٍ للمنتج {prod.name} — المتاح {balance}")
        # Stock really moves now (it used to record the movements but not the balances).
        _, taken = await apply_movement(db, product_id=item.product_id, warehouse_id=data.from_warehouse_id,
                                        movement_type=MovementType.transfer_out, qty=item.qty, ref_id=ref_id,
                                        ref_type="dispatch", note=item.note or data.notes, created_by=user.id)
        # The same batches arrive at the other branch.
        for lot in taken or [None]:
            await apply_movement(db, product_id=item.product_id, warehouse_id=data.to_warehouse_id,
                                 movement_type=MovementType.transfer_in, qty=lot["qty"] if lot else item.qty,
                                 ref_id=ref_id, ref_type="dispatch", note=item.note or data.notes,
                                 created_by=user.id, lot=lot)
        total_qty += item.qty
        items_detail.append({"product_id": str(item.product_id), "name": prod.name, "qty": float(item.qty)})
    doc = _archive(db, DocType.dispatch_order, doc_number, total_qty,
                   {"from": from_wh.name, "to": to_wh.name, "from_id": str(from_wh.id), "to_id": str(to_wh.id),
                    "items": items_detail, "notes": data.notes, "employee": user.full_name, "status": "done"},
                   user.id, ref_id)
    await db.flush()
    await audit_log(db, "dispatch", "create", user.id, user.full_name, ref_id,
                    {"from": from_wh.name, "to": to_wh.name, "items_count": len(data.items)}, f"إذن صرف {doc_number}")
    return {"id": str(doc.id), "doc_number": doc_number, "doc_type": "dispatch_order", "items_count": len(data.items)}


async def request_stock(db: AsyncSession, data: StockRequestRequest, user) -> dict:
    """طلب نواقص: a supply request document; no stock moves. The requester asks for goods into a
    warehouse they work in (`to`); the source may be any warehouse."""
    from_wh, to_wh = await _warehouse(db, data.from_warehouse_id), await _warehouse(db, data.to_warehouse_id)
    await verify_warehouse_access(db, user, to_wh.id)
    products = await _products(db, data.items)
    doc_number = await _doc_number(db, "REQ")
    items_detail = [{"product_id": str(i.product_id), "name": products[i.product_id].name, "qty": float(i.qty)} for i in data.items]
    doc = _archive(db, DocType.stock_request, doc_number, Decimal("0"),
                   {"from": from_wh.name, "to": to_wh.name, "from_id": str(from_wh.id), "to_id": str(to_wh.id),
                    "items": items_detail, "notes": data.notes, "employee": user.full_name, "status": "pending"},
                   user.id, uuid.uuid4())
    await db.flush()
    await audit_log(db, "stock_request", "create", user.id, user.full_name, doc.ref_id,
                    {"from": from_wh.name, "to": to_wh.name, "items_count": len(data.items)}, f"طلب نواقص {doc_number}")
    return {"id": str(doc.id), "doc_number": doc_number, "doc_type": "stock_request", "items_count": len(data.items)}


async def cancel_dispatch(db: AsyncSession, doc_id: uuid.UUID, user, reason: str | None = None) -> dict:
    """Cancel a dispatch (OPS-5): what arrived at the destination goes back to the source, by the
    same path as a dispatch (transfer out and in, batches followed), recorded as `dispatch_cancel`
    movements under the dispatch's reference. Refused when the destination no longer holds what it
    received (sold or moved on). The document is kept, marked cancelled, and audited."""
    doc = (await db.execute(select(ArchivedDocument).where(ArchivedDocument.id == doc_id)
                            .with_for_update())).scalar_one_or_none()
    if doc is None or doc.doc_type != DocType.dispatch_order:
        raise HTTPException(404, "إذن الصرف غير موجود")
    meta = dict(doc.metadata_ or {})
    if meta.get("status") == "cancelled":
        raise HTTPException(400, "إذن الصرف ملغى بالفعل")
    rows = (await db.execute(
        select(StockMovement.product_id, StockMovement.warehouse_id, StockMovement.movement_type,
               func.sum(StockMovement.qty).label("qty"))
        .where(StockMovement.ref_id == doc.ref_id, StockMovement.ref_type == "dispatch")
        .group_by(StockMovement.product_id, StockMovement.warehouse_id, StockMovement.movement_type)
    )).all()
    outs = [r for r in rows if str(r.movement_type).split(".")[-1] == "transfer_out"]
    ins = [r for r in rows if str(r.movement_type).split(".")[-1] == "transfer_in"]
    if not outs or not ins:
        raise HTTPException(400, "لا توجد حركات مخزون مسجلة لهذا الإذن")
    source, destination = outs[0].warehouse_id, ins[0].warehouse_id
    await verify_warehouse_access(db, user, source)
    await verify_warehouse_access(db, user, destination)
    to_wh = await _warehouse(db, destination)
    names = dict((await db.execute(select(Product.id, Product.name)
                                   .where(Product.id.in_({r.product_id for r in ins})))).all())
    note = f"إلغاء إذن الصرف {doc.doc_number}" + (f" — {reason}" if reason else "")
    for row in sorted(ins, key=lambda r: str(r.product_id)):
        qty = Decimal(str(row.qty))
        balance = await get_balance(db, row.product_id, destination, for_update=True)
        if balance < qty:
            raise HTTPException(400, f"لا يمكن إلغاء الإذن: رصيد «{names.get(row.product_id, '')}» في {to_wh.name} "
                                     f"({_qty_text(balance)}) أقل مما وصله ({_qty_text(qty)})")
        _, taken = await apply_movement(db, product_id=row.product_id, warehouse_id=destination,
                                        movement_type=MovementType.transfer_out, qty=qty, ref_id=doc.ref_id,
                                        ref_type="dispatch_cancel", note=note, created_by=user.id)
        for lot in taken or [None]:
            await apply_movement(db, product_id=row.product_id, warehouse_id=source,
                                 movement_type=MovementType.transfer_in, qty=lot["qty"] if lot else qty,
                                 ref_id=doc.ref_id, ref_type="dispatch_cancel", note=note, created_by=user.id, lot=lot)
    meta.update(status="cancelled", cancelled_by=user.full_name, cancelled_at=datetime.now(UTC).isoformat(),
                cancel_reason=reason or "")
    doc.metadata_ = meta
    await audit_log(db, "dispatch", "cancel", user.id, user.full_name, doc.ref_id,
                    {"doc_number": doc.doc_number, "reason": reason or "", "items_count": len(ins)},
                    f"إلغاء إذن الصرف {doc.doc_number}")
    return {"id": str(doc.id), "doc_number": doc.doc_number, "status": "cancelled"}


def doc_out(d: ArchivedDocument) -> dict:
    meta = d.metadata_ or {}
    return {"id": str(d.id), "doc_number": d.doc_number, "doc_type": d.doc_type,
            "amount": float(d.amount or 0), "status": meta.get("status"), "metadata": meta,
            "created_at": d.created_at.isoformat()}


async def list_documents(db: AsyncSession, doc_type: DocType | None, page: int, page_size: int) -> dict:
    """The operation documents, newest first: {items, total, page, pages}."""
    cond = [ArchivedDocument.doc_type == doc_type] if doc_type else [ArchivedDocument.doc_type.in_(DOC_TYPES)]
    total = (await db.execute(select(func.count()).select_from(ArchivedDocument).where(*cond))).scalar_one()
    docs = (await db.execute(select(ArchivedDocument).where(*cond)
                             .order_by(ArchivedDocument.created_at.desc(), ArchivedDocument.id.desc())
                             .limit(page_size).offset((page - 1) * page_size))).scalars().all()
    return {"items": [doc_out(d) for d in docs], "total": total, "page": page,
            "pages": max(1, -(-total // page_size))}
