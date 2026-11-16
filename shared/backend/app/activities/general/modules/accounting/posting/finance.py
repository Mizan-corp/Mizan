"""Posting rules for expenses, safes and wallets (ADR-014 D3).

Expense approved (source 'expense', event 'approve'), dated the expense's date (today if later):
    Dr the category's expense account, else other expenses / Cr the safe or wallet it was paid from
Expense cancelled: the reversing entry of the approval.

Safe and wallet movements made by hand (source 'safe_movement' / 'wallet_movement'). Movements
that belong to a document (a sale, an expense, a customer receipt…) are posted with the document,
never here, so nothing is posted twice:
    deposit into a safe for a shift (shift_id given):  Dr safe / Cr that branch's drawer
    other deposit into a safe:                          Dr safe / Cr other income
    withdrawal from a safe:                             Dr other expenses / Cr safe
    wallet → safe transfer:                             Dr safe / Cr wallet
    wallet balance reset to zero:                       Dr other expenses / Cr wallet (or the opposite)
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.posting.common import drawer_account, role, shift_warehouse, tenant_of
from app.activities.general.modules.accounting.services import chart
from app.activities.general.modules.accounting.services.posting import cr, dr, post, reverse_source, today


def _is_payroll(expense: dict) -> bool:
    return expense.get("payment_method") == "payroll" or (expense.get("notes") or "").startswith("HR payroll month")


async def on_expense_approved(db: AsyncSession, *, expense: dict, user_id=None, **_) -> None:
    if _is_payroll(expense):
        return  # payroll is posted with payroll (ADR-014 D12 step 3)
    amount = Decimal(str(expense["amount"] or 0))
    if amount <= 0:
        return
    tid = tenant_of(expense)
    if expense.get("wallet_id"):
        money = await chart.money_account(db, tid, "wallet", expense["wallet_id"])
    else:
        money = await chart.money_account(db, tid, "safe", expense["safe_id"])
    account = await chart.category_account(db, tid, expense.get("category_id"), "expense")
    on = expense.get("date") or today()
    if isinstance(on, date) and on > today():
        on = today()
    await post(db, tid, "expense", expense["id"], "approve", on, [dr(account, amount), cr(money, amount)],
               memo=f"مصروف: {expense.get('description') or ''}".strip(), warehouse_id=expense.get("warehouse_id"),
               user_id=user_id)


async def on_expense_cancelled(db: AsyncSession, *, expense: dict, user_id=None, **_) -> None:
    await reverse_source(db, tenant_of(expense), "expense", expense["id"], "approve", user_id=user_id,
                         memo=f"إلغاء مصروف: {expense.get('description') or ''}".strip())


async def on_safe_deposited(db: AsyncSession, *, movement_id, safe_id, amount, shift_id=None, note=None,
                            user_id=None, **_) -> None:
    tid = tenant_of()
    amount = Decimal(str(amount))
    safe = await chart.money_account(db, tid, "safe", safe_id)
    wh = await shift_warehouse(db, shift_id)
    if shift_id:
        source, memo = await drawer_account(db, tid, wh), "إيداع نقدية وردية في الخزنة"
    else:
        source, memo = await role(db, tid, "other_income"), "إيداع في الخزنة"
    await post(db, tid, "safe_movement", movement_id, "deposit", today(), [dr(safe, amount), cr(source, amount)],
               memo=memo + (f" — {note}" if note else ""), warehouse_id=wh, user_id=user_id)


async def on_safe_withdrawn(db: AsyncSession, *, movement_id, safe_id, amount, note=None, user_id=None, **_) -> None:
    tid = tenant_of()
    amount = Decimal(str(amount))
    safe = await chart.money_account(db, tid, "safe", safe_id)
    await post(db, tid, "safe_movement", movement_id, "withdraw", today(),
               [dr(await role(db, tid, "other_expenses"), amount), cr(safe, amount)],
               memo="سحب من الخزنة" + (f" — {note}" if note else ""), user_id=user_id)


async def on_wallet_to_safe(db: AsyncSession, *, movement_id, wallet_id, safe_id, amount, note=None,
                            user_id=None, **_) -> None:
    tid = tenant_of()
    amount = Decimal(str(amount))
    safe = await chart.money_account(db, tid, "safe", safe_id)
    wallet = await chart.money_account(db, tid, "wallet", wallet_id)
    await post(db, tid, "wallet_movement", movement_id, "transfer", today(), [dr(safe, amount), cr(wallet, amount)],
               memo="تحويل من المحفظة إلى الخزنة" + (f" — {note}" if note else ""), user_id=user_id)


async def on_wallet_reset(db: AsyncSession, *, movement_id, wallet_id, old_balance, user_id=None, **_) -> None:
    tid = tenant_of()
    old = Decimal(str(old_balance or 0))
    if not old:
        return
    wallet = await chart.money_account(db, tid, "wallet", wallet_id)
    if old > 0:
        lines = [dr(await role(db, tid, "other_expenses"), old), cr(wallet, old)]
    else:
        lines = [dr(wallet, -old), cr(await role(db, tid, "other_income"), -old)]
    await post(db, tid, "wallet_movement", movement_id, "reset", today(), lines, memo="تصفير رصيد المحفظة", user_id=user_id)
