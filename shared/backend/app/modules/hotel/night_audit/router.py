"""FastAPI Router for Hotel Night Audit & Financial Reconciliations."""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.platform.auth.models.user import User
from app.modules.hotel.hospitality.models import HotelFolioItem, HotelNightAudit, HotelReservation, HotelRoom
from .schemas import NightAuditRunRequest

router = APIRouter(prefix="/hospitality/night-audit", tags=["HOT-NightAudit"])


@router.get("")
@router.get("/audits")
async def list_night_audits(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(HotelNightAudit)
        .where(HotelNightAudit.tenant_id == user.tenant_id)
        .order_by(HotelNightAudit.created_at.desc())
    )
    res = await db.execute(query)
    return res.scalars().all()


@router.post("")
@router.post("/run-audit")
async def run_night_audit(
    data: NightAuditRunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    audit_date = data.audit_date or datetime.utcnow().strftime("%Y-%m-%d")

    # 1. Total & Occupied rooms count
    rooms_query = select(HotelRoom).where(HotelRoom.tenant_id == user.tenant_id)
    rooms = (await db.execute(rooms_query)).scalars().all()
    total_rooms = len(rooms) or 1
    occupied_rooms = len([r for r in rooms if r.status == "occupied"])

    occupancy_rate = round((occupied_rooms / total_rooms) * 100, 1)

    # 2. Revenue calculation
    # Room revenue from active reservations checked-in
    res_query = select(func.sum(HotelReservation.room_rate)).where(
        HotelReservation.tenant_id == user.tenant_id,
        HotelReservation.status == "checked_in",
    )
    room_rev = (await db.execute(res_query)).scalar() or 0.0

    # F&B / incidentals revenue from folio items
    folio_query = select(func.sum(HotelFolioItem.total_amount)).where(
        HotelFolioItem.tenant_id == user.tenant_id,
        HotelFolioItem.charge_date == audit_date,
    )
    fnb_rev = (await db.execute(folio_query)).scalar() or 0.0

    total_revenue = room_rev + fnb_rev

    # ADR & RevPAR
    adr = round(room_rev / occupied_rooms, 2) if occupied_rooms > 0 else 0.0
    revpar = round(room_rev / total_rooms, 2)

    audit = HotelNightAudit(
        tenant_id=user.tenant_id,
        audit_date=audit_date,
        total_rooms=total_rooms,
        occupied_rooms=occupied_rooms,
        occupancy_rate=occupancy_rate,
        room_revenue=room_rev,
        fnb_revenue=fnb_rev,
        total_revenue=total_revenue,
        adr=adr,
        revpar=revpar,
        conducted_by=data.conducted_by or user.name or "مدقق الحسابات الليلي",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit
