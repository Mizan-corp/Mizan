"""Batches and expiry (FEFO): business logic.

receive() puts stock coming in into its batch; take() takes stock going out from the batches
that expire first. Called by the inventory pharmacy variant's after_movement hook, so it runs
for every stock movement of a workspace that tracks batches, in the movement's transaction.
"""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.pharmacy.modules.batches.models import NO_BATCH, Lot, LotMovement

SELLABLE_OUT = ("sale", "transfer_out")  # these never take expired or quarantined stock


def _kind(movement_type) -> str:
    return str(movement_type).split(".")[-1]


def lot_out(lot: Lot, qty: Decimal) -> dict:
    return {"lot_id": str(lot.id), "batch_number": lot.batch_number,
            "expiry_date": lot.expiry_date.isoformat() if lot.expiry_date else None,
            "unit_cost": float(lot.unit_cost) if lot.unit_cost is not None else None, "qty": qty}


async def receive(db: AsyncSession, movement, lot: dict | None, required: bool) -> list[dict]:
    """Stock coming in goes into its batch (created on first arrival)."""
    batch = (lot or {}).get("batch_number")
    expiry = (lot or {}).get("expiry_date")
    if isinstance(expiry, str):
        expiry = date.fromisoformat(expiry[:10]) if expiry else None
    kind = _kind(movement.movement_type)
    if not batch:
        if required and kind in ("purchase", "opening_stock", "adjustment_in"):
            raise HTTPException(422, "رقم التشغيلة وتاريخ الصلاحية مطلوبان عند استلام هذا الصنف")
        batch = NO_BATCH
    if required and batch != NO_BATCH and expiry is None and kind in ("purchase", "opening_stock", "adjustment_in"):
        raise HTTPException(422, f"تاريخ صلاحية التشغيلة {batch} مطلوب")
    row = (await db.execute(select(Lot).where(
        Lot.product_id == movement.product_id, Lot.warehouse_id == movement.warehouse_id, Lot.batch_number == batch,
    ).with_for_update())).scalar_one_or_none()
    if row is None:
        row = Lot(product_id=movement.product_id, warehouse_id=movement.warehouse_id, batch_number=batch,
                  expiry_date=expiry, qty=0, unit_cost=movement.unit_cost or (lot or {}).get("unit_cost"))
        db.add(row)
        await db.flush()
    elif expiry and row.expiry_date and expiry != row.expiry_date:
        raise HTTPException(422, f"التشغيلة {batch} مسجلة بتاريخ صلاحية {row.expiry_date.isoformat()}")
    elif expiry and not row.expiry_date:
        row.expiry_date = expiry
    row.qty = (row.qty or 0) + Decimal(str(movement.qty))
    db.add(LotMovement(lot_id=row.id, movement_id=movement.id, qty=Decimal(str(movement.qty))))
    return [lot_out(row, Decimal(str(movement.qty)))]


async def take(db: AsyncSession, movement, lot: dict | None = None) -> list[dict]:
    """Stock going out, first expiry first out. Sales and transfers skip expired and quarantined
    batches; a disposal (adjustment out) takes the named batch, or expired stock first."""
    kind = _kind(movement.movement_type)
    need = Decimal(str(movement.qty))
    today = date.today()
    q = select(Lot).where(Lot.product_id == movement.product_id, Lot.warehouse_id == movement.warehouse_id, Lot.qty > 0)
    if lot and lot.get("batch_number"):
        q = q.where(Lot.batch_number == lot["batch_number"])
    if kind in SELLABLE_OUT:
        q = q.where(Lot.status == "active").where((Lot.expiry_date.is_(None)) | (Lot.expiry_date >= today))
    lots = (await db.execute(q.order_by(Lot.expiry_date.asc().nulls_last(), Lot.received_at).with_for_update())).scalars().all()
    taken: list[dict] = []
    for row in lots:
        if need <= 0:
            break
        part = min(need, Decimal(str(row.qty)))
        row.qty = Decimal(str(row.qty)) - part
        db.add(LotMovement(lot_id=row.id, movement_id=movement.id, qty=-part))
        taken.append(lot_out(row, part))
        need -= part
    if need > 0:
        name = await db.scalar(text("SELECT name FROM products WHERE id = :p"), {"p": movement.product_id})
        if kind in SELLABLE_OUT:
            raise HTTPException(409, f"لا توجد تشغيلات صالحة (غير منتهية) كافية من «{name}»: الناقص {need.normalize()}")
        raise HTTPException(409, f"الكمية أكبر من رصيد التشغيلات المتاح من «{name}»")
    return taken


async def expiring(db: AsyncSession, within_days: int, warehouse_id=None) -> list[dict]:
    """Batches with stock that are expired or expire within `within_days`, soonest first."""
    rows = (await db.execute(text("""
        SELECT l.id, l.product_id, p.name AS product_name, l.warehouse_id, w.name AS warehouse_name, l.batch_number,
               l.expiry_date, l.qty, l.status, (l.expiry_date - CURRENT_DATE) AS days_left
        FROM batches_lots l JOIN products p ON p.id = l.product_id JOIN warehouses w ON w.id = l.warehouse_id
        WHERE l.qty > 0 AND l.expiry_date IS NOT NULL AND l.expiry_date <= CURRENT_DATE + CAST(:d AS integer)
          AND (CAST(:w AS uuid) IS NULL OR l.warehouse_id = CAST(:w AS uuid))
        ORDER BY l.expiry_date, p.name
    """), {"d": within_days, "w": str(warehouse_id) if warehouse_id else None})).mappings().all()
    return [dict(r) for r in rows]
