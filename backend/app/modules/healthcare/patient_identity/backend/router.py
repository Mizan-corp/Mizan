from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import PatientIdentity
from .schemas import PatientCreate, PatientResponse

router = APIRouter(prefix="/api/healthcare/patients", tags=["Healthcare - Patient Identity (HLT-02)"])

@router.get("", response_model=List[PatientResponse])
async def list_patients(q: str | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(PatientIdentity).where(PatientIdentity.is_merged == False)
    if q:
        query = f"%{q}%"
        stmt = stmt.where(
            or_(
                PatientIdentity.first_name.ilike(query),
                PatientIdentity.last_name.ilike(query),
                PatientIdentity.phone.ilike(query),
                PatientIdentity.mrn.ilike(query),
                PatientIdentity.national_id.ilike(query),
            )
        )
    stmt = stmt.order_by(PatientIdentity.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=PatientResponse)
async def create_patient(data: PatientCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    patient = PatientIdentity(**data.model_dump())
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient

@router.get("/{id}", response_model=PatientResponse)
async def get_patient(id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    p = await db.get(PatientIdentity, id)
    if not p:
        raise HTTPException(status_code=404, detail="المريض غير موجود")
    return p
