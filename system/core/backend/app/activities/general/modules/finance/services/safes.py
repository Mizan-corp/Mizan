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


DEFAULT_SAFE_NAME = "الخزينة الرئيسية"
INACTIVE = "الخزنة موقوفة"


async def ensure_default_safe(db: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID | None:
    """A new workspace's main safe (balance 0), so expenses and receipts have somewhere to come
    from and go to from the first day. Nothing when the workspace already has a safe (the demo
    data brings its own). Returns the new safe's id."""
    await db.flush()
    if await db.scalar(text("SELECT 1 FROM safes WHERE tenant_id = :t LIMIT 1"), {"t": tenant_id}):
        return None
    return (await db.execute(text("""
        INSERT INTO safes (id, tenant_id, name, location, safe_type, balance, is_active)
        VALUES (gen_random_uuid(), :t, :n, NULL, 'permanent', 0, true) RETURNING id
    """), {"t": tenant_id, "n": DEFAULT_SAFE_NAME})).scalar_one()


async def create_safe(db: AsyncSession, tenant_id: uuid.UUID, name: str, location: str | None, safe_type: str) -> dict:
    row = (await db.execute(text("""
        INSERT INTO safes (id, tenant_id, name, location, safe_type, balance, is_active)
        VALUES (gen_random_uuid(), :t, :name, :loc, :type, 0, true) RETURNING *
    """), {"t": tenant_id, "name": name.strip(), "loc": location, "type": safe_type})).mappings().one()
    return dict(row)


async def update_safe(db: AsyncSession, safe_id: uuid.UUID, changes: dict) -> dict:
    """Change only the fields given; the balance changes only through movements."""
    safe = await _lock_safe(db, safe_id)
    changes = {k: v for k, v in changes.items() if k in ("name", "location", "safe_type")}
    if "name" in changes:
        if changes["name"] is None:
            raise HTTPException(400, "اسم الخزنة مطلوب")
        changes["name"] = changes["name"].strip()
    if changes.get("safe_type", safe["safe_type"]) is None:
        changes.pop("safe_type")
    if not changes:
        return safe
    sets = ", ".join(f"{k} = :{k}" for k in changes)
    return dict((await db.execute(text(f"UPDATE safes SET {sets} WHERE id = :id RETURNING *"),
                                  {**changes, "id": safe_id})).mappings().one())


async def set_active(db: AsyncSession, safe_id: uuid.UUID, active: bool) -> dict:
    """Stop or resume a safe. A safe holding money can't be stopped: move its balance first."""
    safe = await _lock_safe(db, safe_id)
    if not active and Decimal(str(safe["balance"])) != 0:
        raise HTTPException(409, f"لا يمكن إيقاف خزنة رصيدها {safe['balance']} ج.م. حوّل الرصيد أو اسحبه أولاً")
    return dict((await db.execute(text("UPDATE safes SET is_active = :a WHERE id = :id RETURNING *"),
                                  {"a": active, "id": safe_id})).mappings().one())


def _active(safe: dict) -> dict:
    if not safe["is_active"]:
        raise HTTPException(400, INACTIVE)
    return safe


async def transfer_from_wallet(db: AsyncSession, wallet_id: uuid.UUID, safe_id: uuid.UUID, amount: Decimal,
                               note: str | None, user) -> None:
    """Move money from a payment wallet into a safe."""
    wallet = (await db.execute(text("SELECT * FROM payment_wallets WHERE id = :id FOR UPDATE"), {"id": wallet_id})).mappings().fetchone()
    if not wallet:
        raise HTTPException(404, "المحفظة غير موجودة")
    if not wallet["is_active"]:
        raise HTTPException(400, "المحفظة موقوفة")
    if Decimal(wallet["balance"]) < amount:
        raise HTTPException(400, f"رصيد المحفظة غير كافٍ ({wallet['balance']} ج.م)")
    safe = _active(await _lock_safe(db, safe_id))
    await record_wallet_tx(db, wallet_id, -amount, "safe_transfer", safe_id,
                           note or f"تحويل إلى خزنة {safe['name']}", user.id)
    await _post(db, safe_id, "deposit", amount, note or f"تحويل من {wallet['name']}", user.id)


async def deposit(db: AsyncSession, safe_id: uuid.UUID, amount: Decimal, user, *, shift_id=None, warehouse_id=None,
                  received_by_id=None, notes: str | None = None) -> dict:
    """A cash deposit into a safe, with its numbered document archived. `shift_id` is for the
    shift flows only (the cash comes out of that shift's drawer); the branch and the receiver must
    be the workspace's."""
    safe = _active(await _lock_safe(db, safe_id))
    tid = safe["tenant_id"]
    wh_name = ""
    if warehouse_id:
        wh_name = (await db.execute(text("SELECT name FROM warehouses WHERE id = :id AND tenant_id = :t"),
                                    {"id": warehouse_id, "t": tid})).scalar()
        if wh_name is None:
            raise HTTPException(404, "الفرع غير موجود")
    received_by_name = ""
    if received_by_id:
        received_by_name = (await db.execute(text("SELECT full_name FROM users WHERE id = :id AND tenant_id = :t AND is_active"),
                                             {"id": received_by_id, "t": tid})).scalar()
        if received_by_name is None:
            raise HTTPException(404, "المستلم غير موجود في مساحة العمل")
    from app.platform.archive.numbering import next_number

    doc_number = await next_number(db, "DEP")  # counted per workspace (PLAT-6)

    await db.execute(text("""
        INSERT INTO safe_deposits
            (safe_id, shift_id, warehouse_id, amount, received_by, received_by_name,
             deposited_by, deposited_by_name, notes, doc_number)
        VALUES (:sid, :shift, :wh, :amt, :recv, :recv_name, :dep, :dep_name, :notes, :doc)
    """), {"sid": safe_id, "shift": shift_id, "wh": warehouse_id, "amt": amount, "recv": received_by_id,
           "recv_name": received_by_name, "dep": user.id, "dep_name": user.full_name, "notes": notes or "", "doc": doc_number})
    await _post(db, safe_id, "deposit", amount, notes or "", user.id)

    await db.execute(text("""
        INSERT INTO archived_documents (id, doc_number, doc_type, amount, created_by, metadata)
        VALUES (gen_random_uuid(), :doc, 'safe_deposit', :amt, :uid, cast(:meta as jsonb))
    """), {"doc": doc_number, "amt": amount, "uid": user.id, "meta": json.dumps({
        "safe_name": safe["name"] or "", "warehouse": wh_name, "received_by": received_by_name,
        "deposited_by": user.full_name, "notes": notes or "",
    })})
    return {"doc_number": doc_number, "amount": float(amount), "safe": safe["name"], "received_by": received_by_name}


async def withdraw(db: AsyncSession, safe_id: uuid.UUID, amount: Decimal, note: str | None, user) -> Decimal:
    safe = _active(await _lock_safe(db, safe_id))
    if Decimal(safe["balance"]) < amount:
        raise HTTPException(400, f"رصيد الخزنة غير كافٍ ({safe['balance']} ج.م)")
    return await _post(db, safe_id, "withdraw", -amount, note or "", user.id)


async def strict_balance(db: AsyncSession) -> bool:
    """The finance setting `strict_safe_balance` (on unless the workspace turned it off): an
    expense can't take a safe below zero."""
    from app.framework.loader import registry

    try:
        value = (await registry.get_settings(db, "finance"))["values"].get("strict_safe_balance", True)
    except KeyError:
        return True
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "0", "no", "off")
    return bool(value)


async def pay_expense(db: AsyncSession, safe_id: uuid.UUID, amount: Decimal, note: str, user_id,
                      expense_id: uuid.UUID | None = None, *, allow_overdraft: bool = False) -> Decimal:
    """Money out of a safe for an approved expense. A stopped safe pays nothing; a balance short of
    the amount is refused unless the workspace turned `strict_safe_balance` off (the caller passes
    `allow_overdraft`)."""
    safe = _active(await _lock_safe(db, safe_id))
    if not allow_overdraft and Decimal(safe["balance"]) < amount:
        raise HTTPException(400, f"رصيد الخزنة غير كافٍ ({safe['balance']} ج.م) لصرف المصروف "
                                 f"({amount} ج.م). أودع المبلغ أولاً أو اختر مصدرًا آخر")
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
