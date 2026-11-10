"""FastAPI Router for Banquets, Conference Halls & Catering Events."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.platform.auth.models.user import User
from app.modules.hotel.hospitality.models import HotelBanquetEvent
from .schemas import BanquetEventCreate, BanquetStatusUpdate

router = APIRouter(prefix="/hospitality/banquet", tags=["HOT-BanquetEvents"])


@router.get("")
@router.get("/events")
async def list_banquet_events(
    status: Optional[str] = None,
    hall_name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(HotelBanquetEvent).where(HotelBanquetEvent.tenant_id == user.tenant_id)
    if status:
        query = query.where(HotelBanquetEvent.status == status)
    if hall_name:
        query = query.where(HotelBanquetEvent.hall_name == hall_name)
    query = query.order_by(HotelBanquetEvent.event_date.desc(), HotelBanquetEvent.created_at.desc())
    res = await db.execute(query)
    return res.scalars().all()


@router.post("")
@router.post("/events")
async def create_banquet_event(
    data: BanquetEventCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ref = f"BNQ-{uuid.uuid4().hex[:6].upper()}"
    event = HotelBanquetEvent(
        tenant_id=user.tenant_id,
        booking_ref=ref,
        hall_name=data.hall_name,
        client_name=data.client_name,
        client_phone=data.client_phone,
        event_type=data.event_type,
        event_date=data.event_date,
        start_time=data.start_time,
        end_time=data.end_time,
        guest_count=data.guest_count,
        catering_package=data.catering_package,
        total_amount=data.total_amount,
        deposit_amount=data.deposit_amount,
        status="confirmed",
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


@router.post("/events/{event_id}/status")
async def update_event_status(
    event_id: str,
    data: BanquetStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(HotelBanquetEvent).where(
            HotelBanquetEvent.id == event_id, HotelBanquetEvent.tenant_id == user.tenant_id
        )
    )
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Banquet event not found")

    event.status = data.status
    await db.commit()
    await db.refresh(event)
    return event
