from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import MedicationAdminRecord
from .schemas import MARCreate, MARResponse

router = APIRouter(prefix="/api/healthcare/nursing", tags=["Healthcare - Nursing & MAR (HLT-09)"])

@router.get("/mar", response_model=List[MARResponse])
async def list_mar_records(patient_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(MedicationAdminRecord)
    if patient_id:
        stmt = stmt.where(MedicationAdminRecord.patient_id == patient_id)
    stmt = stmt.order_by(MedicationAdminRecord.administered_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/mar", response_model=MARResponse)
async def record_administration(data: MARCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    rec = MedicationAdminRecord(**data.model_dump())
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec
