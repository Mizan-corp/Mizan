from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import PatientVitalRecord, PatientAllergyRecord
from .schemas import VitalCreate, VitalResponse, AllergyCreate, AllergyResponse

router = APIRouter(prefix="/healthcare/emr", tags=["Healthcare - EMR (HLT-05)"])

@router.get("")
@router.get("/vitals", response_model=List[VitalResponse])
async def list_vitals(patient_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(PatientVitalRecord)
    if patient_id:
        stmt = stmt.where(PatientVitalRecord.patient_id == patient_id)
    stmt = stmt.order_by(PatientVitalRecord.recorded_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("")
@router.post("/vitals", response_model=VitalResponse)
async def record_vitals(data: VitalCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    bmi = None
    if data.height_cm and data.weight_kg and data.height_cm > 0:
        h_m = float(data.height_cm) / 100.0
        bmi = round(float(data.weight_kg) / (h_m * h_m), 1)
    vital = PatientVitalRecord(**data.model_dump(), bmi=bmi)
    db.add(vital)
    await db.commit()
    await db.refresh(vital)
    return vital

@router.get("/allergies", response_model=List[AllergyResponse])
async def list_allergies(patient_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(PatientAllergyRecord)
    if patient_id:
        stmt = stmt.where(PatientAllergyRecord.patient_id == patient_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/allergies", response_model=AllergyResponse)
async def record_allergy(data: AllergyCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    allergy = PatientAllergyRecord(**data.model_dump())
    db.add(allergy)
    await db.commit()
    await db.refresh(allergy)
    return allergy
