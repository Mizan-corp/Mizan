from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import HealthcareCostCenter
from .schemas import CostCenterCreate, CostCenterResponse

router = APIRouter(prefix="/api/healthcare/accounting", tags=["Healthcare - Accounting (HLT-18)"])

@router.get("/cost-centers", response_model=List[CostCenterResponse])
async def list_cost_centers(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(HealthcareCostCenter)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/cost-centers", response_model=CostCenterResponse)
async def create_cost_center(data: CostCenterCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    cc = HealthcareCostCenter(**data.model_dump())
    db.add(cc)
    await db.commit()
    await db.refresh(cc)
    return cc
