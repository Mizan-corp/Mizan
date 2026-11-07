from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import HospitalWard, HospitalBed
from .schemas import WardCreate, WardResponse, BedCreate, BedResponse

router = APIRouter(prefix="/healthcare/beds", tags=["Healthcare - Beds & Wards (HLT-08)"])

@router.get("/wards", response_model=List[WardResponse])
async def list_wards(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(HospitalWard)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/wards", response_model=WardResponse)
async def create_ward(data: WardCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    ward = HospitalWard(**data.model_dump())
    db.add(ward)
    await db.commit()
    await db.refresh(ward)
    return ward

@router.get("", response_model=List[BedResponse])
async def list_beds(ward_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(HospitalBed)
    if ward_id:
        stmt = stmt.where(HospitalBed.ward_id == ward_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=BedResponse)
async def create_bed(data: BedCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    bed = HospitalBed(**data.model_dump())
    db.add(bed)
    await db.commit()
    await db.refresh(bed)
    return bed

@router.patch("/{id}/status")
async def update_bed_status(id: int, status: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    bed = await db.get(HospitalBed, id)
    if not bed:
        raise HTTPException(status_code=404, detail="السرير غير موجود")
    bed.status = status
    await db.commit()
    return {"id": id, "status": status}
