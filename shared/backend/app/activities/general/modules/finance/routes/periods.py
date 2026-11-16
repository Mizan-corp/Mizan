"""Accounting periods — month-end closing."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError
from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.platform.auth.models.user import User

router = APIRouter(prefix="/periods", tags=["periods"])

_initialized = False


def current_month() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m")


# Ensure accounting_periods table exists (run once at startup)
async def ensure_period_table(db: AsyncSession):
    """Create accounting_periods table if it doesn't exist."""
    global _initialized
    if _initialized:
        return
    # Requests run as the workspace role, which can't run DDL (#112): only create it if missing.
    if await db.scalar(text("SELECT to_regclass('public.accounting_periods')")) is not None:
        _initialized = True
        return
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS accounting_periods (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
                DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
            month VARCHAR(7) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            closed_by UUID REFERENCES users(id),
            closed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (tenant_id, month)
        )
    """))
    await db.commit()
    _initialized = True


@router.get("")
async def list_periods(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    # Do NOT call ensure_table from GET handler; table should be created at startup.
    # For compatibility with existing deployments, just skip the DDL.
    rows = await db.execute(text("SELECT * FROM accounting_periods ORDER BY month DESC LIMIT 24"))
    return [dict(r._mapping) for r in rows.fetchall()]


def _months_between(first: str, last: str) -> list[str]:
    """Every month from `first` to `last` included ("YYYY-MM")."""
    y, m = int(first[:4]), int(first[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _previous(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"


def _check_month(month: str) -> None:
    import re

    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise BusinessError("صيغة الشهر غير صحيحة (YYYY-MM)")


@router.post("/{month}/close")
async def close_period(month: str, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(require_perm("accounting:close", "finance"))):
    """Close a past month. Every earlier month since the books began (the first journal entry,
    or the first month ever closed) must be closed first (ADR-014 D7)."""
    _check_month(month)
    await ensure_period_table(db)
    if month >= current_month():
        raise BusinessError("لا يمكن إغلاق الشهر الحالي أو المستقبلي")
    existing = (await db.execute(text("SELECT status FROM accounting_periods WHERE month=:m"), {"m": month})).scalar_one_or_none()
    if existing == "closed":
        raise BusinessError(f"شهر {month} مغلق بالفعل")
    first = await db.scalar(text("""
        SELECT MIN(m) FROM (
            SELECT to_char(MIN(date), 'YYYY-MM') AS m FROM acc_entries
            UNION ALL SELECT MIN(month) FROM accounting_periods
        ) x
    """))
    if first and first < month:
        closed = set((await db.execute(text("SELECT month FROM accounting_periods WHERE status = 'closed'"))).scalars().all())
        missing = [m for m in _months_between(first, _previous(month)) if m not in closed]
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
                        current_user: User = Depends(require_perm("accounting:close", "finance"))):
    """Reopen a closed month, with a reason, logged. Later closed months are reopened first, so
    the closed months always run back from the latest one without gaps."""
    from app.platform.audit.service import log as audit_log

    _check_month(month)
    await ensure_period_table(db)
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


# Dead code — kept for reference but unused.
# async def check_period_open(month: str, db: AsyncSession):
#     """Raise BusinessError if the given month is closed."""
#     await ensure_table(db)
#     status = (await db.execute(text("SELECT status FROM accounting_periods WHERE month=:m"), {"m": month})).scalar_one_or_none()
#     if status == "closed":
#         raise BusinessError(f"هذا الشهر {month} مغلق — لا يمكن تعديل أو إضافة قيود")
