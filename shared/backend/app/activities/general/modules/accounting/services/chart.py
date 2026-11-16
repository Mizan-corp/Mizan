"""The chart of accounts (ADR-014 D2) and the money sub-accounts.

The standard chart (`charts/eg_standard.json`) is copied into a workspace the first time the
ledger is used there: `ensure_chart` is idempotent and runs before any posting or read, so it
doesn't matter which screen enabled the module (module centre, owner panel, activity change).

Each safe, wallet and branch drawer gets its own sub-account under the cash or bank group the
first time money moves through it (`money_account`), linked in `acc_money_accounts`.
"""
import json
import uuid
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.models import Account, MoneyAccount
from app.core.exceptions import BusinessError

CHARTS_DIR = Path(__file__).resolve().parents[1] / "charts"
STANDARD_CHART = "eg_standard"


@lru_cache(maxsize=4)
def load_chart(chart_id: str = STANDARD_CHART) -> dict:
    return json.loads((CHARTS_DIR / f"{chart_id}.json").read_text(encoding="utf-8"))


async def _lock(db: AsyncSession, key: str) -> None:
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": key})


async def ensure_chart(db: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Copy the standard chart into the workspace if it has no accounts yet. Returns whether it
    copied. Runs in the caller's transaction."""
    exists = await db.scalar(text("SELECT 1 FROM acc_accounts WHERE tenant_id = :t LIMIT 1"), {"t": tenant_id})
    if exists:
        return False
    await _lock(db, f"acc_chart:{tenant_id}")
    if await db.scalar(text("SELECT 1 FROM acc_accounts WHERE tenant_id = :t LIMIT 1"), {"t": tenant_id}):
        return False
    ids: dict[str, uuid.UUID] = {}
    for a in load_chart()["accounts"]:
        acc = Account(id=uuid.uuid4(), tenant_id=tenant_id, code=a["code"], name=a["name"], name_en=a.get("name_en"),
                      type=a["type"], parent_id=ids.get(a.get("parent")) if a.get("parent") else None,
                      is_group=bool(a.get("group")), role=a.get("role"), active=True)
        ids[a["code"]] = acc.id
        db.add(acc)
    await db.flush()
    return True


async def account_by_role(db: AsyncSession, tenant_id: uuid.UUID, role: str) -> Account:
    await ensure_chart(db, tenant_id)
    acc = (await db.execute(select(Account).where(Account.tenant_id == tenant_id, Account.role == role))).scalar_one_or_none()
    if acc is None:
        raise BusinessError(f"لا يوجد في دليل الحسابات حساب بالدور «{role}». راجع إعداد دليل الحسابات")
    return acc


async def _next_child_code(db: AsyncSession, parent: Account) -> str:
    codes = (await db.execute(select(Account.code).where(Account.tenant_id == parent.tenant_id,
                                                          Account.parent_id == parent.id))).scalars().all()
    n = len(codes) + 1
    taken = set((await db.execute(select(Account.code).where(Account.tenant_id == parent.tenant_id))).scalars().all())
    while f"{parent.code}{n:03d}" in taken:
        n += 1
    return f"{parent.code}{n:03d}"


async def add_account(db: AsyncSession, parent: Account, name: str, name_en: str | None = None,
                      code: str | None = None, is_group: bool = False) -> Account:
    """A sub-account under a group account (same type as its parent)."""
    if not parent.is_group:
        raise BusinessError("لا يمكن إضافة حساب فرعي إلا تحت حساب تجميعي")
    code = code or await _next_child_code(db, parent)
    if await db.scalar(text("SELECT 1 FROM acc_accounts WHERE tenant_id = :t AND code = :c"),
                       {"t": parent.tenant_id, "c": code}):
        raise BusinessError(f"رقم الحساب {code} مستخدم بالفعل")
    acc = Account(id=uuid.uuid4(), tenant_id=parent.tenant_id, code=code, name=name, name_en=name_en,
                  type=parent.type, parent_id=parent.id, is_group=is_group, active=True)
    db.add(acc)
    await db.flush()
    return acc


async def _money_name(db: AsyncSession, kind: str, ref_id: uuid.UUID) -> tuple[str, str, str]:
    """(group role, Arabic name, English name) of a money sub-account."""
    if kind == "safe":
        row = (await db.execute(text("SELECT name, safe_type FROM safes WHERE id = :id"), {"id": ref_id})).one_or_none()
        if row is None:
            raise BusinessError("الخزنة غير موجودة")
        if row.safe_type == "bank":
            return "bank_group", f"بنك — {row.name}", f"Bank — {row.name}"
        return "cash_group", f"خزنة — {row.name}", f"Safe — {row.name}"
    if kind == "wallet":
        name = await db.scalar(text("SELECT name FROM payment_wallets WHERE id = :id"), {"id": ref_id})
        if name is None:
            raise BusinessError("المحفظة غير موجودة")
        return "cash_group", f"محفظة — {name}", f"Wallet — {name}"
    if kind == "drawer":
        name = await db.scalar(text("SELECT name FROM warehouses WHERE id = :id"), {"id": ref_id}) or ""
        return "cash_group", f"درج كاشير — {name}".strip(" —"), f"Cashier drawer — {name}".strip(" —")
    return "bank_group", "حساب بنكي افتراضي", "Default bank account"


async def money_account(db: AsyncSession, tenant_id: uuid.UUID, kind: str, ref_id: uuid.UUID) -> uuid.UUID:
    """The ledger account of a safe, wallet or branch drawer (kind 'drawer', ref: the warehouse),
    created on first use."""
    q = select(MoneyAccount.account_id).where(MoneyAccount.tenant_id == tenant_id, MoneyAccount.kind == kind,
                                              MoneyAccount.ref_id == ref_id)
    found = (await db.execute(q)).scalar_one_or_none()
    if found:
        return found
    await _lock(db, f"acc_money:{tenant_id}")
    found = (await db.execute(q)).scalar_one_or_none()
    if found:
        return found
    group_role, name, name_en = await _money_name(db, kind, ref_id)
    parent = await account_by_role(db, tenant_id, group_role)
    acc = await add_account(db, parent, name, name_en)
    db.add(MoneyAccount(tenant_id=tenant_id, kind=kind, ref_id=ref_id, account_id=acc.id))
    await db.flush()
    return acc.id


async def default_bank_account(db: AsyncSession, tenant_id: uuid.UUID) -> uuid.UUID:
    """Where bank, cheque and card payments with no named account go: the first active bank
    (a safe of type bank), else a "default bank account" under the bank group."""
    bank = await db.scalar(text(
        "SELECT id FROM safes WHERE safe_type = 'bank' AND is_active ORDER BY created_at, id LIMIT 1"))
    if bank:
        return await money_account(db, tenant_id, "safe", bank)
    return await money_account(db, tenant_id, "default_bank", tenant_id)


async def category_account(db: AsyncSession, tenant_id: uuid.UUID, category_id: uuid.UUID | None, kind: str) -> uuid.UUID:
    """The account of a financial category, or other income / other expenses (kind: income or
    expense) when it has none, so posting never fails because of setup (D3)."""
    if category_id:
        acc = await db.scalar(text(
            "SELECT a.id FROM financial_categories c JOIN acc_accounts a ON a.id = c.account_id "
            "WHERE c.id = :id AND a.active AND NOT a.is_group"), {"id": category_id})
        if acc:
            return acc
    return (await account_by_role(db, tenant_id, "other_income" if kind == "income" else "other_expenses")).id
