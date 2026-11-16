"""Accounting: API routes (ADR-014 step 2: a read API and the chart's settings). Posted entries
have no edit or delete route, by design (D1)."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.models import Account
from app.activities.general.modules.accounting.schemas import AccountCreate, AccountUpdate, CategoryAccount
from app.activities.general.modules.accounting.services import chart, ledger
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
                        db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("accounting:view"))):
    out = await ledger.trial_balance(db, user.tenant_id, date_from, date_to)
    await db.commit()
    return out
