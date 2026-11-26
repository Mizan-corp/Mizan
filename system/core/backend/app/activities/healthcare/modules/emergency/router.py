from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import EmergencyCase
from .schemas import EmergencyCaseCreate, EmergencyCaseResponse

router = APIRouter(prefix="/healthcare/emergency", tags=["Healthcare - Emergency (HLT-13)"])

@router.get("")
@router.get("/cases", response_model=List[EmergencyCaseResponse])
async def list_cases(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(EmergencyCase).order_by(EmergencyCase.arrived_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("")
@router.post("/cases", response_model=EmergencyCaseResponse)
async def create_case(data: EmergencyCaseCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    c = EmergencyCase(**data.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c

@router.patch("/cases/{id}/status")
async def update_case_status(id: int, status: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    c = await db.get(EmergencyCase, id)
    if not c:
        raise HTTPException(status_code=404, detail="حالة الطوارئ غير موجودة")
    c.status = status
    await db.commit()
    return {"id": id, "status": status}
