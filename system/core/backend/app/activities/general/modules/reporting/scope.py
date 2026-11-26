"""What a report may cover: the bound workspace, the branches the user reaches, and whole days in the
workspace's time zone.

- Branches: a manager, a holder of `supervise` or of `reports:finance` (accountants: they answer for
  the company's figures) sees every branch unless they pick one; anyone else
  sees only the branches assigned to them (`user_warehouses`), and asking for another one is a 403.
  So leaving the branch filter empty never widens a report.
- Days: a range `from`..`to` covers both days fully: `>= from 00:00` and `< (to + 1 day) 00:00`, in
  the workspace's time zone (`app/platform/tenancy/clock.py`, Africa/Cairo: the one the ledger
  dates entries in).
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ForbiddenError, NotFoundError
from app.dependencies import verify_warehouse_access
from app.platform.permissions.access import can
from app.platform.tenancy.clock import TZ, TZ_NAME, day_start, today  # noqa: F401  (re-exported)
from app.platform.tenancy.context import current_tenant_id

FINANCE = "reports:finance"  # profit, cost, debts, cash flow, stock at cost, the company overview
MAX_RANGE_DAYS = 3700  # about ten years


def day_range(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """[start, end): the first moment of `date_from` and the first moment after `date_to`."""
    if date_to < date_from:
        raise BusinessError("تاريخ البداية بعد تاريخ النهاية")
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise BusinessError("الفترة أطول من المسموح (عشر سنوات)")
    return day_start(date_from), day_start(date_to + timedelta(days=1))


@dataclass(frozen=True)
class Scope:
    """The branches a report covers: None for every branch of the workspace."""
    warehouses: tuple[uuid.UUID, ...] | None

    @property
    def everything(self) -> bool:
        return self.warehouses is None

    def sql(self, column: str, params: dict) -> str:
        """An `AND` filter on `column` (empty for every branch). Rows whose branch is NULL (an expense
        of the company) are left out of a branch-limited report."""
        if self.warehouses is None:
            return ""
        params["scope_wh"] = list(self.warehouses)
        return f" AND {column} = ANY(:scope_wh)"

    def out(self) -> list[str] | None:
        return None if self.warehouses is None else [str(w) for w in self.warehouses]


def is_supervisor(user) -> bool:
    return bool(user.is_manager or can(user, "supervise") or can(user, FINANCE))


async def user_branches(db: AsyncSession, user) -> tuple[uuid.UUID, ...]:
    rows = (await db.execute(text(
        "SELECT uw.warehouse_id FROM user_warehouses uw JOIN warehouses w ON w.id = uw.warehouse_id "
        "WHERE uw.user_id = :u ORDER BY w.name"), {"u": user.id})).scalars().all()
    return tuple(rows)


def require_workspace() -> None:
    """Reports read other modules' tables with raw SQL: only ever with a workspace bound (RLS)."""
    if current_tenant_id.get() is None:
        raise ForbiddenError("لا توجد مساحة عمل محددة")


async def branch_scope(db: AsyncSession, user, warehouse_id: uuid.UUID | None = None) -> Scope:
    require_workspace()
    if warehouse_id is not None:
        if (await db.execute(text("SELECT 1 FROM warehouses WHERE id = :id"), {"id": warehouse_id})).first() is None:
            raise NotFoundError("الفرع غير موجود")
        if not is_supervisor(user):  # who sees every branch may pick any one of them
            await verify_warehouse_access(db, user, warehouse_id)
        return Scope((warehouse_id,))
    if is_supervisor(user):
        return Scope(None)
    return Scope(await user_branches(db, user))


async def company_scope(db: AsyncSession, user) -> Scope:
    """Company-wide figures (safes, suppliers' debts): only for those who see every branch."""
    scope = await branch_scope(db, user)
    if not scope.everything:
        raise ForbiddenError("هذا التقرير يخص الشركة كلها، ويحتاج صلاحية الإشراف على كل الفروع")
    return scope
