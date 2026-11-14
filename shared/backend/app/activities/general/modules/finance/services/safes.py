"""Safes (خزنات): balances change only here, under a row lock, with a transaction logged.

Amounts are Decimal end to end (money is never a float). Callers commit.
"""
import json
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.finance.services.wallets import record_wallet_tx


async def _lock_safe(db: AsyncSession, safe_id: uuid.UUID) -> dict:
    safe = (await db.execute(text("SELECT * FROM safes WHERE id = :id FOR UPDATE"), {"id": safe_id})).mappings().fetchone()
    if not safe:
        raise HTTPException(404, "الخزنة غير موجودة")
    return dict(safe)


async def _post(db: AsyncSession, safe_id: uuid.UUID, tx_type: str, delta: Decimal, note: str, user_id,
                ref_type: str | None = None, ref_id: uuid.UUID | None = None) -> Decimal:
    """Apply delta (+ in, - out) to a locked safe and log it with the document it belongs to
    (ref_type/ref_id); returns the new balance."""
    new_balance = (await db.execute(
        text("UPDATE safes SET balance = balance + :d WHERE id = :id RETURNING balance"), {"d": delta, "id": safe_id}
    )).scalar_one()
    await db.execute(text("""
        INSERT INTO safe_transactions (safe_id, tx_type, amount, balance_after, note, created_by, ref_type, ref_id)
        VALUES (:sid, :type, :amt, :bal, :note, :uid, :rtype, :rid)
    """), {"sid": safe_id, "type": tx_type, "amt": abs(delta), "bal": new_balance, "note": note, "uid": user_id,
           "rtype": ref_type, "rid": ref_id})
    return new_balance


async def transfer_from_wallet(db: AsyncSession, wallet_id: uuid.UUID, safe_id: uuid.UUID, amount: Decimal,
                               note: str | None, user) -> None:
    """Move money from a payment wallet into a safe."""
    wallet = (await db.execute(text("SELECT * FROM payment_wallets WHERE id = :id FOR UPDATE"), {"id": wallet_id})).mappings().fetchone()
    if not wallet:
        raise HTTPException(404, "Wallet not found")
    if Decimal(wallet["balance"]) < amount:
        raise HTTPException(400, f"رصيد المحفظة غير كافٍ ({wallet['balance']} ج.م)")
    await _lock_safe(db, safe_id)
    await record_wallet_tx(db, wallet_id, -amount, "safe_transfer", safe_id,
                           note or f"تحويل إلى خزنة {wallet['name']}", user.id)
    await _post(db, safe_id, "deposit", amount, note or f"تحويل من {wallet['name']}", user.id)


async def deposit(db: AsyncSession, safe_id: uuid.UUID, amount: Decimal, user, *, shift_id=None, warehouse_id=None,
                  received_by_id=None, notes: str | None = None) -> dict:
    """A cash deposit into a safe, with its numbered document archived."""
    safe = await _lock_safe(db, safe_id)
    seq = (await db.execute(text("SELECT nextval('invoice_seq')"))).scalar()
    doc_number = f"DEP-{seq:06d}"

    received_by_name = ""
    if received_by_id:
        received_by_name = (await db.execute(text("SELECT full_name FROM users WHERE id = :id"), {"id": received_by_id})).scalar() or ""

    await db.execute(text("""
        INSERT INTO safe_deposits
            (safe_id, shift_id, warehouse_id, amount, received_by, received_by_name,
             deposited_by, deposited_by_name, notes, doc_number)
        VALUES (:sid, :shift, :wh, :amt, :recv, :recv_name, :dep, :dep_name, :notes, :doc)
    """), {"sid": safe_id, "shift": shift_id, "wh": warehouse_id, "amt": amount, "recv": received_by_id,
           "recv_name": received_by_name, "dep": user.id, "dep_name": user.full_name, "notes": notes or "", "doc": doc_number})
    await _post(db, safe_id, "deposit", amount, notes or "", user.id)

    wh_name = ""
    if warehouse_id:
        wh_name = (await db.execute(text("SELECT name FROM warehouses WHERE id = :id"), {"id": warehouse_id})).scalar() or ""
    await db.execute(text("""
        INSERT INTO archived_documents (id, doc_number, doc_type, amount, created_by, metadata)
        VALUES (gen_random_uuid(), :doc, 'safe_deposit', :amt, :uid, cast(:meta as jsonb))
    """), {"doc": doc_number, "amt": amount, "uid": user.id, "meta": json.dumps({
        "safe_name": safe["name"] or "", "warehouse": wh_name, "received_by": received_by_name,
        "deposited_by": user.full_name, "notes": notes or "",
    })})
    return {"doc_number": doc_number, "amount": float(amount), "safe": safe["name"], "received_by": received_by_name}


async def withdraw(db: AsyncSession, safe_id: uuid.UUID, amount: Decimal, note: str | None, user) -> Decimal:
    safe = await _lock_safe(db, safe_id)
    if Decimal(safe["balance"]) < amount:
        raise HTTPException(400, f"رصيد الخزنة غير كافٍ ({safe['balance']} ج.م)")
    return await _post(db, safe_id, "withdraw", -amount, note or "", user.id)


async def pay_expense(db: AsyncSession, safe_id: uuid.UUID, amount: Decimal, note: str, user_id,
                      expense_id: uuid.UUID | None = None) -> Decimal:
    """Money out of a safe for an approved expense. Unlike withdraw(), this does not refuse an
    overdraft: approving an expense has always been allowed to take a safe below zero."""
    await _lock_safe(db, safe_id)
    return await _post(db, safe_id, "withdraw", -amount, note, user_id, "expense", expense_id)


async def pay_out(db: AsyncSession, safe_id: uuid.UUID, amount: Decimal, note: str, user_id, *,
                  ref_type: str, ref_id: uuid.UUID | None) -> Decimal:
    """Money out of a safe for a document (supplier payment, salaries, advance…). Refuses an
    overdraft: cash that isn't in the safe can't be paid out of it."""
    safe = await _lock_safe(db, safe_id)
    if not safe["is_active"]:
        raise HTTPException(400, "الخزنة موقوفة")
    if Decimal(safe["balance"]) < amount:
        raise HTTPException(400, f"رصيد الخزنة غير كافٍ ({safe['balance']} ج.م)")
    return await _post(db, safe_id, "withdraw", -amount, note, user_id, ref_type, ref_id)


async def take_in(db: AsyncSession, safe_id: uuid.UUID, amount: Decimal, note: str, user_id, *,
                  ref_type: str, ref_id: uuid.UUID | None) -> Decimal:
    """Money into a safe for a document (customer receipt, reversed payment…)."""
    safe = await _lock_safe(db, safe_id)
    if not safe["is_active"]:
        raise HTTPException(400, "الخزنة موقوفة")
    return await _post(db, safe_id, "deposit", amount, note, user_id, ref_type, ref_id)
