"""Stock operations: dispatch (warehouse to showroom) and stock request (a document only). Each is
archived; a dispatch moves stock. Goods from a supplier are received through a purchase order (the
purchases module: supplier, payable and the ledger's purchase.received), not here. Callers commit."""
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement, get_balance
from app.activities.general.modules.operations.schemas import DispatchRequest, OperationItem, StockRequestRequest
from app.dependencies import verify_warehouse_access
from app.platform.archive.models import ArchivedDocument, DocType
from app.platform.audit.service import log as audit_log


async def _doc_number(db: AsyncSession, prefix: str) -> str:
    # A sequence, not the clock: two documents in the same second got the same number.
    seq = (await db.execute(text("SELECT nextval('invoice_seq')"))).scalar()
    return f"{prefix}-{seq:06d}"


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
             created_by: uuid.UUID, ref_id: uuid.UUID) -> None:
    db.add(ArchivedDocument(doc_number=doc_number, doc_type=doc_type, amount=amount, metadata_=metadata,
                            ref_id=ref_id, created_by=created_by))


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
    _archive(db, DocType.dispatch_order, doc_number, total_qty,
             {"from": from_wh.name, "to": to_wh.name, "items": items_detail, "notes": data.notes, "employee": user.full_name},
             user.id, ref_id)
    await audit_log(db, "dispatch", "create", user.id, user.full_name, ref_id,
                    {"from": from_wh.name, "to": to_wh.name, "items_count": len(data.items)}, f"إذن صرف {doc_number}")
    return {"doc_number": doc_number, "doc_type": "dispatch_order", "items_count": len(data.items)}


async def request_stock(db: AsyncSession, data: StockRequestRequest, user) -> dict:
    """طلب نواقص: a supply request document; no stock moves. The requester asks for goods into a
    warehouse they work in (`to`); the source may be any warehouse."""
    from_wh, to_wh = await _warehouse(db, data.from_warehouse_id), await _warehouse(db, data.to_warehouse_id)
    await verify_warehouse_access(db, user, to_wh.id)
    products = await _products(db, data.items)
    doc_number = await _doc_number(db, "REQ")
    items_detail = [{"product_id": str(i.product_id), "name": products[i.product_id].name, "qty": float(i.qty)} for i in data.items]
    _archive(db, DocType.stock_request, doc_number, Decimal("0"),
             {"from": from_wh.name, "to": to_wh.name, "items": items_detail, "notes": data.notes, "employee": user.full_name,
              "status": "pending"}, user.id, uuid.uuid4())
    return {"doc_number": doc_number, "doc_type": "stock_request", "items_count": len(data.items)}
