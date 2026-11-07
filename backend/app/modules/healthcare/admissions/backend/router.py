from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import InpatientAdmission
from .schemas import AdmissionCreate, AdmissionResponse

router = APIRouter(prefix="/api/healthcare/admissions", tags=["Healthcare - Admissions (HLT-07)"])

@router.get("", response_model=List[AdmissionResponse])
async def list_admissions(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(InpatientAdmission).order_by(InpatientAdmission.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=AdmissionResponse)
async def create_admission(data: AdmissionCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    adm = InpatientAdmission(**data.model_dump())
    db.add(adm)
    await db.commit()
    await db.refresh(adm)
    return adm

@router.post("/{id}/discharge", response_model=AdmissionResponse)
async def discharge_patient(id: int, summary: str | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    adm = await db.get(InpatientAdmission, id)
    if not adm:
        raise HTTPException(status_code=404, detail="حالة التنويم غير موجودة")
    adm.status = "discharged"
    adm.discharge_date = datetime.utcnow()
    if summary:
        adm.discharge_summary = summary
    await db.commit()
    await db.refresh(adm)
    return adm
