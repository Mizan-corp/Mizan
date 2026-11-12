"""Scanning at the till: GET /pos/scan/{code} (a barcode, or a weighing-scale label in retail)."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.modules.general.inventory.schemas.product import ProductOut
from app.modules.general.pos import service

router = APIRouter(prefix="/pos", tags=["pos"])


@router.get("/scan/{code}")
async def scan(code: str, warehouse_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
               _=Depends(require_perm("pos"))):
    """`available`: the branch's stock of the product, when a branch is given (the till warns
    when the cart goes over it)."""
    from app.modules.general.inventory.models.stock_balance import StockBalance

    found = await service.scan(db, code)
    available = None
    if warehouse_id:
        qty = await db.scalar(select(StockBalance.qty).where(StockBalance.product_id == found["product"].id,
                                                             StockBalance.warehouse_id == warehouse_id))
        available = str(qty or 0)
    return {"product": ProductOut.model_validate(found["product"]), "qty": str(found["qty"]), "scale": found["scale"],
            "available": available}
