from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import MedicalAppointment
from .schemas import AppointmentCreate, AppointmentResponse, StatusUpdate

router = APIRouter(prefix="/healthcare/appointments", tags=["Healthcare - Appointments (HLT-03)"])

@router.get("", response_model=List[AppointmentResponse])
async def list_appointments(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(MedicalAppointment).order_by(MedicalAppointment.appointment_date.desc(), MedicalAppointment.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=AppointmentResponse)
async def create_appointment(data: AppointmentCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    appt = MedicalAppointment(**data.model_dump())
    db.add(appt)
    await db.commit()
    await db.refresh(appt)
    return appt

@router.patch("/{id}/status", response_model=AppointmentResponse)
async def update_status(id: int, data: StatusUpdate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    appt = await db.get(MedicalAppointment, id)
    if not appt:
        raise HTTPException(status_code=404, detail="الموعد غير موجود")
    appt.status = data.status
    if data.cancellation_reason:
        appt.cancellation_reason = data.cancellation_reason
    await db.commit()
    await db.refresh(appt)
    return appt
