"""Payment wallets — محافظ إلكترونية."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.framework import idempotency
from app.framework.events import notify
from app.dependencies import get_current_user, require_perm
from app.platform.auth.models.user import User
from app.activities.general.modules.finance.schemas.wallet import WalletCreate, WalletReset, WalletUpdate
from app.activities.general.modules.finance.services import wallets as wallets_service
from app.activities.general.modules.finance.services.access import branch_scope, sees_balances
from app.activities.general.modules.finance.services.ledger import day_bounds

router = APIRouter(prefix="/wallets", tags=["wallets"])

NOT_FOUND = "المحفظة غير موجودة"
PUBLIC_FIELDS = ("id", "name", "type", "phone", "is_active")


@router.get("")
async def list_wallets(include_inactive: bool = False, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    """Every signed-in user picks a wallet (a POS payment, a receipt); only `finance` and `reports`
    see the balances and the stopped wallets."""
    full = sees_balances(user)
    rows = (await db.execute(text(
        "SELECT * FROM payment_wallets WHERE (:all OR is_active) ORDER BY is_active DESC, type, name"
    ), {"all": include_inactive and full})).mappings().all()
    return [dict(r) if full else {k: r[k] for k in PUBLIC_FIELDS} for r in rows]


DUPLICATE_NAME = wallets_service.DUPLICATE_NAME


@router.post("", status_code=201)
async def create_wallet(data: WalletCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("finance"))):
    wallet = await wallets_service.create_wallet(db, data.name, data.type, data.phone, user.tenant_id)
    await db.commit()
    return wallet


async def _lock(db: AsyncSession, wid: uuid.UUID) -> dict:
    row = (await db.execute(text("SELECT * FROM payment_wallets WHERE id = :id FOR UPDATE"), {"id": wid})).mappings().first()
    if row is None:
        raise HTTPException(404, NOT_FOUND)
    return dict(row)


@router.put("/{wid}")
async def update_wallet(wid: uuid.UUID, data: WalletUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    """Change only the fields sent."""
    wallet = await _lock(db, wid)
    changes = data.model_dump(exclude_unset=True)
    for required in ("name", "type"):
        if required in changes and changes[required] is None:
            changes.pop(required)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if not changes:
        return wallet
    sets = ", ".join(f"{k} = :{k}" for k in changes)
    try:
        async with db.begin_nested():
            row = (await db.execute(text(f"UPDATE payment_wallets SET {sets} WHERE id = :id RETURNING *"),
                                    {**changes, "id": wid})).mappings().one()
    except IntegrityError:
        raise HTTPException(status_code=409, detail=DUPLICATE_NAME) from None
    await db.commit()
    return dict(row)


@router.delete("/{wid}", status_code=204)
async def delete_wallet(wid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    """Stop a wallet (it keeps its history). Only an empty wallet can be stopped."""
    wallet = await _lock(db, wid)
    if wallet["balance"] and wallet["balance"] != 0:
        raise HTTPException(409, f"لا يمكن إيقاف المحفظة — رصيدها {wallet['balance']} ج.م. قم بتحويل الرصيد أولاً")
    await db.execute(text("UPDATE payment_wallets SET is_active=false WHERE id=:id"), {"id": wid})
    await db.commit()


@router.post("/{wid}/activate")
async def activate_wallet(wid: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("finance"))):
    await _lock(db, wid)
    row = (await db.execute(text("UPDATE payment_wallets SET is_active=true WHERE id=:id RETURNING *"),
                            {"id": wid})).mappings().one()
    await db.commit()
    return dict(row)


@router.get("/summary")
async def wallets_summary(
    from_date: date | None = None,
    to_date: date | None = None,
    warehouse_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("finance", "reports")),
):
    """Confirmed sales per payment method and wallet: the number of invoices and their net total
    (lines less the invoice discount, counted once per invoice)."""
    branches = await branch_scope(db, current_user, warehouse_id)
    conditions = ["s.status = 'confirmed'"]
    params: dict = {}  # NOSONAR: values are parameterized
    start, end = day_bounds(from_date, to_date)
    if start:
        conditions.append("s.created_at >= :start")
        params["start"] = start
    if end:
        conditions.append("s.created_at < :end")
        params["end"] = end
    if branches is not None:
        conditions.append("s.warehouse_id = ANY(:whs)")
        params["whs"] = branches

    rows = await db.execute(text(f"""
        WITH inv AS (
            SELECT s.id, COALESCE(s.payment_method, 'cash') AS payment_method, s.wallet_id,
                   COALESCE(it.lines, 0) - COALESCE(s.discount_amount, 0) AS net
            FROM sales s
            LEFT JOIN LATERAL (
                SELECT SUM(si.qty * si.unit_price - si.discount) AS lines FROM sale_items si WHERE si.sale_id = s.id
            ) it ON true
            WHERE {' AND '.join(conditions)}
        )
        SELECT inv.payment_method, pw.name AS wallet_name, pw.phone AS wallet_phone, pw.type AS wallet_type,
               COUNT(*) AS invoice_count, COALESCE(SUM(inv.net), 0) AS total
        FROM inv LEFT JOIN payment_wallets pw ON pw.id = inv.wallet_id
        GROUP BY inv.payment_method, pw.name, pw.phone, pw.type
        ORDER BY total DESC
    """), params)
    return [dict(r._mapping) for r in rows.fetchall()]


@router.post("/{wid}/reset-balance", status_code=204)
async def reset_wallet_balance(wid: uuid.UUID, data: WalletReset | None = None, db: AsyncSession = Depends(get_db),
                               current_user: User = Depends(require_perm("finance")),
                               idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """Bring a wallet's balance to 0, recorded as an adjustment movement (never a silent overwrite)."""
    key = idempotency.key_of(idempotency_key, data.client_id if data else None)
    if await idempotency.claim(db, "wallet.reset", key, {"wallet_id": wid}, current_user.id) is not None:
        return
    old_balance = (await _lock(db, wid))["balance"]
    if old_balance != 0:
        await wallets_service.record_wallet_tx(db, wid, -old_balance, "adjustment", None, "تصفير الرصيد", current_user.id)
        await notify("wallet.balance_reset", db, movement_id=uuid.uuid4(), wallet_id=wid, old_balance=old_balance,
                     user_id=current_user.id)
    await idempotency.remember(db, "wallet.reset", key, {"old_balance": old_balance})
    await db.commit()


@router.get("/{wid}/history")
async def wallet_history(wid: uuid.UUID, limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db),
                         _=Depends(require_perm("finance"))):
    if not await db.scalar(text("SELECT 1 FROM payment_wallets WHERE id = :id"), {"id": wid}):
        raise HTTPException(404, NOT_FOUND)
    return await wallets_service.get_wallet_history(db, wid, limit)
