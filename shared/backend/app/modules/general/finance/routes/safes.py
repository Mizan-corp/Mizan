"""Safes (خزنات) — treasury management."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_is_manager, require_perm
from app.platform.auth.models.user import User
from app.modules.general.finance.schemas.safe import SafeCreate, SafeDepositCreate, SafeTransferCreate, SafeUpdate, SafeWithdrawCreate
from app.modules.general.finance.services import safes as safes_service

router = APIRouter(prefix="/safes", tags=["safes"])


@router.get("")
async def list_safes(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute(text("SELECT * FROM safes WHERE is_active=true ORDER BY name"))
    return [dict(r._mapping) for r in rows.fetchall()]


@router.post("", status_code=201)
async def create_safe(data: SafeCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    r = await db.execute(text(
        "INSERT INTO safes (name, location) VALUES (:name, :loc) RETURNING *"
    ), {"name": data.name, "loc": data.location or ""})
    await db.commit()
    return dict(r.fetchone()._mapping)


@router.put("/{safe_id}")
async def update_safe(safe_id: uuid.UUID, data: SafeUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    await db.execute(text(
        "UPDATE safes SET name=:name, location=:loc WHERE id=:id"
    ), {"name": data.name, "loc": data.location or "", "id": safe_id})
    await db.commit()
    r = await db.execute(text("SELECT * FROM safes WHERE id=:id"), {"id": safe_id})
    return dict(r.fetchone()._mapping)


@router.post("/transfer")
async def transfer_to_safe(data: SafeTransferCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("finance"))):
    """Transfer balance from a payment wallet to a permanent safe."""
    await safes_service.transfer_from_wallet(db, data.from_wallet_id, data.to_safe_id, data.amount, data.note, current_user)
    await db.commit()
    return {"ok": True}


@router.post("/{safe_id}/deposit")
async def deposit_to_safe(
    safe_id: uuid.UUID,
    data: SafeDepositCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("finance"))
):
    """Record a cash deposit to a safe."""
    result = await safes_service.deposit(db, safe_id, data.amount, current_user, shift_id=data.shift_id,
                                         warehouse_id=data.warehouse_id, received_by_id=data.received_by_id, notes=data.notes)
    await db.commit()
    return result


@router.post("/{safe_id}/withdraw")
async def withdraw_from_safe(
    safe_id: uuid.UUID,
    data: SafeWithdrawCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_is_manager)
):
    balance = await safes_service.withdraw(db, safe_id, data.amount, data.note, current_user)
    await db.commit()
    return {"balance": balance}


@router.get("/{safe_id}/history")
async def safe_history(safe_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    rows = await db.execute(text("""
        SELECT * FROM safe_transactions WHERE safe_id = :id ORDER BY created_at DESC LIMIT 100
    """), {"id": safe_id})
    return [dict(r._mapping) for r in rows.fetchall()]
