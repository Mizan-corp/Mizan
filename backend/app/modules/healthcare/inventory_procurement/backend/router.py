from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import MedicalSupplyItem
from .schemas import SupplyItemCreate, SupplyItemResponse

router = APIRouter(prefix="/healthcare/inventory", tags=["Healthcare - Medical Inventory (HLT-17)"])

@router.get("/items", response_model=List[SupplyItemResponse])
async def list_items(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(MedicalSupplyItem)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/items", response_model=SupplyItemResponse)
async def create_item(data: SupplyItemCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    item = MedicalSupplyItem(**data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
