"""Accounting: API routes (ADR-014: the read API and reports, the chart's settings, the opening entry, the year-end closing, manual
journal entries and reversals). Posted entries have no edit or delete route, by design (D1): they are reversed."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.models import Account
from app.activities.general.modules.accounting.schemas import (AccountCreate, AccountUpdate, CategoryAccount, DraftIn, OpeningCreate,
                                                               ReverseIn, SettingsUpdate)
from app.activities.general.modules.accounting.services import chart, closing, journal, ledger, opening, posting, reports
from app.activities.general.modules.accounting.services import settings as acc_settings
from app.core.exceptions import BusinessError, NotFoundError
from app.db.base import get_db
from app.dependencies import require_perm
from app.framework.activation import require_module
from app.platform.auth.models.user import User

router = APIRouter(prefix="/accounting", tags=["Accounting"], dependencies=[Depends(require_module("accounting"))])


@router.get("/accounts")
async def list_accounts(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    tree = await ledger.accounts_tree(db, user.tenant_id)
    await db.commit()  # the chart may just have been copied
    return tree


async def _account(db: AsyncSession, tenant_id, account_id) -> Account:
    acc = (await db.execute(select(Account).where(Account.tenant_id == tenant_id, Account.id == account_id))).scalar_one_or_none()
    if acc is None:
        raise NotFoundError("الحساب غير موجود")
    return acc


@router.post("/accounts", status_code=201)
async def create_account(data: AccountCreate, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_perm("accounting:settings"))):
    await chart.ensure_chart(db, user.tenant_id)
    parent = await _account(db, user.tenant_id, data.parent_id)
    acc = await chart.add_account(db, parent, data.name.strip(), data.name_en, data.code, data.is_group)
    await db.commit()
    return {"id": acc.id, "code": acc.code, "name": acc.name, "type": acc.type, "parent_id": acc.parent_id,
            "is_group": acc.is_group}


@router.put("/accounts/{account_id}")
async def update_account(account_id: uuid.UUID, data: AccountUpdate, db: AsyncSession = Depends(get_db),
                         user: User = Depends(require_perm("accounting:settings"))):
    """Rename an account, or stop/resume one the posting rules don't rely on."""
    acc = await _account(db, user.tenant_id, account_id)
    if data.name is not None:
        acc.name = data.name.strip()
    if "name_en" in data.model_fields_set:
        acc.name_en = data.name_en
    if data.active is not None and data.active != acc.active:
        in_use = acc.role or await db.scalar(text("SELECT 1 FROM acc_money_accounts WHERE account_id = :id"), {"id": acc.id})
        if not data.active and in_use:
            raise BusinessError("لا يمكن إيقاف حساب تستخدمه القيود التلقائية")
        acc.active = data.active
    await db.commit()
    return {"id": acc.id, "code": acc.code, "name": acc.name, "name_en": acc.name_en, "active": acc.active}


@router.put("/categories/{category_id}/account")
async def set_category_account(category_id: uuid.UUID, data: CategoryAccount, db: AsyncSession = Depends(get_db),
                               user: User = Depends(require_perm("accounting:settings"))):
    """The account a financial category posts to (none: other income / other expenses)."""
    cat = (await db.execute(text("SELECT id, type FROM financial_categories WHERE id = :id"), {"id": category_id})).one_or_none()
    if cat is None:
        raise NotFoundError("البند غير موجود")
    if data.account_id:
        acc = await _account(db, user.tenant_id, data.account_id)
        if acc.is_group:
            raise BusinessError("اختر حساباً فرعياً وليس حساباً تجميعياً")
        wanted = "income" if cat.type == "income" else "expense"
        if acc.type != wanted:
            raise BusinessError("بند الإيرادات يُربط بحساب إيرادات، وبند المصروفات بحساب مصروفات")
    await db.execute(text("UPDATE financial_categories SET account_id = :a WHERE id = :id"),
                     {"a": data.account_id, "id": category_id})
    await db.commit()
    return {"id": category_id, "account_id": data.account_id}


@router.get("/entries")
async def list_entries(date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
                       source_type: str | None = None, account_id: uuid.UUID | None = None,
                       page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                       db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    return await ledger.list_entries(db, user.tenant_id, date_from=date_from, date_to=date_to, source_type=source_type,
                                     account_id=account_id, page=page, page_size=page_size)


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    user: User = Depends(require_perm("accounting:view"))):
    return await ledger.get_entry(db, user.tenant_id, entry_id)


@router.get("/trial-balance")
async def trial_balance(date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
                        warehouse_id: uuid.UUID | None = None, include_zero: bool = False, include_closing: bool = True,
                        db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    out = await reports.trial_balance(db, user.tenant_id, date_from, date_to, warehouse_id, include_zero, include_closing)
    await db.commit()  # the chart may just have been copied
    return out


@router.get("/income-statement")
async def income_statement(date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
                           warehouse_id: uuid.UUID | None = None, include_closing: bool = False,
                           db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    out = await reports.income_statement(db, user.tenant_id, date_from, date_to, warehouse_id, include_closing)
    await db.commit()
    return out


@router.get("/balance-sheet")
async def balance_sheet(as_of: date | None = None, warehouse_id: uuid.UUID | None = None, include_closing: bool = True,
                        db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    out = await reports.balance_sheet(db, user.tenant_id, as_of, warehouse_id, include_closing)
    await db.commit()
    return out


@router.get("/general-ledger/{account_id}")
async def general_ledger(account_id: uuid.UUID, date_from: date | None = Query(None, alias="from"),
                         date_to: date | None = Query(None, alias="to"), warehouse_id: uuid.UUID | None = None,
                         include_closing: bool = True, page: int = Query(1, ge=1), page_size: int = Query(200, ge=1, le=1000),
                         db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    out = await reports.general_ledger(db, user.tenant_id, account_id, date_from, date_to, warehouse_id, include_closing,
                                       page, page_size)
    await db.commit()
    return out


@router.get("/party-statement/{party_type}/{party_id}")
async def party_statement(party_type: str, party_id: uuid.UUID, date_from: date | None = Query(None, alias="from"),
                          date_to: date | None = Query(None, alias="to"), warehouse_id: uuid.UUID | None = None,
                          page: int = Query(1, ge=1), page_size: int = Query(200, ge=1, le=1000),
                          db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    """A customer's, supplier's or employee's statement from the lines carrying them as party."""
    out = await reports.party_statement(db, user.tenant_id, party_type, party_id, date_from, date_to, warehouse_id,
                                        page, page_size)
    await db.commit()
    return out


@router.get("/vat-report")
async def vat_report(date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
                     db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    """Output VAT, input VAT and the net payable from the ledger, with the documents' VAT by tax code (D6)."""
    from app.activities.general.modules.accounting.services.vat import vat_report as build

    out = await build(db, user.tenant_id, date_from, date_to)
    await db.commit()
    return out


@router.get("/reconciliation")
async def reconciliation(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    """The ledger against the operational balances (customers, suppliers, safes, wallets, stock): flags only."""
    out = await reports.reconciliation(db, user.tenant_id)
    await db.commit()
    return out


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    """The settings, and the state the screens need: the opening entry in force (none: the opening
    wizard is offered), the first entry's date, and the year-end closings in force."""
    out = await acc_settings.get(db, user.tenant_id)
    entry, _ = await posting.active_source(db, user.tenant_id, opening.SOURCE, "opening", opening.SOURCE)
    first = await db.scalar(text("SELECT MIN(date) FROM acc_entries WHERE tenant_id = :t"), {"t": user.tenant_id})
    closings = (await db.execute(text("""
        SELECT e.id, e.number, e.date, e.memo FROM acc_entries e
        WHERE e.tenant_id = :t AND e.source_type = 'year_end' AND e.event = 'close'
          AND NOT EXISTS (SELECT 1 FROM acc_entries r WHERE r.reverses_id = e.id)
        ORDER BY e.date DESC
    """), {"t": user.tenant_id})).mappings().all()
    return {**out, "opening_entry": None if entry is None else {"id": entry.id, "number": entry.number, "date": entry.date},
            "first_entry_date": first, "year_end_closings": [dict(r) for r in closings]}


@router.get("/periods")
async def list_periods(db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("accounting:view", "accounting:close", "accounting:settings"))):
    """Every month from the first one the books know (the first entry, or the first month ever closed)
    to the current month, newest first, with its status and whether it can be closed or reopened now
    (D7: in order); and each fiscal year with its closing entry in force. Closing and reopening go
    through /periods (finance)."""
    from app.activities.general.modules.finance.services import periods as finance_periods

    t = user.tenant_id
    now = finance_periods.current_month()
    out_months = await finance_periods.month_rows(db, t, accounting=True)
    months = [m["month"] for m in reversed(out_months)]
    closed = {m["month"] for m in out_months if m["status"] == "closed"}
    fy_start = (await acc_settings.get(db, t))["fiscal_year_start"]
    in_force = {r.number: r for r in (await db.execute(text("""
        SELECT e.id, e.number, e.date FROM acc_entries e
        WHERE e.tenant_id = :t AND e.source_type = 'year_end' AND e.event = 'close'
          AND NOT EXISTS (SELECT 1 FROM acc_entries r WHERE r.reverses_id = e.id)
    """), {"t": t})).all()}
    years = []
    today = posting.today()
    first_day = date(int(months[0][:4]), int(months[0][5:7]), 1)
    y = reports.fiscal_year_start_for(first_day, fy_start).year
    while True:
        start, end = closing.fiscal_year(y, fy_start)
        if start > today:
            break
        entry = next((e for e in in_force.values() if start <= e.date <= end), None)
        year_months = closing._months(max(start, first_day), end)
        years.append({"year": y, "from": start, "to": end, "over": end < today,
                      "open_months": [m for m in year_months if m not in closed],
                      "closing_entry": None if entry is None else {"id": entry.id, "number": entry.number, "date": entry.date}})
        y += 1
    return {"current_month": now, "fiscal_year_start": fy_start, "months": out_months, "years": list(reversed(years))}


# ── manual journal entries (D9) and reversals (D1) ────────────────────────────────────────────

@router.get("/drafts")
async def list_drafts(status: str = Query("draft", pattern="^(draft|posted)$"), page: int = Query(1, ge=1),
                      page_size: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db),
                      user: User = Depends(require_perm("accounting:journal"))):
    return await journal.list_drafts(db, user.tenant_id, status, page, page_size)


@router.get("/drafts/{draft_id}")
async def get_draft(draft_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    user: User = Depends(require_perm("accounting:journal"))):
    """A draft with its lines, totals and `problems`: what stops it from being posted (empty: it can be)."""
    return await journal.view(db, user.tenant_id, await journal._draft(db, user.tenant_id, draft_id))


@router.post("/drafts", status_code=201)
async def create_draft(data: DraftIn, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("accounting:journal"))):
    draft = await journal.save(db, user.tenant_id, data, user.id)
    out = await journal.view(db, user.tenant_id, draft)
    await db.commit()
    return out


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: uuid.UUID, data: DraftIn, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("accounting:journal"))):
    draft = await journal.save(db, user.tenant_id, data, user.id, draft_id)
    out = await journal.view(db, user.tenant_id, draft)
    await db.commit()
    return out


@router.delete("/drafts/{draft_id}", status_code=204)
async def delete_draft(draft_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("accounting:journal"))):
    await journal.remove(db, user.tenant_id, draft_id)
    await db.commit()


@router.post("/drafts/{draft_id}/post")
async def post_draft(draft_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_perm("accounting:journal"))):
    """Post a draft (D9): every rule is checked again, then the entry is written and the customers',
    suppliers', safes' and wallets' balances follow it. Posting twice returns the same entry."""
    from app.platform.audit.service import log as audit_log

    out = await journal.post_draft(db, user.tenant_id, draft_id, user.id)
    if not out["already"]:
        await audit_log(db, "acc_entry", "post", user.id, user.full_name, out["entry"]["id"],
                        {"draft_id": str(draft_id), "number": out["entry"]["number"]}, f"ترحيل قيد يومية {out['entry']['number']}")
    await db.commit()
    return out


@router.post("/entries/{entry_id}/reverse")
async def reverse_entry(entry_id: uuid.UUID, data: ReverseIn | None = None, db: AsyncSession = Depends(get_db),
                        user: User = Depends(require_perm("accounting:journal", "accounting:settings"))):
    """Reverse a manual entry (accounting:journal) or the opening entry (accounting:settings). A
    year-end closing is reversed through /year-end/reverse; a document's entry by cancelling the
    document. Idempotent; the reversal links to the original (`reverses_id`)."""
    from app.platform.audit.service import log as audit_log
    from app.platform.permissions.access import can

    data = data or ReverseIn()
    entry = await journal.entry_or_404(db, user.tenant_id, entry_id)
    needed = "accounting:journal" if journal.reversal_kind(entry) == "journal" else "accounting:settings"
    if not can(user, needed):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    out = await journal.reverse_entry(db, user.tenant_id, entry, data.date, data.memo, user.id)
    if not out["already"]:
        await audit_log(db, "acc_entry", "reverse", user.id, user.full_name, entry.id,
                        {"number": entry.number, "reversal": out["entry"]["number"], "memo": data.memo},
                        f"عكس القيد {entry.number}")
    await db.commit()
    return out


@router.put("/settings")
async def update_settings(data: SettingsUpdate, db: AsyncSession = Depends(get_db),
                          user: User = Depends(require_perm("accounting:settings"))):
    """The first month of the fiscal year (D7); fixed once a year-end closing is in force."""
    if await closing.closed_year_blocking(db, user.tenant_id, "0001-01"):
        raise BusinessError("لا يمكن تغيير بداية السنة المالية بعد إقفال سنة مالية. اعكس قيد الإقفال أولاً")
    out = await acc_settings.update(db, user.tenant_id, fiscal_year_start=data.fiscal_year_start)
    await db.commit()
    return out


@router.get("/opening/preview")
async def opening_preview(on: date | None = Query(None, alias="date"), db: AsyncSession = Depends(get_db),
                          user: User = Depends(require_perm("accounting:view"))):
    """The opening entry's lines and totals from today's balances, without posting anything."""
    out = await opening.preview(db, user.tenant_id, on or posting.today())
    await db.commit()
    return out


@router.post("/opening", status_code=201)
async def post_opening(data: OpeningCreate, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("accounting:settings"))):
    """Post the workspace's opening entry (once, unless reversed) and record the start date."""
    out = await opening.create(db, user.tenant_id, data.date or posting.today(), user.id)
    await db.commit()
    return out


@router.post("/year-end")
async def year_end(year: int = Query(..., ge=2000, le=2200), db: AsyncSession = Depends(get_db),
                   user: User = Depends(require_perm("accounting:close"))):
    """Post the closing entry of a fiscal year whose months are all closed (D7). Once per year."""
    out = await closing.close_year(db, user.tenant_id, year, user.id)
    await db.commit()
    return out


@router.post("/year-end/reverse")
async def year_end_reverse(year: int = Query(..., ge=2000, le=2200), db: AsyncSession = Depends(get_db),
                           user: User = Depends(require_perm("accounting:close"))):
    out = await closing.reverse_year(db, user.tenant_id, year, user.id)
    await db.commit()
    return out
