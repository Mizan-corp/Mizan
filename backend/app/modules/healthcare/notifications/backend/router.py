from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import HealthcareAlert
from .schemas import AlertCreate, AlertResponse

router = APIRouter(prefix="/healthcare/notifications", tags=["Healthcare - Notifications (HLT-23)"])

@router.get("", response_model=List[AlertResponse])
async def list_alerts(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(HealthcareAlert).order_by(HealthcareAlert.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=AlertResponse)
async def send_alert(data: AlertCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    alt = HealthcareAlert(**data.model_dump())
    db.add(alt)
    await db.commit()
    await db.refresh(alt)
    return alt
