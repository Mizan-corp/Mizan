"""Where the money of a payment goes (ADR-014 D4): a safe (including bank accounts, safes of type
bank) or a payment wallet. Every payment that isn't a drawer movement goes through here, so each
one changes a real balance and is logged with the document it belongs to. Callers commit.
"""
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.finance.services import safes
from app.activities.general.modules.finance.services.wallets import record_wallet_tx

SOURCE_REQUIRED = "حدد الخزنة أو المحفظة التي خرج منها المبلغ أو دخل إليها"
ONE_SOURCE = "اختر خزنة أو محفظة واحدة فقط"


def check_source(safe_id: uuid.UUID | None, wallet_id: uuid.UUID | None, message: str = SOURCE_REQUIRED) -> None:
    if safe_id and wallet_id:
        raise HTTPException(400, ONE_SOURCE)
    if not safe_id and not wallet_id:
        raise HTTPException(400, message)


def method_of(safe_id: uuid.UUID | None, wallet_id: uuid.UUID | None, method: str | None = None) -> str:
    """The payment method stored with a payment: the one given, else what the source implies."""
    if method:
        return method
    return "wallet" if wallet_id else "cash"


async def _check_wallet(db: AsyncSession, wallet_id: uuid.UUID) -> None:
    active = (await db.execute(text("SELECT is_active FROM payment_wallets WHERE id = :id FOR UPDATE"),
                               {"id": wallet_id})).scalar_one_or_none()
    if active is None:
        raise HTTPException(404, "المحفظة غير موجودة")
    if not active:
        raise HTTPException(400, "المحفظة موقوفة")


async def money_out(db: AsyncSession, amount: Decimal, *, safe_id: uuid.UUID | None, wallet_id: uuid.UUID | None,
                    ref_type: str, ref_id: uuid.UUID | None, note: str, user_id) -> None:
    """Pay `amount` out of the safe or wallet. Neither may go below zero."""
    check_source(safe_id, wallet_id)
    amount = Decimal(str(amount))
    if amount <= 0:
        return
    if wallet_id:
        await _check_wallet(db, wallet_id)
        await record_wallet_tx(db, wallet_id, -amount, ref_type, ref_id, note, user_id)
    else:
        await safes.pay_out(db, safe_id, amount, note, user_id, ref_type=ref_type, ref_id=ref_id)


async def money_in(db: AsyncSession, amount: Decimal, *, safe_id: uuid.UUID | None, wallet_id: uuid.UUID | None,
                   ref_type: str, ref_id: uuid.UUID | None, note: str, user_id) -> None:
    """Receive `amount` into the safe or wallet."""
    check_source(safe_id, wallet_id)
    amount = Decimal(str(amount))
    if amount <= 0:
        return
    if wallet_id:
        await _check_wallet(db, wallet_id)
        await record_wallet_tx(db, wallet_id, amount, ref_type, ref_id, note, user_id)
    else:
        await safes.take_in(db, safe_id, amount, note, user_id, ref_type=ref_type, ref_id=ref_id)
