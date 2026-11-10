from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import ClinicalCredentialRecord
from .schemas import CredentialCreate, CredentialResponse

router = APIRouter(prefix="/healthcare/hr", tags=["Healthcare - HR & Credentials (HLT-19)"])

@router.get("")
@router.get("/credentials", response_model=List[CredentialResponse])
async def list_credentials(staff_id: int | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(ClinicalCredentialRecord)
    if staff_id:
        stmt = stmt.where(ClinicalCredentialRecord.staff_id == staff_id)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("")
@router.post("/credentials", response_model=CredentialResponse)
async def create_credential(data: CredentialCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    c = ClinicalCredentialRecord(**data.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c
