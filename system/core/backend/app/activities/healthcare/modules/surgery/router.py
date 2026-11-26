from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import SurgicalCase
from .schemas import SurgicalCaseCreate, SurgicalCaseResponse

router = APIRouter(prefix="/healthcare/surgery", tags=["Healthcare - Surgery (HLT-14)"])

@router.get("")
@router.get("/cases", response_model=List[SurgicalCaseResponse])
async def list_cases(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(SurgicalCase).order_by(SurgicalCase.scheduled_date.desc(), SurgicalCase.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("")
@router.post("/cases", response_model=SurgicalCaseResponse)
async def create_case(data: SurgicalCaseCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    sc = SurgicalCase(**data.model_dump())
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    return sc

@router.post("/cases/{id}/who-checklist")
async def complete_who_checklist(id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    sc = await db.get(SurgicalCase, id)
    if not sc:
        raise HTTPException(status_code=404, detail="الحالة الجراحية غير موجودة")
    sc.who_checklist_completed = True
    await db.commit()
    return {"id": id, "who_checklist_completed": True}
