"""Accounting periods — month-end closing (ADR-014 D7). The months and their rules are in
services/periods.py; the accounting module's /accounting/periods shows the same months."""
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError
from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.auth.models.user import User
from app.activities.general.modules.finance.services import periods as periods_service
from app.activities.general.modules.finance.services.periods import current_month  # noqa: F401  (used by accounting)

router = APIRouter(prefix="/periods", tags=["periods"])

READ_PERMS = ("finance", "accounting:view", "accounting:close", "accounting:settings")
CLOSE_PERMS = ("accounting:close", "finance")


@router.get("")
async def list_periods(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm(*READ_PERMS))):
    """Every month from the first one the books know to the current month, newest first: its status,
    and whether it can be closed or reopened now."""
    return await periods_service.month_rows(db, user.tenant_id)


def _check_month(month: str) -> None:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise BusinessError("صيغة الشهر غير صحيحة (YYYY-MM)")


@router.post("/{month}/close")
async def close_period(month: str, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(require_perm(*CLOSE_PERMS))):
    """Close a past month. Every earlier month since the books began must be closed first."""
    _check_month(month)
    if month >= periods_service.current_month():
        raise BusinessError("لا يمكن إغلاق الشهر الحالي أو المستقبلي")
    # One close at a time per workspace, so two months can't both pass the order check.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"periods:{current_user.tenant_id}"})
    existing = (await db.execute(text("SELECT status FROM accounting_periods WHERE month=:m"), {"m": month})).scalar_one_or_none()
    if existing == "closed":
        raise BusinessError(f"شهر {month} مغلق بالفعل")
    first = await periods_service.first_month(db, current_user.tenant_id)
    if first and first < month:
        closed = set((await db.execute(text("SELECT month FROM accounting_periods WHERE status = 'closed'"))).scalars().all())
        missing = [m for m in periods_service.months_between(first, periods_service.previous(month)) if m not in closed]
        if missing:
            raise BusinessError(f"أغلق الأشهر السابقة أولاً بالترتيب: {', '.join(missing[:6])}{' …' if len(missing) > 6 else ''}")
    await db.execute(text("""
        INSERT INTO accounting_periods (month, status, closed_by, closed_at)
        VALUES (:m, 'closed', :by, now())
        ON CONFLICT (tenant_id, month) DO UPDATE SET status='closed', closed_by=:by, closed_at=now(), updated_at=now()
    """), {"m": month, "by": current_user.id})
    await db.commit()
    return {"detail": f"شهر {month} مغلق"}


class ReopenRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


@router.post("/{month}/reopen")
async def reopen_period(month: str, data: ReopenRequest, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(require_perm(*CLOSE_PERMS))):
    """Reopen a closed month, with a reason, logged. Later closed months are reopened first, so
    the closed months always run back from the latest one without gaps."""
    from app.platform.audit.service import log as audit_log

    _check_month(month)
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"periods:{current_user.tenant_id}"})
    existing = (await db.execute(text("SELECT status FROM accounting_periods WHERE month=:m"), {"m": month})).scalar_one_or_none()
    if not existing or existing != "closed":
        raise BusinessError(f"شهر {month} غير مغلق")
    later = (await db.execute(text(
        "SELECT month FROM accounting_periods WHERE status = 'closed' AND month > :m ORDER BY month DESC"
    ), {"m": month})).scalars().all()
    if later:
        raise BusinessError(f"أعد فتح الأشهر اللاحقة أولاً: {', '.join(later)}")
    from app.activities.general.modules.accounting.services.closing import closed_year_blocking

    closing_entry = await closed_year_blocking(db, current_user.tenant_id, month)
    if closing_entry:
        raise BusinessError(f"لا يمكن إعادة فتح {month}: سنته المالية مقفلة بالقيد {closing_entry}. اعكس قيد إقفال السنة أولاً")
    reason = data.reason.strip()
    await db.execute(text("""
        UPDATE accounting_periods SET status='open', closed_by=NULL, closed_at=NULL, updated_at=now(),
            reopened_by=:by, reopened_at=now(), reopen_reason=:reason
        WHERE month=:m
    """), {"m": month, "by": current_user.id, "reason": reason})
    await audit_log(db, "accounting_period", "reopen", current_user.id, current_user.full_name, None,
                    {"month": month, "reason": reason}, f"إعادة فتح شهر {month}: {reason}")
    await db.commit()
    return {"detail": f"شهر {month} مفتوح"}
