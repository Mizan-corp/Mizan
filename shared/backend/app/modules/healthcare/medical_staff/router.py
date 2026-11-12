from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import MedicalStaff
from .schemas import StaffCreate, StaffResponse

router = APIRouter(prefix="/healthcare/medical-staff", tags=["Healthcare - Medical Staff (HLT-04)"])

@router.get("", response_model=List[StaffResponse])
async def list_staff(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(MedicalStaff).order_by(MedicalStaff.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=StaffResponse)
async def create_staff(data: StaffCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    staff = MedicalStaff(**data.model_dump())
    db.add(staff)
    await db.commit()
    await db.refresh(staff)
    return staff
