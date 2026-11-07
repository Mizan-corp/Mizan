from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import ClinicalEncounter
from .schemas import EncounterCreate, EncounterResponse

router = APIRouter(prefix="/api/healthcare/consultations", tags=["Healthcare - Consultation (HLT-06)"])

@router.get("", response_model=List[EncounterResponse])
async def list_encounters(patient_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(ClinicalEncounter)
    if patient_id:
        stmt = stmt.where(ClinicalEncounter.patient_id == patient_id)
    stmt = stmt.order_by(ClinicalEncounter.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=EncounterResponse)
async def create_encounter(data: EncounterCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    enc = ClinicalEncounter(**data.model_dump())
    db.add(enc)
    await db.commit()
    await db.refresh(enc)
    return enc

@router.post("/{id}/finalize", response_model=EncounterResponse)
async def finalize_encounter(id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    enc = await db.get(ClinicalEncounter, id)
    if not enc:
        raise HTTPException(status_code=404, detail="الكشف غير موجود")
    enc.status = "finalized"
    enc.signed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(enc)
    return enc
