"""The posting service (ADR-014 D1, D7): the only way a journal entry is written.

`post()` checks that the entry balances, that no line is on a group account, and that the month
of its date is open; it is idempotent on (source_type, source_id, event); and it runs in the
caller's transaction (flush, never commit), so a document and its entry are saved together or
not at all. A posted entry is never changed: `reverse()` writes the opposite entry.
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.models import Entry, Line
from app.core.exceptions import BusinessError

CAIRO = ZoneInfo("Africa/Cairo")
CENT = Decimal("0.01")


def today() -> date:
    """Today in Egypt: the posting date of things happening now."""
    return datetime.now(CAIRO).date()


def local_date(moment: datetime | date | None) -> date:
    if moment is None:
        return today()
    if isinstance(moment, datetime):
        return (moment if moment.tzinfo else moment.replace(tzinfo=ZoneInfo("UTC"))).astimezone(CAIRO).date()
    return moment


@dataclass
class PostLine:
    account_id: uuid.UUID
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    party_type: str | None = None
    party_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID | None = None


def dr(account_id, amount, **kw) -> PostLine:
    return PostLine(account_id, debit=Decimal(str(amount)).quantize(CENT), **kw)


def cr(account_id, amount, **kw) -> PostLine:
    return PostLine(account_id, credit=Decimal(str(amount)).quantize(CENT), **kw)


async def period_closed(db: AsyncSession, tenant_id: uuid.UUID, on: date) -> bool:
    return (await db.scalar(text(
        "SELECT status FROM accounting_periods WHERE tenant_id = :t AND month = :m"
    ), {"t": tenant_id, "m": on.strftime("%Y-%m")})) == "closed"


async def _next_number(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"acc_entries:{tenant_id}"})
    last = await db.scalar(text(
        "SELECT COALESCE(MAX(CAST(substring(number FROM 4) AS integer)), 0) FROM acc_entries "
        "WHERE tenant_id = :t AND number LIKE 'JE-%'"), {"t": tenant_id})
    return f"JE-{int(last) + 1:06d}"


async def find(db: AsyncSession, tenant_id: uuid.UUID, source_type: str, source_id, event: str) -> Entry | None:
    return (await db.execute(select(Entry).where(
        Entry.tenant_id == tenant_id, Entry.source_type == source_type, Entry.source_id == source_id,
        Entry.event == event))).scalar_one_or_none()


async def post(db: AsyncSession, tenant_id: uuid.UUID, source_type: str, source_id: uuid.UUID, event: str,
               on: date, lines: list[PostLine], memo: str | None = None, warehouse_id: uuid.UUID | None = None,
               user_id: uuid.UUID | None = None, reverses_id: uuid.UUID | None = None) -> Entry | None:
    """Post one entry. Lines of zero are dropped; nothing at all to post returns None. The same
    (source_type, source_id, event) posted again returns the existing entry."""
    existing = await find(db, tenant_id, source_type, source_id, event)
    if existing is not None:
        return existing
    lines = [ln for ln in lines if ln.debit or ln.credit]
    if not lines:
        return None
    for ln in lines:
        if ln.debit < 0 or ln.credit < 0 or (ln.debit and ln.credit):
            raise BusinessError("كل سطر في القيد إما مدين أو دائن بمبلغ موجب")
    debit = sum((ln.debit for ln in lines), Decimal("0"))
    credit = sum((ln.credit for ln in lines), Decimal("0"))
    if debit != credit or debit <= 0:
        raise BusinessError(f"القيد غير متوازن: المدين {debit} والدائن {credit}")
    ids = {ln.account_id for ln in lines}
    accounts = (await db.execute(text(
        "SELECT id, is_group, active, name FROM acc_accounts WHERE tenant_id = :t AND id = ANY(:ids)"
    ), {"t": tenant_id, "ids": list(ids)})).all()
    if len(accounts) != len(ids):
        raise BusinessError("حساب غير موجود في دليل الحسابات")
    for a in accounts:
        if a.is_group:
            raise BusinessError(f"لا يمكن الترحيل على الحساب التجميعي «{a.name}»")
        if not a.active:
            raise BusinessError(f"الحساب «{a.name}» موقوف")
    if await period_closed(db, tenant_id, on):
        raise BusinessError(f"الفترة المحاسبية {on.strftime('%Y-%m')} مغلقة — لا يمكن تسجيل قيود بتاريخ {on.isoformat()}. "
                            "أعد فتح الشهر أولاً (صلاحية إقفال الفترات) أو استخدم تاريخاً في فترة مفتوحة")
    entry = Entry(id=uuid.uuid4(), tenant_id=tenant_id, number=await _next_number(db, tenant_id), date=on,
                  source_type=source_type, source_id=source_id, event=event, memo=memo, warehouse_id=warehouse_id,
                  created_by=user_id, reverses_id=reverses_id)
    db.add(entry)
    await db.flush()
    for ln in lines:
        db.add(Line(tenant_id=tenant_id, entry_id=entry.id, account_id=ln.account_id, debit=ln.debit, credit=ln.credit,
                    party_type=ln.party_type, party_id=ln.party_id, warehouse_id=ln.warehouse_id or warehouse_id))
    await db.flush()
    return entry


async def reverse(db: AsyncSession, entry: Entry, on: date | None = None, user_id: uuid.UUID | None = None,
                  memo: str | None = None) -> Entry | None:
    """The reversing entry of `entry` (event 'reverse', lines swapped), dated `on` (default
    today). Idempotent: reversing twice returns the first reversal."""
    rows = (await db.execute(select(Line).where(Line.entry_id == entry.id))).scalars().all()
    lines = [PostLine(r.account_id, debit=r.credit, credit=r.debit, party_type=r.party_type, party_id=r.party_id,
                      warehouse_id=r.warehouse_id) for r in rows]
    return await post(db, entry.tenant_id, entry.source_type, entry.source_id, "reverse", on or today(), lines,
                      memo=memo or f"عكس القيد {entry.number}" + (f" — {entry.memo}" if entry.memo else ""),
                      warehouse_id=entry.warehouse_id, user_id=user_id, reverses_id=entry.id)


async def reverse_source(db: AsyncSession, tenant_id: uuid.UUID, source_type: str, source_id, event: str,
                         user_id: uuid.UUID | None = None, memo: str | None = None) -> Entry | None:
    """Reverse the entry a document posted, if it posted one (documents from before the ledger
    started have none, and nothing is reversed)."""
    entry = await find(db, tenant_id, source_type, source_id, event)
    if entry is None:
        return None
    return await reverse(db, entry, user_id=user_id, memo=memo)
