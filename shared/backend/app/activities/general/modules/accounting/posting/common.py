"""What the posting rules share: the workspace, and where a payment's money is in the ledger."""
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.services import chart


def tenant_of(obj=None) -> uuid.UUID:
    from app.platform.tenancy.context import current_tenant_id

    tid = getattr(obj, "tenant_id", None) if obj is not None and not isinstance(obj, dict) else (obj or {}).get("tenant_id")
    return tid or current_tenant_id.get()


async def shift_warehouse(db: AsyncSession, shift_id) -> uuid.UUID | None:
    if not shift_id:
        return None
    return await db.scalar(text("SELECT warehouse_id FROM shifts WHERE id = :id"), {"id": shift_id})


async def drawer_account(db: AsyncSession, tenant_id: uuid.UUID, warehouse_id: uuid.UUID | None) -> uuid.UUID:
    """The cashier drawer of a branch (one account per warehouse, whichever cashier holds it)."""
    return await chart.money_account(db, tenant_id, "drawer", warehouse_id or tenant_id)


async def payment_account(db: AsyncSession, tenant_id: uuid.UUID, method: str | None, *, safe_id=None, wallet_id=None,
                          drawer_warehouse: uuid.UUID | None = None) -> uuid.UUID:
    """Where the money of one payment line is: the named safe or wallet, else the branch drawer
    for cash, else the default bank account for bank, cheque and card. (Credit lines are the
    customer's receivable and are handled by the caller.)"""
    if safe_id:
        return await chart.money_account(db, tenant_id, "safe", safe_id)
    if wallet_id:
        return await chart.money_account(db, tenant_id, "wallet", wallet_id)
    if (method or "cash") == "cash":
        return await drawer_account(db, tenant_id, drawer_warehouse)
    return await chart.default_bank_account(db, tenant_id)


async def role(db: AsyncSession, tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    return (await chart.account_by_role(db, tenant_id, name)).id
