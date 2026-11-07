from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import MedicationProduct, MedicationDispenseRecord
from .schemas import MedicationCreate, MedicationResponse, DispenseCreate, DispenseResponse

router = APIRouter(prefix="/healthcare/pharmacy", tags=["Healthcare - Pharmacy (HLT-12)"])

@router.get("")
@router.get("/formulary", response_model=List[MedicationResponse])
async def list_medications(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(MedicationProduct)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("")
@router.post("/formulary", response_model=MedicationResponse)
async def create_medication(data: MedicationCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    med = MedicationProduct(**data.model_dump())
    db.add(med)
    await db.commit()
    await db.refresh(med)
    return med

@router.post("/dispense", response_model=DispenseResponse)
async def dispense_medication(data: DispenseCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    med = await db.get(MedicationProduct, data.medication_id)
    if not med:
        raise HTTPException(status_code=404, detail="الدواء غير موجود")
    if med.stock_qty < data.quantity:
        raise HTTPException(status_code=400, detail="الرصيد المتاح غير كافٍ للصرف")
    med.stock_qty -= data.quantity
    dispense = MedicationDispenseRecord(**data.model_dump())
    db.add(dispense)
    await db.commit()
    await db.refresh(dispense)
    return dispense
