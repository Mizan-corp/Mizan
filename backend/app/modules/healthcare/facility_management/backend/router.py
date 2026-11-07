from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import HealthcareFacility, FacilityDepartment
from .schemas import FacilityCreate, FacilityResponse, DepartmentCreate, DepartmentResponse

router = APIRouter(prefix="/api/healthcare/facilities", tags=["Healthcare - Facilities (HLT-01)"])

@router.get("", response_model=List[FacilityResponse])
async def list_facilities(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(HealthcareFacility).order_by(HealthcareFacility.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=FacilityResponse)
async def create_facility(data: FacilityCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    facility = HealthcareFacility(**data.model_dump())
    db.add(facility)
    await db.commit()
    await db.refresh(facility)
    return facility

@router.get("/departments", response_model=List[DepartmentResponse])
async def list_departments(facility_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(FacilityDepartment)
    if facility_id:
        stmt = stmt.where(FacilityDepartment.facility_id == facility_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/departments", response_model=DepartmentResponse)
async def create_department(data: DepartmentCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    dept = FacilityDepartment(**data.model_dump())
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return dept
