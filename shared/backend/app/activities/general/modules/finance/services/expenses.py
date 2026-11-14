"""Expenses: approving one is the moment money leaves its wallet or safe; cancelling an approved
one puts the money back. An approved expense is never deleted (ADR-014 D4). Callers commit."""
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.activities.general.modules.finance.services import safes
from app.activities.general.modules.finance.services.wallets import record_wallet_tx

SOURCE_REQUIRED = "حدد الخزنة أو المحفظة التي يُصرف منها المصروف قبل اعتماده"
PAYROLL_MANAGED = "مصروف الرواتب يُدار من شاشة الرواتب"
FINAL_STATUSES = ("approved", "cancelled")


async def decide(db: AsyncSession, expense_id: uuid.UUID, approved: bool, notes: str | None, user, *,
                 safe_id: uuid.UUID | None = None, wallet_id: uuid.UUID | None = None) -> dict:
    """Approve (and pay) or reject an expense, in one transaction.

    An approved expense is final: approving or rejecting it again would pay twice or leave the
    money spent on a rejected expense. Approving needs the money's source: a wallet, or a safe
    (a bank account is a safe of type bank); the source can be given here if the draft lacks it.
    """
    current = (await db.execute(text("SELECT * FROM expenses WHERE id = :id FOR UPDATE"), {"id": expense_id})).mappings().first()
    if current is None:
        raise NotFoundError()
    if current["status"] == "approved":
        raise HTTPException(409, "المصروف معتمد بالفعل وتم صرفه")
    if current["status"] == "cancelled":
        raise HTTPException(409, "المصروف ملغى")

    if not approved:
        row = (await db.execute(text("""
            UPDATE expenses SET status = 'rejected', approved_by = :by, approved_at = now(), notes = COALESCE(:notes, notes)
            WHERE id = :id RETURNING *
        """), {"by": user.id, "notes": notes, "id": expense_id})).mappings().first()
        return dict(row)

    method = current["payment_method"]
    safe_id = safe_id or current["safe_id"]
    wallet_id = wallet_id or current["wallet_id"]
    if wallet_id and (method == "wallet" or not safe_id):
        method, safe_id = "wallet", None
    elif safe_id:
        wallet_id = None
        if method in (None, "", "wallet"):
            method = "cash"
    else:
        raise HTTPException(400, SOURCE_REQUIRED)

    row = (await db.execute(text("""
        UPDATE expenses SET status = 'approved', approved_by = :by, approved_at = now(), notes = COALESCE(:notes, notes),
            payment_method = :method, safe_id = :sid, wallet_id = :wid
        WHERE id = :id RETURNING *
    """), {"by": user.id, "notes": notes, "id": expense_id, "method": method, "sid": safe_id, "wid": wallet_id})).mappings().first()

    amount = Decimal(str(row["amount"]))
    note = row["description"] or "مصروف"
    if wallet_id:
        await record_wallet_tx(db, wallet_id, -amount, "expense", expense_id, note, user.id)
    else:
        await safes.pay_expense(db, safe_id, amount, note, user.id, expense_id)
    return dict(row)


async def cancel(db: AsyncSession, expense_id: uuid.UUID, reason: str | None, user) -> dict:
    """Cancel an approved expense: the money it took goes back to the same safe or wallet, and the
    expense stays on record as cancelled, with who cancelled it and when."""
    row = (await db.execute(text("SELECT * FROM expenses WHERE id = :id FOR UPDATE"), {"id": expense_id})).mappings().first()
    if row is None:
        raise NotFoundError()
    if row["status"] == "cancelled":
        raise HTTPException(409, "المصروف ملغى بالفعل")
    if row["status"] != "approved":
        raise HTTPException(409, "لا يُلغى إلا مصروف معتمد. المسودة أو المرفوض يمكن حذفه")
    if row["payment_method"] == "payroll" or (row["notes"] or "").startswith("HR payroll month"):
        raise HTTPException(409, PAYROLL_MANAGED)

    note = f"إلغاء مصروف: {row['description'] or ''}".strip()
    wallet_moves = (await db.execute(text(
        "SELECT wallet_id, amount FROM wallet_transactions WHERE ref_id = :id AND tx_type = 'expense'"
    ), {"id": expense_id})).all()
    for wallet_id, amount in wallet_moves:
        await record_wallet_tx(db, wallet_id, -Decimal(str(amount)), "expense_reversed", expense_id, note, user.id)

    safe_moves = (await db.execute(text(
        "SELECT safe_id, amount FROM safe_transactions WHERE ref_type = 'expense' AND ref_id = :id AND tx_type = 'withdraw'"
    ), {"id": expense_id})).all()
    if not wallet_moves and not safe_moves and row["payment_method"] == "safe" and row["safe_id"]:
        # Approved before safe movements carried their document (v81): the safe paid the amount.
        safe_moves = [(row["safe_id"], row["amount"])]
    for safe_id, amount in safe_moves:
        await safes._lock_safe(db, safe_id)
        await safes._post(db, safe_id, "deposit", Decimal(str(amount)), note, user.id, "expense_cancel", expense_id)

    updated = (await db.execute(text("""
        UPDATE expenses SET status = 'cancelled', cancelled_at = now(), cancelled_by = :by, cancel_reason = :reason
        WHERE id = :id RETURNING *
    """), {"by": user.id, "reason": reason, "id": expense_id})).mappings().first()
    return dict(updated)
