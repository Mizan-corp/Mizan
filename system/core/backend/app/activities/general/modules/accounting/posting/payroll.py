"""Posting rules for payroll and HR advances (ADR-014 D3, step 3). Employees are the lines' parties.

Payroll approved (source 'payroll', id: the approval's salaries expense, event 'approve'), one entry
for the month from its payroll entries, dated today. Per employee: net = the entry's net salary;
withheld = gross - net (gross = base + overtime + bonus payment + bonus; never below zero);
recovered = the advances deducted (less what the month's pay couldn't cover and was carried to the
next month as an open advance, `advances_carried`, HR-9), up to what was withheld; the rest of the
withheld amount is deductions, lateness and absence. A carried advance stays in employee advances
and is recovered by the month that deducts it.
    Dr salaries expense                       (net + withheld, all employees)
    Cr salaries payable (party: employee)     (net)
    Cr employee advances (party: employee)    (advances recovered)
    Cr other income                           (deductions, lateness, absence)
Reopening an approved, unpaid month: the reversing entry of the approval ('payroll.reopened').
Payroll paid (source 'payroll', id: the period, event 'pay'): Dr salaries payable (party: employee,
their net) / Cr the safe or wallet it was paid from.
HR advance (سلفة) paid out (source 'hr_advance', event 'pay'): Dr employee advances (party: employee) /
Cr the safe or wallet; cancelling it ('hr_advance.cancelled') reverses that entry. Deductions (خصم) and bonuses (مكافأة) move no cash and post nothing by
themselves: they enter the ledger through payroll.
"""
import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.posting.common import role, source_account, tenant_of
from app.activities.general.modules.accounting.services.posting import cr, dr, post, reverse_source, today

CENT = Decimal("0.01")


def _d(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT)


def _uid(user_id):
    return uuid.UUID(str(user_id)) if user_id else None


async def _entries(db: AsyncSession, period_id) -> list:
    return (await db.execute(text("""
        SELECT employee_id, base_salary, overtime_pay, bonus_payment, bonus, advances, advances_carried, net_salary
        FROM hr_payroll_entries WHERE period_id = :p ORDER BY employee_id
    """), {"p": period_id})).all()


async def on_payroll_approved(db: AsyncSession, *, period_id, month, expense_id, user_id=None, **_) -> None:
    tid = tenant_of()
    salaries_payable = await role(db, tid, "salaries_payable")
    advances_account = await role(db, tid, "employee_advances")
    expense = total_other = Decimal("0")
    lines = []
    for e in await _entries(db, period_id):
        net = _d(e.net_salary)
        gross = _d(e.base_salary) + _d(e.overtime_pay) + _d(e.bonus_payment) + _d(e.bonus)
        withheld = max(Decimal("0"), gross - net)
        recovered = min(_d(e.advances) - _d(e.advances_carried), withheld)
        party = {"party_type": "employee", "party_id": e.employee_id}
        expense += net + withheld
        total_other += withheld - recovered
        if net > 0:
            lines.append(cr(salaries_payable, net, **party))
        if recovered > 0:
            lines.append(cr(advances_account, recovered, **party))
    if expense <= 0:
        return
    lines.insert(0, dr(await role(db, tid, "salaries_expense"), expense))
    if total_other > 0:
        lines.append(cr(await role(db, tid, "other_income"), total_other))
    await post(db, tid, "payroll", expense_id, "approve", today(), lines, memo=f"رواتب شهر {month}",
               user_id=_uid(user_id))


async def on_payroll_reopened(db: AsyncSession, *, month, expense_id, user_id=None, **_) -> None:
    await reverse_source(db, tenant_of(), "payroll", expense_id, "approve", user_id=_uid(user_id),
                         memo=f"إعادة فتح رواتب شهر {month}")


async def on_payroll_paid(db: AsyncSession, *, period_id, month, safe_id=None, wallet_id=None, user_id=None, **_) -> None:
    tid = tenant_of()
    salaries_payable = await role(db, tid, "salaries_payable")
    lines, total = [], Decimal("0")
    for e in await _entries(db, period_id):
        net = _d(e.net_salary)
        if net > 0:
            total += net
            lines.append(dr(salaries_payable, net, party_type="employee", party_id=e.employee_id))
    if total <= 0:
        return
    lines.append(cr(await source_account(db, tid, safe_id=safe_id, wallet_id=wallet_id), total))
    await post(db, tid, "payroll", period_id, "pay", today(), lines, memo=f"صرف رواتب شهر {month}",
               user_id=_uid(user_id))


async def on_hr_advance_paid(db: AsyncSession, *, advance_id, employee_id, amount, safe_id=None, wallet_id=None,
                             note=None, user_id=None, **_) -> None:
    amount = _d(amount)
    if amount <= 0:
        return
    tid = tenant_of()
    await post(db, tid, "hr_advance", advance_id, "pay", today(),
               [dr(await role(db, tid, "employee_advances"), amount, party_type="employee", party_id=employee_id),
                cr(await source_account(db, tid, safe_id=safe_id, wallet_id=wallet_id), amount)],
               memo="سلفة موظف" + (f" — {note}" if note else ""), user_id=_uid(user_id))


async def on_hr_advance_cancelled(db: AsyncSession, *, advance_id, user_id=None, **_) -> None:
    await reverse_source(db, tenant_of(), "hr_advance", advance_id, "pay", user_id=_uid(user_id),
                         memo="إلغاء سلفة موظف")
