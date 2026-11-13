"""Expenses: approving one is the moment money leaves its wallet or safe. Callers commit."""
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.activities.general.modules.finance.services import safes
from app.activities.general.modules.finance.services.wallets import record_wallet_tx


async def decide(db: AsyncSession, expense_id: uuid.UUID, approved: bool, notes: str | None, user) -> dict:
    """Approve (and pay) or reject an expense, in one transaction.

    An approved expense is final: approving or rejecting it again would pay twice or leave the
    money spent on a rejected expense.
    """
    current = (await db.execute(text("SELECT status FROM expenses WHERE id = :id FOR UPDATE"), {"id": expense_id})).scalar()
    if current is None:
        raise NotFoundError()
    if current == "approved":
        raise HTTPException(409, "المصروف معتمد بالفعل وتم صرفه")
    status = "approved" if approved else "rejected"
    row = (await db.execute(text("""
        UPDATE expenses SET status = :st, approved_by = :by, approved_at = now(), notes = COALESCE(:notes, notes)
        WHERE id = :id RETURNING *
    """), {"st": status, "by": user.id, "notes": notes, "id": expense_id})).mappings().first()

    if status == "approved":
        amount = Decimal(str(row["amount"]))
        note = row["description"] or "مصروف"
        if row["payment_method"] == "wallet" and row["wallet_id"]:
            await record_wallet_tx(db, row["wallet_id"], -amount, "expense", expense_id, note, user.id)
        elif row["payment_method"] == "safe" and row["safe_id"]:
            await safes.pay_expense(db, row["safe_id"], amount, note, user.id)
    return dict(row)
