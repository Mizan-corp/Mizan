"""Accounting: API routes (ADR-014: the read API and reports, the chart's settings, the opening entry and the year-end closing). Posted entries
have no edit or delete route, by design (D1)."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.models import Account
from app.activities.general.modules.accounting.schemas import AccountCreate, AccountUpdate, CategoryAccount, OpeningCreate, SettingsUpdate
from app.activities.general.modules.accounting.services import chart, closing, ledger, opening, posting, reports
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


@router.get("/reconciliation")
async def reconciliation(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    """The ledger against the operational balances (customers, suppliers, safes, wallets, stock): flags only."""
    out = await reports.reconciliation(db, user.tenant_id)
    await db.commit()
    return out


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    return await acc_settings.get(db, user.tenant_id)


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
