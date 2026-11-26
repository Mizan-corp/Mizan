"""
GET /reports/ledger
The sale lines, returns and drawer movements of a date range (paged), with the range's totals.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.auth.models.user import User
from app.activities.general.modules.finance.services import ledger as ledger_service
from app.activities.general.modules.finance.services.access import branch_scope

router = APIRouter(prefix="/reports/ledger", tags=["ledger"])


@router.get("")
async def ledger(
    from_date: date,
    to_date: date,
    warehouse_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("finance", "reports")),
):
    branches = await branch_scope(db, current_user, warehouse_id)
    return await ledger_service.get_ledger(db, from_date, to_date, branches, page, page_size, warehouse_id=warehouse_id)
