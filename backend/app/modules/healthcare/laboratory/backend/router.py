from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import LabTestItem, LabSpecimenOrder
from .schemas import LabTestCreate, LabTestResponse, SpecimenCreate, SpecimenResponse

router = APIRouter(prefix="/api/healthcare/laboratory", tags=["Healthcare - Laboratory (HLT-10)"])

@router.get("/tests", response_model=List[LabTestResponse])
async def list_tests(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(LabTestItem)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/tests", response_model=LabTestResponse)
async def create_test(data: LabTestCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    t = LabTestItem(**data.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t

@router.get("/specimens", response_model=List[SpecimenResponse])
async def list_specimens(patient_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(LabSpecimenOrder)
    if patient_id:
        stmt = stmt.where(LabSpecimenOrder.patient_id == patient_id)
    stmt = stmt.order_by(LabSpecimenOrder.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/specimens", response_model=SpecimenResponse)
async def create_specimen(data: SpecimenCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    sp = LabSpecimenOrder(**data.model_dump())
    db.add(sp)
    await db.commit()
    await db.refresh(sp)
    return sp

@router.post("/specimens/{id}/result")
async def record_result(id: int, result_value: str, is_abnormal: bool = False, is_critical: bool = False, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    sp = await db.get(LabSpecimenOrder, id)
    if not sp:
        raise HTTPException(status_code=404, detail="العينة غير موجودة")
    sp.result_value = result_value
    sp.is_abnormal = is_abnormal
    sp.is_critical = is_critical
    sp.status = "completed"
    sp.completed_at = datetime.utcnow()
    await db.commit()
    return {"id": id, "status": "completed", "result_value": result_value}
