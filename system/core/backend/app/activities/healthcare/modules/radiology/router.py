from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import RadiologyStudyOrder
from .schemas import RadiologyOrderCreate, RadiologyOrderResponse

router = APIRouter(prefix="/healthcare/radiology", tags=["Healthcare - Radiology (HLT-11)"])

@router.get("")
@router.get("/orders", response_model=List[RadiologyOrderResponse])
async def list_orders(patient_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(RadiologyStudyOrder)
    if patient_id:
        stmt = stmt.where(RadiologyStudyOrder.patient_id == patient_id)
    stmt = stmt.order_by(RadiologyStudyOrder.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("")
@router.post("/orders", response_model=RadiologyOrderResponse)
async def create_order(data: RadiologyOrderCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    ord = RadiologyStudyOrder(**data.model_dump())
    db.add(ord)
    await db.commit()
    await db.refresh(ord)
    return ord

@router.post("/orders/{id}/report")
async def record_findings(id: int, findings: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    ord = await db.get(RadiologyStudyOrder, id)
    if not ord:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    ord.findings = findings
    ord.status = "reported"
    await db.commit()
    return {"id": id, "status": "reported", "findings": findings}
