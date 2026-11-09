from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.base import get_db
from app.dependencies import get_current_user
from .models import BiomedicalDevice
from .schemas import DeviceCreate, DeviceResponse

router = APIRouter(prefix="/healthcare/equipment", tags=["Healthcare - Equipment (HLT-20)"])

@router.get("", response_model=List[DeviceResponse])
async def list_devices(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(BiomedicalDevice)
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("", response_model=DeviceResponse)
async def create_device(data: DeviceCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    dev = BiomedicalDevice(**data.model_dump())
    db.add(dev)
    await db.commit()
    await db.refresh(dev)
    return dev
