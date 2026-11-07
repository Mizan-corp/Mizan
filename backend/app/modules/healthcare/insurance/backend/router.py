from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import InsuranceClaimRecord
from .schemas import ClaimCreate, ClaimResponse

router = APIRouter(prefix="/healthcare/insurance", tags=["Healthcare - Insurance (HLT-16)"])

@router.get("")
@router.get("/claims", response_model=List[ClaimResponse])
async def list_claims(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(InsuranceClaimRecord).order_by(InsuranceClaimRecord.id.desc())
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("")
@router.post("/claims", response_model=ClaimResponse)
async def create_claim(data: ClaimCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    cl = InsuranceClaimRecord(**data.model_dump())
    db.add(cl)
    await db.commit()
    await db.refresh(cl)
    return cl

@router.patch("/claims/{id}/adjudicate")
async def adjudicate_claim(id: int, status: str, approved_amount: float = 0.0, rejection_reason: str | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    cl = await db.get(InsuranceClaimRecord, id)
    if not cl:
        raise HTTPException(status_code=404, detail="المطالبة غير موجودة")
    cl.status = status
    cl.approved_amount = approved_amount
    if rejection_reason:
        cl.rejection_reason = rejection_reason
    await db.commit()
    return {"id": id, "status": status, "approved_amount": approved_amount}
