from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import TeleconsultationSession
from .schemas import TeleconsultationCreate, TeleconsultationResponse

router = APIRouter(prefix="/healthcare/telemedicine", tags=["Healthcare - Telemedicine (HLT-22)"])

@router.get("/sessions", response_model=List[TeleconsultationResponse])
async def list_sessions(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(TeleconsultationSession).order_by(TeleconsultationSession.scheduled_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/sessions", response_model=TeleconsultationResponse)
async def schedule_session(data: TeleconsultationCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    sess = TeleconsultationSession(**data.model_dump())
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess
