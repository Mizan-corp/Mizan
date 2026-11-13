"""Batches and expiry (FEFO): API routes. Routes parse the request, check permissions and call service.py."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.framework.activation import require_module
from app.activities.pharmacy.modules.batches import service
from app.activities.pharmacy.modules.batches.models import Lot

router = APIRouter(
    prefix="/modules/batches",
    tags=["Batches and expiry (FEFO)"],
    dependencies=[Depends(require_module("batches"))],
)


class LotStatus(BaseModel):
    status: Literal["active", "quarantined"]


@router.get("")
async def list_lots(product_id: uuid.UUID | None = None, warehouse_id: uuid.UUID | None = None,
                    include_empty: bool = False, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory", "pos"))):
    """A product's batches (or all), soonest expiry first: what FEFO will sell next."""
    rows = (await db.execute(text("""
        SELECT l.id, l.product_id, p.name AS product_name, l.warehouse_id, w.name AS warehouse_name, l.batch_number,
               l.expiry_date, l.qty, l.unit_cost, l.status, l.received_at, (l.expiry_date - CURRENT_DATE) AS days_left
        FROM batches_lots l JOIN products p ON p.id = l.product_id JOIN warehouses w ON w.id = l.warehouse_id
        WHERE (CAST(:p AS uuid) IS NULL OR l.product_id = CAST(:p AS uuid))
          AND (CAST(:w AS uuid) IS NULL OR l.warehouse_id = CAST(:w AS uuid))
          AND (:all OR l.qty > 0)
        ORDER BY p.name, l.expiry_date NULLS LAST, l.received_at
        LIMIT 500
    """), {"p": str(product_id) if product_id else None, "w": str(warehouse_id) if warehouse_id else None,
           "all": include_empty})).mappings().all()
    return [dict(r) for r in rows]


@router.get("/expiring")
async def expiring(days: int = Query(90, ge=0, le=730), warehouse_id: uuid.UUID | None = None,
                   db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory", "pos"))):
    """Expired batches, then those expiring within `days`."""
    return await service.expiring(db, days, warehouse_id)


@router.post("/{lot_id}/status")
async def set_status(lot_id: uuid.UUID, data: LotStatus, db: AsyncSession = Depends(get_db),
                     _=Depends(require_perm("inventory"))):
    """Quarantine a batch (it isn't sold) or release it."""
    lot = await db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "التشغيلة غير موجودة")
    lot.status = data.status
    await db.commit()
    return {"id": str(lot.id), "status": lot.status}


@router.get("/{lot_id}/trace")
async def trace(lot_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("inventory"))):
    """Where a batch went: every movement in and out (for recalls)."""
    rows = (await db.execute(text("""
        SELECT lm.qty, lm.created_at, m.movement_type::text AS movement_type, m.ref_type, m.ref_id,
               s.invoice_number, c.name AS customer_name
        FROM batches_lot_movements lm JOIN stock_movements m ON m.id = lm.movement_id
        LEFT JOIN sales s ON s.id = m.sale_id LEFT JOIN customers c ON c.id = s.customer_id
        WHERE lm.lot_id = :l ORDER BY lm.created_at
    """), {"l": lot_id})).mappings().all()
    return [dict(r) for r in rows]
