"""FastAPI Router for Hotel Folio & Incidentals Room Posting."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.platform.auth.models.user import User
from app.modules.hotel.hospitality.models import HotelFolioItem, HotelReservation
from .schemas import FolioChargeCreate, FolioSettleRequest

router = APIRouter(prefix="/hospitality/billing", tags=["HOT-BillingFolio"])


@router.get("")
@router.get("/folios")
async def list_folios(
    reservation_id: Optional[str] = None,
    room_number: Optional[str] = None,
    is_settled: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(HotelFolioItem).where(HotelFolioItem.tenant_id == user.tenant_id)
    if reservation_id:
        query = query.where(HotelFolioItem.reservation_id == reservation_id)
    if room_number:
        query = query.where(HotelFolioItem.room_number == room_number)
    if is_settled is not None:
        query = query.where(HotelFolioItem.is_settled == is_settled)
    query = query.order_by(HotelFolioItem.created_at.desc())
    res = await db.execute(query)
    return res.scalars().all()


@router.post("")
@router.post("/folios")
async def add_folio_charge(
    data: FolioChargeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    folio = HotelFolioItem(
        tenant_id=user.tenant_id,
        reservation_id=data.reservation_id,
        guest_name=data.guest_name,
        room_number=data.room_number,
        charge_type=data.charge_type,
        description=data.description,
        net_amount=data.net_amount,
        tax_amount=data.tax_amount,
        total_amount=data.total_amount,
        charge_date=data.charge_date,
        is_settled=False,
    )
    db.add(folio)

    # Cascade add charge to reservation total_charges if reservation exists
    if data.reservation_id:
        r_query = select(HotelReservation).where(
            HotelReservation.id == data.reservation_id,
            HotelReservation.tenant_id == user.tenant_id,
        )
        res = (await db.execute(r_query)).scalar_one_or_none()
        if res:
            res.total_charges += data.total_amount

    await db.commit()
    await db.refresh(folio)
    return folio


@router.post("/folios/{folio_id}/settle")
async def settle_folio_item(
    folio_id: str,
    data: FolioSettleRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(HotelFolioItem).where(
            HotelFolioItem.id == folio_id, HotelFolioItem.tenant_id == user.tenant_id
        )
    )
    folio = res.scalar_one_or_none()
    if not folio:
        raise HTTPException(status_code=404, detail="Folio item not found")

    folio.is_settled = True
    await db.commit()
    await db.refresh(folio)
    return {"status": "settled", "folio": folio}
