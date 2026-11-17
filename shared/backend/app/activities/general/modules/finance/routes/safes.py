"""Safes (خزنات) — treasury management. A bank account is a safe of type bank."""
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.framework import idempotency
from app.framework.events import notify
from app.dependencies import get_current_user, require_perm
from app.platform.auth.models.user import User
from app.activities.general.modules.finance.schemas.safe import SafeCreate, SafeDepositCreate, SafeTransferCreate, SafeUpdate, SafeWithdrawCreate
from app.activities.general.modules.finance.services import safes as safes_service
from app.activities.general.modules.finance.services.access import require_finance_manager, sees_balances

router = APIRouter(prefix="/safes", tags=["safes"])

PUBLIC_FIELDS = ("id", "name", "safe_type", "is_active")


@router.get("")
async def list_safes(include_inactive: bool = False, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """Every signed-in user picks a safe to pay into or out of (a receipt, a supplier payment); only
    `finance` and `reports` see the balances and the stopped safes."""
    full = sees_balances(user)
    rows = (await db.execute(text(
        "SELECT * FROM safes WHERE (:all OR is_active) ORDER BY is_active DESC, name"
    ), {"all": include_inactive and full})).mappings().all()
    return [dict(r) if full else {k: r[k] for k in PUBLIC_FIELDS} for r in rows]


@router.post("", status_code=201)
async def create_safe(data: SafeCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("finance"))):
    safe = await safes_service.create_safe(db, user.tenant_id, data.name, data.location, data.safe_type)
    await db.commit()
    return safe


@router.put("/{safe_id}")
async def update_safe(safe_id: uuid.UUID, data: SafeUpdate, db: AsyncSession = Depends(get_db),
                      _=Depends(require_perm("finance"))):
    safe = await safes_service.update_safe(db, safe_id, data.model_dump(exclude_unset=True))
    await db.commit()
    return safe


@router.delete("/{safe_id}")
async def deactivate_safe(safe_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    """Stop a safe (it keeps its history). Only an empty safe can be stopped."""
    safe = await safes_service.set_active(db, safe_id, False)
    await db.commit()
    return safe


@router.post("/{safe_id}/activate")
async def activate_safe(safe_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    safe = await safes_service.set_active(db, safe_id, True)
    await db.commit()
    return safe


@router.post("/transfer")
async def transfer_to_safe(data: SafeTransferCreate, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(require_perm("finance")),
                           idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """Transfer balance from a payment wallet to a safe."""
    key = idempotency.key_of(idempotency_key, data.client_id)
    payload = data.model_dump(exclude={"client_id"})
    if (replay := await idempotency.claim(db, "safe.transfer", key, payload, current_user.id)) is not None:
        return replay
    await safes_service.transfer_from_wallet(db, data.from_wallet_id, data.to_safe_id, data.amount, data.note, current_user)
    await notify("wallet.transferred_to_safe", db, movement_id=uuid.uuid4(), wallet_id=data.from_wallet_id,
                 safe_id=data.to_safe_id, amount=data.amount, note=data.note, user_id=current_user.id)
    result = {"ok": True}
    await idempotency.remember(db, "safe.transfer", key, result)
    await db.commit()
    return result


@router.post("/{safe_id}/deposit")
async def deposit_to_safe(
    safe_id: uuid.UUID,
    data: SafeDepositCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("finance")),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Record a cash deposit to a safe by hand (posted as other income). A shift's cash comes in
    through the shift (revenue delivery, closing with a manager), so no shift is named here."""
    from app.dependencies import verify_warehouse_access

    key = idempotency.key_of(idempotency_key, data.client_id)
    payload = {"safe_id": safe_id, **data.model_dump(exclude={"client_id"})}
    if (replay := await idempotency.claim(db, "safe.deposit", key, payload, current_user.id)) is not None:
        return replay
    await verify_warehouse_access(db, current_user, data.warehouse_id)
    result = await safes_service.deposit(db, safe_id, data.amount, current_user, warehouse_id=data.warehouse_id,
                                         received_by_id=data.received_by_id, notes=data.notes)
    await notify("safe.deposited", db, movement_id=uuid.uuid4(), safe_id=safe_id, amount=data.amount,
                 note=f"{result['doc_number']} {data.notes or ''}".strip(), user_id=current_user.id)
    await idempotency.remember(db, "safe.deposit", key, result)
    await db.commit()
    return result


@router.post("/{safe_id}/withdraw")
async def withdraw_from_safe(
    safe_id: uuid.UUID,
    data: SafeWithdrawCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_finance_manager),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Money out of a safe by hand (posted as other expenses): a manager with `finance` only."""
    key = idempotency.key_of(idempotency_key, data.client_id)
    payload = {"safe_id": safe_id, **data.model_dump(exclude={"client_id"})}
    if (replay := await idempotency.claim(db, "safe.withdraw", key, payload, current_user.id)) is not None:
        return replay
    balance = await safes_service.withdraw(db, safe_id, data.amount, data.note, current_user)
    await notify("safe.withdrawn", db, movement_id=uuid.uuid4(), safe_id=safe_id, amount=data.amount, note=data.note,
                 user_id=current_user.id)
    result = {"balance": balance}
    await idempotency.remember(db, "safe.withdraw", key, result)
    await db.commit()
    return result


@router.get("/{safe_id}/history")
async def safe_history(safe_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                       db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    if not await db.scalar(text("SELECT 1 FROM safes WHERE id = :id"), {"id": safe_id}):
        raise HTTPException(404, "الخزنة غير موجودة")
    rows = await db.execute(text("""
        SELECT st.*, u.full_name AS user_name FROM safe_transactions st LEFT JOIN users u ON u.id = st.created_by
        WHERE st.safe_id = :id ORDER BY st.created_at DESC, st.id DESC LIMIT :lim OFFSET :off
    """), {"id": safe_id, "lim": limit, "off": offset})
    return [dict(r._mapping) for r in rows.fetchall()]
