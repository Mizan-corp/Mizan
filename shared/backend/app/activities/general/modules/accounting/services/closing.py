"""The year-end closing entry (ADR-014 D7).

Fiscal year `YYYY` starts on the first day of the workspace's first fiscal month in YYYY and ends the
day before the same day a year later (the calendar year when the first month is January). Once every
month of the year is closed, one entry dated the last day of the year moves each income and expense
balance of the year (per branch too) to retained earnings (role `retained_earnings`): income
accounts are debited, expense accounts credited, and the profit (or loss) goes to retained earnings.

It is posted once per year; asking again is refused. The months are closed, so it is the one entry
allowed into a closed month (`allow_closed`), and reopening any month of a closed year is refused
until the closing entry is reversed. Reports leave it out with `include_closing=false`.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.services import chart as chart_service
from app.activities.general.modules.accounting.services import posting, reports
from app.activities.general.modules.accounting.services import settings as acc_settings
from app.activities.general.modules.accounting.services.posting import PostLine
from app.core.exceptions import BusinessError

ZERO = Decimal("0")
SOURCE = "year_end"


def fiscal_year(year: int, first_month: int) -> tuple[date, date]:
    start = date(year, first_month, 1)
    return start, date(year + 1, first_month, 1) - timedelta(days=1)


def _months(start: date, end: date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


async def _open_months(db: AsyncSession, tenant_id: uuid.UUID, start: date, end: date) -> list[str]:
    first = await db.scalar(text("SELECT MIN(date) FROM acc_entries WHERE tenant_id = :t AND source_type <> :s"),
                            {"t": tenant_id, "s": SOURCE})
    begin = max(start, first.replace(day=1)) if first else start
    closed = set((await db.execute(text(
        "SELECT month FROM accounting_periods WHERE tenant_id = :t AND status = 'closed'"), {"t": tenant_id})).scalars().all())
    return [m for m in _months(begin, end) if m not in closed]


async def _plan(db: AsyncSession, tenant_id: uuid.UUID, start: date, end: date) -> list[PostLine]:
    chart = await reports.load_chart(db, tenant_id)
    retained = chart.by_id[chart.by_role["retained_earnings"]]["id"]
    rows = (await db.execute(text("""
        SELECT l.account_id, l.warehouse_id, SUM(l.debit - l.credit) AS bal
        FROM acc_lines l JOIN acc_entries e ON e.id = l.entry_id JOIN acc_accounts a ON a.id = l.account_id
        WHERE l.tenant_id = :t AND e.date >= :df AND e.date <= :dt AND e.source_type <> :s AND a.type IN ('income', 'expense')
        GROUP BY l.account_id, l.warehouse_id
    """), {"t": tenant_id, "df": start, "dt": end, "s": SOURCE})).all()
    lines: list[PostLine] = []
    profit: dict[uuid.UUID | None, Decimal] = {}
    for r in rows:
        bal = Decimal(r.bal)
        if bal == 0:
            continue
        lines.append(posting.cr(r.account_id, bal, warehouse_id=r.warehouse_id) if bal > 0
                     else posting.dr(r.account_id, -bal, warehouse_id=r.warehouse_id))
        profit[r.warehouse_id] = profit.get(r.warehouse_id, ZERO) - bal
    for wh, amount in profit.items():
        if amount:
            lines.append(posting.cr(retained, amount, warehouse_id=wh) if amount > 0
                         else posting.dr(retained, -amount, warehouse_id=wh))
    return lines


async def close_year(db: AsyncSession, tenant_id: uuid.UUID, year: int, user_id: uuid.UUID | None) -> dict:
    """Post the closing entry of fiscal year `year`. Runs in the caller's transaction."""
    first_month = (await acc_settings.get(db, tenant_id))["fiscal_year_start"]
    start, end = fiscal_year(year, first_month)
    existing, source_id = await posting.active_source(db, tenant_id, SOURCE, str(year), "close")
    if existing is not None:
        raise BusinessError(f"السنة المالية {year} مقفلة بالفعل ({existing.number}). لا يُنشأ قيد الإقفال إلا مرة واحدة، "
                            "ويلزم عكسه أولاً لإعادة الإقفال")
    if end >= posting.today():
        raise BusinessError(f"السنة المالية {year} لم تنتهِ بعد (آخر يوم فيها {end.isoformat()})")
    open_months = await _open_months(db, tenant_id, start, end)
    if open_months:
        raise BusinessError("أغلق كل أشهر السنة المالية أولاً: " + "، ".join(open_months[:6]) + (" …" if len(open_months) > 6 else ""))
    lines = await _plan(db, tenant_id, start, end)
    if not lines:
        raise BusinessError(f"لا توجد إيرادات أو مصروفات في السنة المالية {year} لإقفالها")
    entry = await posting.post(db, tenant_id, SOURCE, source_id, "close", end, lines, user_id=user_id, allow_closed=True,
                               memo=f"إقفال السنة المالية {year}: ترحيل الإيرادات والمصروفات إلى الأرباح المحتجزة")
    retained = await _retained(db, tenant_id)
    net = sum((ln.credit - ln.debit for ln in lines if ln.account_id == retained), ZERO)
    return {"year": year, "from": start, "to": end, "entry": {"id": entry.id, "number": entry.number, "date": entry.date},
            "net_profit": float(net), "lines": len(lines)}


async def _retained(db: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    return (await chart_service.account_by_role(db, tenant_id, "retained_earnings")).id


async def reverse_year(db: AsyncSession, tenant_id: uuid.UUID, year: int, user_id: uuid.UUID | None) -> dict:
    """Undo the closing of `year` (dated the same day as the closing, so the years stay apart)."""
    existing, _ = await posting.active_source(db, tenant_id, SOURCE, str(year), "close")
    if existing is None:
        raise BusinessError(f"السنة المالية {year} غير مقفلة")
    rev = await posting.reverse(db, existing, on=existing.date, user_id=user_id, allow_closed=True)
    return {"year": year, "reversed": existing.number, "entry": {"id": rev.id, "number": rev.number, "date": rev.date}}


async def closed_year_blocking(db: AsyncSession, tenant_id: uuid.UUID, month: str) -> str | None:
    """The number of a closing entry still in force that covers `month` ("YYYY-MM") or any later
    one: the month can't be reopened until that closing is reversed."""
    first = date(int(month[:4]), int(month[5:7]), 1)
    row = await db.scalar(text("""
        SELECT e.number FROM acc_entries e
        WHERE e.tenant_id = :t AND e.source_type = :s AND e.event = 'close' AND e.date >= :d
          AND NOT EXISTS (SELECT 1 FROM acc_entries r WHERE r.reverses_id = e.id)
        ORDER BY e.date LIMIT 1
    """), {"t": tenant_id, "s": SOURCE, "d": first})
    return row
