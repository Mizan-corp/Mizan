"""Month-end closing (ADR-014 D7): which months exist, which can be closed or reopened now.

The months run from the first one the books know to the current month (the workspace's time zone,
Africa/Cairo). With the accounting module on, the books begin with the first journal entry (or the
first month ever closed), as the accounting screens show them; without it, with the first money
movement: a sale, an expense, a safe, wallet or drawer movement, a customer receipt. Months close in
order, never the current one, and reopen from the latest closed one back.
"""
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.tenancy.clock import TZ_NAME, current_month

# The first month of each kind of finance activity, in the workspace's time zone.
FIRST_ACTIVITY = f"""
    SELECT MIN(m) FROM (
        SELECT MIN(month) AS m FROM accounting_periods WHERE tenant_id = :t
        UNION ALL SELECT to_char(MIN(created_at AT TIME ZONE '{TZ_NAME}'), 'YYYY-MM') FROM sales
            WHERE tenant_id = :t AND status IN ('confirmed', 'returned')
        UNION ALL SELECT to_char(MIN(date), 'YYYY-MM') FROM expenses WHERE tenant_id = :t AND status IN ('approved', 'cancelled')
        UNION ALL SELECT to_char(MIN(created_at AT TIME ZONE '{TZ_NAME}'), 'YYYY-MM') FROM safe_transactions WHERE tenant_id = :t
        UNION ALL SELECT to_char(MIN(created_at AT TIME ZONE '{TZ_NAME}'), 'YYYY-MM') FROM wallet_transactions WHERE tenant_id = :t
        UNION ALL SELECT to_char(MIN(created_at AT TIME ZONE '{TZ_NAME}'), 'YYYY-MM') FROM drawer_transactions WHERE tenant_id = :t
        UNION ALL SELECT to_char(MIN(created_at AT TIME ZONE '{TZ_NAME}'), 'YYYY-MM') FROM customer_payments WHERE tenant_id = :t
    ) x
"""

FIRST_ENTRY = """
    SELECT MIN(m) FROM (
        SELECT MIN(month) AS m FROM accounting_periods WHERE tenant_id = :t
        UNION ALL SELECT to_char(MIN(date), 'YYYY-MM') FROM acc_entries WHERE tenant_id = :t
    ) x
"""


def months_between(first: str, last: str) -> list[str]:
    """Every month from `first` to `last` included ("YYYY-MM")."""
    y, m = int(first[:4]), int(first[5:7])
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def previous(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"


async def accounting_on(db: AsyncSession) -> bool:
    from app.framework.activation import get_active_modules

    return "accounting" in set(await get_active_modules(db))


async def first_month(db: AsyncSession, tenant_id: uuid.UUID, accounting: bool | None = None) -> str | None:
    """The first month the books know (None: nothing yet)."""
    if accounting is None:
        accounting = await accounting_on(db)
    return await db.scalar(text(FIRST_ENTRY if accounting else FIRST_ACTIVITY), {"t": tenant_id})


async def month_rows(db: AsyncSession, tenant_id: uuid.UUID, accounting: bool | None = None) -> list[dict]:
    """Every month from the first one to the current one, newest first, with its status and whether
    it can be closed (the earliest open past month) or reopened (the latest closed month, unless its
    fiscal year's closing entry is in force) now."""
    if accounting is None:
        accounting = await accounting_on(db)
    now = current_month()
    rows = {r["month"]: dict(r) for r in (await db.execute(text("""
        SELECT p.month, p.status, p.closed_at, p.reopened_at, p.reopen_reason, cu.full_name AS closed_by_name,
               ru.full_name AS reopened_by_name
        FROM accounting_periods p LEFT JOIN users cu ON cu.id = p.closed_by LEFT JOIN users ru ON ru.id = p.reopened_by
        WHERE p.tenant_id = :t
    """), {"t": tenant_id})).mappings().all()}
    first = await first_month(db, tenant_id, accounting) or now
    months = months_between(min(first, now), now)
    closed = {m for m, r in rows.items() if r["status"] == "closed"}
    latest_closed = max(closed) if closed else None
    first_open = next((m for m in months if m not in closed and m < now), None)
    closings = []
    if accounting:
        closings = (await db.execute(text("""
            SELECT e.date FROM acc_entries e
            WHERE e.tenant_id = :t AND e.source_type = 'year_end' AND e.event = 'close'
              AND NOT EXISTS (SELECT 1 FROM acc_entries r WHERE r.reverses_id = e.id)
        """), {"t": tenant_id})).scalars().all()
    out = []
    for m in reversed(months):
        r = rows.get(m, {})
        status = r.get("status") or "open"
        blocked = any(d.strftime("%Y-%m") >= m for d in closings)
        out.append({"month": m, "status": status, "closed_at": r.get("closed_at"), "closed_by_name": r.get("closed_by_name"),
                    "reopened_at": r.get("reopened_at"), "reopened_by_name": r.get("reopened_by_name"),
                    "reopen_reason": r.get("reopen_reason"), "current": m == now,
                    "can_close": status != "closed" and m == first_open,
                    "can_reopen": status == "closed" and m == latest_closed and not blocked})
    return out
