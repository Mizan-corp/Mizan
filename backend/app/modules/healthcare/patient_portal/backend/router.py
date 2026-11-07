from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import PatientPortalRequest
from .schemas import PortalRequestCreate, PortalRequestResponse

router = APIRouter(prefix="/healthcare/portal", tags=["Healthcare - Patient Portal (HLT-21)"])

@router.get("")
@router.get("/requests", response_model=List[PortalRequestResponse])
async def list_requests(patient_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(PatientPortalRequest)
    if patient_id:
        stmt = stmt.where(PatientPortalRequest.patient_id == patient_id)
    stmt = stmt.order_by(PatientPortalRequest.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("")
@router.post("/requests", response_model=PortalRequestResponse)
async def submit_request(data: PortalRequestCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    r = PatientPortalRequest(**data.model_dump())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r
