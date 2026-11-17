"""Who reads which money: the permissions and branches the finance routes check.

Balances, histories and money reports need `finance` (`reports` for the summaries). A user who
neither supervises every branch (the manager flag, `supervise`, or `finance`: accountants answer for
the company's money) nor names a branch they may use
sees only their own branches: `branch_scope` gives the list to filter on (None: every branch).
"""
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, require_perm, verify_warehouse_access
from app.platform.auth.models.user import User, user_warehouses

MANAGER_ONLY = "هذه العملية تحتاج إلى مدير لديه صلاحية المالية"


def can(user, *perms: str) -> bool:
    from app.platform.permissions.access import can as _can

    return _can(user, *perms)


def supervises(user) -> bool:
    return bool(getattr(user, "is_manager", False)) or can(user, "supervise") or can(user, "finance")


def sees_balances(user) -> bool:
    return can(user, "finance", "reports")


async def require_finance_manager(user: User = Depends(require_perm("finance"))) -> User:
    """`finance`, and the manager flag: taking money out of a safe by hand."""
    if not user.is_manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=MANAGER_ONLY)
    return user


async def require_finance_or_manager(user: User = Depends(get_current_user)) -> User:
    """`finance`, or a manager: writing off what a customer owes, removing or stopping a customer."""
    if can(user, "finance") or user.is_manager:
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="هذه العملية تحتاج إلى صلاحية المالية أو مدير")


async def branch_scope(db: AsyncSession, user, warehouse_id: uuid.UUID | None) -> list[uuid.UUID] | None:
    """The branches a read covers: the one asked for (if the user may use it), else every branch for
    a supervisor, else the user's own branches (possibly none)."""
    if warehouse_id is not None:
        await verify_warehouse_access(db, user, warehouse_id)
        return [warehouse_id]
    if supervises(user):
        return None
    return list((await db.execute(
        select(user_warehouses.c.warehouse_id).where(user_warehouses.c.user_id == user.id)
    )).scalars().all())
