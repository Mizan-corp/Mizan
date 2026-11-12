"""Scanning at the till: GET /pos/scan/{code} (a barcode, or a weighing-scale label in retail)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.modules.general.inventory.schemas.product import ProductOut
from app.modules.general.pos import service

router = APIRouter(prefix="/pos", tags=["pos"])


@router.get("/scan/{code}")
async def scan(code: str, db: AsyncSession = Depends(get_db), _=Depends(require_perm("pos"))):
    found = await service.scan(db, code)
    return {"product": ProductOut.model_validate(found["product"]), "qty": str(found["qty"]), "scale": found["scale"]}
