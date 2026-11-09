"""FastAPI Router for Hotel PMS (Front Desk & Room Rack)."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.modules.hospitality.models import HotelRoom, HotelReservation
from .schemas import RoomCreate, RoomStatusUpdate, ReservationCreate, CheckinRequest, CheckoutRequest

router = APIRouter(prefix="/hospitality/pms", tags=["HOT-PMS"])


@router.get("")
@router.get("/rooms")
async def list_rooms(
    floor: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(HotelRoom).where(HotelRoom.tenant_id == user.tenant_id)
    if floor:
        query = query.where(HotelRoom.floor == floor)
    if status:
        query = query.where(HotelRoom.status == status)
    query = query.order_by(HotelRoom.room_number)
    res = await db.execute(query)
    return res.scalars().all()


@router.post("")
@router.post("/rooms")
async def create_room(
    data: RoomCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = HotelRoom(
        tenant_id=user.tenant_id,
        room_number=data.room_number,
        room_type=data.room_type,
        floor=data.floor,
        bed_type=data.bed_type,
        max_guests=data.max_guests,
        base_rate=data.base_rate,
        status=data.status,
        amenities=data.amenities,
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


@router.post("/rooms/{room_id}/status")
async def update_room_status(
    room_id: str,
    data: RoomStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(HotelRoom).where(HotelRoom.id == room_id, HotelRoom.tenant_id == user.tenant_id)
    )
    room = res.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    room.status = data.status
    await db.commit()
    await db.refresh(room)
    return room


@router.get("/reservations")
async def list_reservations(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(HotelReservation).where(HotelReservation.tenant_id == user.tenant_id)
    if status:
        query = query.where(HotelReservation.status == status)
    query = query.order_by(HotelReservation.created_at.desc())
    res = await db.execute(query)
    return res.scalars().all()


@router.post("/reservations")
async def create_reservation(
    data: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ref = f"HTL-RES-{uuid.uuid4().hex[:6].upper()}"
    total = data.nights * data.room_rate
    res = HotelReservation(
        tenant_id=user.tenant_id,
        reservation_ref=ref,
        guest_name=data.guest_name,
        guest_phone=data.guest_phone,
        guest_passport=data.guest_passport,
        room_number=data.room_number,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        nights=data.nights,
        room_rate=data.room_rate,
        total_charges=total,
        paid_amount=data.paid_amount,
        status="confirmed",
    )
    db.add(res)
    await db.commit()
    await db.refresh(res)
    return res


@router.post("/reservations/{res_id}/checkin")
async def checkin_reservation(
    res_id: str,
    data: CheckinRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r_query = select(HotelReservation).where(
        HotelReservation.id == res_id, HotelReservation.tenant_id == user.tenant_id
    )
    res = (await db.execute(r_query)).scalar_one_or_none()
    if not res:
        raise HTTPException(status_code=404, detail="Reservation not found")
    res.status = "checked_in"
    res.paid_amount += data.initial_deposit

    # Update room status to occupied
    room_query = select(HotelRoom).where(
        HotelRoom.room_number == res.room_number, HotelRoom.tenant_id == user.tenant_id
    )
    room = (await db.execute(room_query)).scalar_one_or_none()
    if room:
        room.status = "occupied"

    await db.commit()
    return {"status": "checked_in", "reservation": res}


@router.post("/reservations/{res_id}/checkout")
async def checkout_reservation(
    res_id: str,
    data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    r_query = select(HotelReservation).where(
        HotelReservation.id == res_id, HotelReservation.tenant_id == user.tenant_id
    )
    res = (await db.execute(r_query)).scalar_one_or_none()
    if not res:
        raise HTTPException(status_code=404, detail="Reservation not found")
    res.status = "checked_out"
    if data.settle_all:
        res.paid_amount = res.total_charges

    # Update room status to vacant_dirty for housekeeping
    room_query = select(HotelRoom).where(
        HotelRoom.room_number == res.room_number, HotelRoom.tenant_id == user.tenant_id
    )
    room = (await db.execute(room_query)).scalar_one_or_none()
    if room:
        room.status = "vacant_dirty"

    await db.commit()
    return {"status": "checked_out", "reservation": res}
