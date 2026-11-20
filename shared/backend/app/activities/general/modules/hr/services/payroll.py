"""Payroll: the month's period (draft → review → approved → paid), its entries and the rules that
keep money consistent with the ledger.

- Every change to a month takes its period row FOR UPDATE first (calculate, entry edits, approve,
  pay, reopen), so a calculation or an edit can't race an approval.
- A month that is approved or paid is closed: its entries, attendance and HR records can't change
  until it is reopened (an approved month only; a paid one never).
- Paying pays exactly the approved total and leaves the approved expense as it was.
- Advances are deducted up to what the month pays (HR-9): what the net can't cover is carried to
  the next month as an open advance (`hr_advances.carried_from_period_id`), made when the month is
  approved and cancelled when it is reopened; the ledger recovers only what was deducted, so the
  employee's advance balance stays open for the rest.
"""
import asyncio
import json
from datetime import date
from decimal import Decimal
from functools import partial

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.framework.events import notify
from app.activities.general.modules.hr.services.payroll_engine import calculate_payroll as calc_engine
from app.activities.general.modules.hr.services.payroll_engine import effective_settings

LOCKED_STATUSES = ("approved", "paid")
EDITABLE_STATUSES = ("draft", "review")
CENT = Decimal("0.01")


def month_range(month: str) -> tuple[date, date]:
    """The first day of `month` ("YYYY-MM") and of the month after it."""
    year, mon = int(month[:4]), int(month[5:7])
    start = date(year, mon, 1)
    return start, (date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1))


def month_of(day: date) -> str:
    return day.strftime("%Y-%m")


def next_month(month: str) -> str:
    return month_of(month_range(month)[1])


async def get_or_create_period(db: AsyncSession, month: str) -> str:
    """The workspace's payroll period for `month` (created as a draft if missing)."""
    find = text("SELECT id FROM hr_payroll_periods WHERE month=:m")
    period_id = (await db.execute(find, {"m": month})).scalar_one_or_none()
    if period_id is None:
        # tenant_id comes from the session (app.tenant_id); (tenant_id, month) is unique.
        await db.execute(
            text("INSERT INTO hr_payroll_periods (month, status) VALUES (:m, 'draft') ON CONFLICT DO NOTHING"),
            {"m": month},
        )
        period_id = (await db.execute(find, {"m": month})).scalar_one()
    return period_id


async def get_period(db: AsyncSession, month: str) -> dict:
    """The month's period, read only: a month nobody has touched is a draft without an id."""
    row = (await db.execute(text("SELECT * FROM hr_payroll_periods WHERE month=:m"), {"m": month})).mappings().first()
    return dict(row) if row else {"id": None, "month": month, "status": "draft"}


async def get_period_status(db: AsyncSession, month: str) -> str | None:
    """Get status of a payroll period."""
    return (await db.execute(
        text("SELECT status FROM hr_payroll_periods WHERE month=:m"), {"m": month}
    )).scalar_one_or_none()


async def _lock_period(db: AsyncSession, month: str, *, create: bool = False) -> dict | None:
    if create:
        await get_or_create_period(db, month)
    row = (await db.execute(text("SELECT * FROM hr_payroll_periods WHERE month=:m FOR UPDATE"), {"m": month})).mappings().first()
    return dict(row) if row else None


async def ensure_month_open(db: AsyncSession, month: str, what: str = "سجلاته") -> None:
    """Refuse a change to a month whose payroll is approved or paid. The period row is locked FOR
    SHARE until the caller commits, so the month can't be approved in between."""
    status = (await db.execute(
        text("SELECT status FROM hr_payroll_periods WHERE month=:m FOR SHARE"), {"m": month}
    )).scalar_one_or_none()
    if status == "paid":
        raise ConflictError(f"تم صرف رواتب شهر {month} — لا يمكن تعديل {what}")
    if status == "approved":
        raise ConflictError(f"رواتب شهر {month} معتمدة — أعد فتح الشهر قبل تعديل {what}")


async def load_hr_settings(db: AsyncSession) -> dict:
    """The stored settings rows (key → text); the engine reads them through effective_settings."""
    rows = await db.execute(text("SELECT key, value FROM hr_settings"))
    return {r[0]: r[1] for r in rows.fetchall()}


async def hr_settings(db: AsyncSession) -> dict:
    """Every HR setting, typed, the defaults filled in (HR-12)."""
    return effective_settings(await load_hr_settings(db))


async def load_shifts_map(db: AsyncSession) -> dict:
    shifts_rows = await db.execute(
        text("SELECT id, name, start_time, end_time FROM hr_shifts")
    )
    return {
        r[0]: {"id": r[0], "name": r[1], "start_time": r[2], "end_time": r[3]}
        for r in shifts_rows.fetchall()
    }


EMPLOYEE_COLUMNS = (
    "id", "emp_code", "name", "position", "monthly_salary", "shift_schedule", "shift_id",
    "hire_date", "ignore_lateness", "max_lateness_before_overtime_cancellation",
)


async def load_active_employees(db: AsyncSession, employee_id=None) -> list[dict]:
    emp_q = f"SELECT {', '.join(EMPLOYEE_COLUMNS)} FROM hr_employees WHERE is_active=TRUE"
    params = {}
    if employee_id:
        emp_q += " AND id=:eid"
        params["eid"] = employee_id
    rows = await db.execute(text(emp_q + " ORDER BY name"), params)
    return [dict(r) for r in rows.mappings().all()]


ATTENDANCE_COLUMNS = (
    "work_date", "check_in", "check_out", "status", "edited", "edited_by", "edit_reason",
    "excuse_no_late", "excuse_no_early", "excuse_allow_overtime", "shift_override",
)


async def load_attendance_for_month(db: AsyncSession, employee_id, month: str) -> list[dict]:
    start, end = month_range(month)
    rows = await db.execute(
        text(f"""
            SELECT {', '.join(ATTENDANCE_COLUMNS)}
            FROM hr_attendance WHERE employee_id=:eid AND work_date >= :start AND work_date < :end
            ORDER BY work_date
        """),
        {"eid": employee_id, "start": start, "end": end},
    )
    return [dict(r) for r in rows.mappings().all()]


BONUS_TYPES = ("مكافأة", "bonus")
DEDUCTION_TYPES = ("خصم", "deduction")


def record_kind(record_type: str | None) -> str:
    """An HR money record is a bonus (مكافأة), a deduction (خصم) or, otherwise, an advance (سلفة)."""
    record_type = getattr(record_type, "value", record_type)
    if record_type in BONUS_TYPES:
        return "bonus"
    if record_type in DEDUCTION_TYPES:
        return "deduction"
    return "advance"


async def load_hr_records_for_month(db: AsyncSession, employee_id, month: str) -> dict[str, Decimal]:
    """The month's advances, deductions and bonuses (not cancelled ones), summed separately:
    advances and deductions lower the salary, bonuses raise it."""
    start, end = month_range(month)
    rows = (await db.execute(
        text("""
            SELECT record_type, COALESCE(SUM(amount),0) FROM hr_advances
            WHERE employee_id=:eid AND date >= :start AND date < :end AND status <> 'cancelled'
            GROUP BY record_type
        """),
        {"eid": employee_id, "start": start, "end": end},
    )).all()
    totals = {"advance": Decimal("0"), "deduction": Decimal("0"), "bonus": Decimal("0")}
    for record_type, amount in rows:
        totals[record_kind(record_type)] += Decimal(str(amount or 0))
    return totals


async def load_advances_for_month(db: AsyncSession, employee_id, month: str) -> Decimal:
    """The month's advances only (not deductions or bonuses)."""
    return (await load_hr_records_for_month(db, employee_id, month))["advance"]


async def calculate_employee_payroll(
    emp: dict,
    attendances: list[dict],
    settings: dict,
    shifts_map: dict,
    advance,
    month: str,
    bonus=0,
    deduction=0,
) -> dict:
    """Run payroll engine for a single employee."""
    return await asyncio.get_running_loop().run_in_executor(
        None,
        partial(calc_engine, emp, attendances, settings, shifts_map, bonus=bonus, deduction=deduction,
                advance=advance, month=month),
    )


def _d(value) -> Decimal:
    return Decimal(str(value or 0))


def settle(*, base_pay, lateness_deduction, deductions, advances, overtime_pay, bonus_payment, bonus,
           drawer_variance=0) -> tuple[Decimal, Decimal]:
    """(net, carried): the month's pay is the prorated base, less lateness and deductions, plus
    overtime, extra days and bonuses (and a drawer variance); the advances are deducted from it as
    far as it goes. The net never goes below zero, and the part of the advances it couldn't cover is
    carried to the next month (HR-9) instead of being dropped."""
    pay = (_d(base_pay) - _d(lateness_deduction) - _d(deductions) + _d(overtime_pay) + _d(bonus_payment)
           + _d(bonus) + _d(drawer_variance))
    advances = _d(advances)
    recovered = min(advances, max(Decimal("0"), pay))
    return max(Decimal("0"), (pay - advances).quantize(CENT)), (advances - recovered).quantize(CENT)


def compose_net(**parts) -> Decimal:
    """The net salary as the engine composes it (see settle), never below zero."""
    return settle(**parts)[0]


async def save_payroll_entry(
    db: AsyncSession,
    period_id,
    employee_id,
    result: dict,
    current_user_id: str,
) -> Decimal:
    """Upsert the employee's entry in the period from the engine's result and return its net. A
    recalculation keeps the entry's drawer variance and notes (the variance stays in the net)."""
    variance = (await db.execute(
        text("SELECT drawer_variance FROM hr_payroll_entries WHERE period_id=:p AND employee_id=:e"),
        {"p": period_id, "e": employee_id},
    )).scalar_one_or_none()
    net, carried = settle(base_pay=result["base_pay"], lateness_deduction=result["lateness_deduction"],
                          deductions=result["deductions"], advances=result["advances"],
                          overtime_pay=result["overtime_pay"], bonus_payment=result["bonus_payment"],
                          bonus=result["bonus"], drawer_variance=variance)
    await db.execute(
        text("""
            INSERT INTO hr_payroll_entries (
                period_id, employee_id, base_salary, base_pay, working_days, actual_working_days,
                absent_days, vacation_days, total_hours, lateness_minutes, early_leave_minutes,
                missing_scan_minutes, lateness_deduction, overtime_hours, overtime_pay,
                bonus_days, bonus_payment, bonuses, bonus, deductions, advances, advances_carried, drawer_variance,
                net_salary, hourly_rate, daily_breakdown, created_by, status
            ) VALUES (
                :pid, :eid, :base, :bpay, :wd, :awd, :abd, :vd, :th, :lm, :elm, :msm, :ld, :oth, :otp,
                :bd, :bp, :bonus, :bonus, :ded, :adv, :carried, 0, :net, :hr, CAST(:db AS jsonb), :by, 'draft'
            )
            ON CONFLICT (period_id, employee_id) DO UPDATE SET
                base_salary=EXCLUDED.base_salary, base_pay=EXCLUDED.base_pay,
                working_days=EXCLUDED.working_days, actual_working_days=EXCLUDED.actual_working_days,
                absent_days=EXCLUDED.absent_days, vacation_days=EXCLUDED.vacation_days,
                total_hours=EXCLUDED.total_hours, lateness_minutes=EXCLUDED.lateness_minutes,
                early_leave_minutes=EXCLUDED.early_leave_minutes, missing_scan_minutes=EXCLUDED.missing_scan_minutes,
                lateness_deduction=EXCLUDED.lateness_deduction,
                overtime_hours=EXCLUDED.overtime_hours, overtime_pay=EXCLUDED.overtime_pay,
                bonus_days=EXCLUDED.bonus_days, bonus_payment=EXCLUDED.bonus_payment,
                bonuses=EXCLUDED.bonuses, bonus=EXCLUDED.bonus, deductions=EXCLUDED.deductions,
                advances=EXCLUDED.advances, advances_carried=EXCLUDED.advances_carried, net_salary=EXCLUDED.net_salary,
                hourly_rate=EXCLUDED.hourly_rate, daily_breakdown=EXCLUDED.daily_breakdown,
                status=EXCLUDED.status
        """),
        {
            "pid": period_id, "eid": employee_id, "base": result["base_salary"], "bpay": result["base_pay"],
            "wd": result["working_days"], "awd": result["actual_working_days"],
            "abd": result["absent_days"], "vd": result["vacation_days"],
            "th": result["total_hours"], "lm": result["lateness_minutes"],
            "elm": result["early_leave_minutes"], "msm": result["missing_scan_minutes"],
            "ld": result["lateness_deduction"], "oth": result["overtime_hours"],
            "otp": result["overtime_pay"], "bd": result["bonus_days"],
            "bp": result["bonus_payment"], "bonus": result["bonus"],
            "ded": result["deductions"], "adv": result["advances"],
            "carried": carried, "net": net, "hr": result["hourly_rate"],
            "db": json.dumps(result["daily_breakdown"], ensure_ascii=False),
            "by": current_user_id,
        },
    )
    return net


async def calculate_payroll_month(
    db: AsyncSession,
    month: str,
    current_user_id: str,
    employee_id=None,
) -> dict:
    """Calculate payroll for all (or one) employee(s) for a month, with the period locked."""
    period = await _lock_period(db, month, create=True)
    period_status = period["status"]
    if period_status == "paid":
        raise BusinessError("تم صرف رواتب هذا الشهر بالفعل — لا يمكن إعادة الحساب")
    if period_status == "approved":
        raise BusinessError("تم اعتماد رواتب هذا الشهر — لا يمكن إعادة الحساب إلا بعد إعادة فتح الشهر")

    settings = await load_hr_settings(db)
    shifts_map = await load_shifts_map(db)
    employees = await load_active_employees(db, employee_id)

    results = []
    for emp in employees:
        eid = emp["id"]
        attendances = await load_attendance_for_month(db, eid, month)
        records = await load_hr_records_for_month(db, eid, month)

        result = await calculate_employee_payroll(emp, attendances, settings, shifts_map, records["advance"], month,
                                                  bonus=records["bonus"], deduction=records["deduction"])
        net = await save_payroll_entry(db, period["id"], eid, result, current_user_id)

        results.append({
            "name": emp["name"], "net": float(net),
            "working_days": result["working_days"], "lateness_min": result["lateness_minutes"],
            "overtime_h": result["overtime_hours"]
        })

    await db.commit()
    total = sum((Decimal(str(r["net"])) for r in results), Decimal("0"))
    return {"month": month, "employees": len(results), "total": float(total), "detail": results}


async def update_period_status(
    db: AsyncSession, month: str, new_status: str, current_user_id: str
) -> None:
    """Update period status and all related payroll entries."""
    prefix = "submitted" if new_status == "review" else new_status
    by_col = f"{prefix}_by"
    at_col = f"{prefix}_at"
    await db.execute(
        text(f"""
            INSERT INTO hr_payroll_periods (month, status, {by_col}, {at_col})
            VALUES (:m, '{new_status}', :by, now())
            ON CONFLICT (tenant_id, month) DO UPDATE SET status='{new_status}', {by_col}=:by, {at_col}=now(), updated_at=now()
        """),
        {"m": month, "by": current_user_id},
    )
    await db.execute(
        text("""
            UPDATE hr_payroll_entries SET status=:st
            WHERE period_id = (SELECT id FROM hr_payroll_periods WHERE month=:m)
        """),
        {"st": new_status, "m": month},
    )
    await db.commit()


async def submit_payroll_period(db: AsyncSession, month: str, current_user_id: str) -> None:
    period = await _lock_period(db, month)
    status = (period or {}).get("status") or "draft"
    if status != "draft":
        raise BusinessError("لا يمكن إرسال الشهر للمراجعة إلا من حالة مسودة")
    await update_period_status(db, month, "review", current_user_id)


async def _payroll_total(db: AsyncSession, month: str) -> Decimal:
    total = (await db.execute(
        text("""
            SELECT COALESCE(SUM(pe.net_salary),0)
            FROM hr_payroll_entries pe
            JOIN hr_payroll_periods p ON pe.period_id = p.id
            WHERE p.month = :m
        """),
        {"m": month},
    )).scalar()
    return Decimal(str(total or 0))


async def approve_payroll_period(db: AsyncSession, month: str, current_user_id: str) -> float:
    """Approve the month's salaries: records them as an approved expense whose payment is still
    pending, and keeps the approved total on the period. No money moves here; paying the month
    (pay_payroll_period) moves exactly that total, once."""
    period = await _lock_period(db, month)
    status = (period or {}).get("status") or "draft"
    if status != "review":
        raise BusinessError("لا يمكن اعتماد الشهر إلا بعد المراجعة")

    total = await _payroll_total(db, month)

    # Ensure expense category exists
    cat_id = (await db.execute(
        text("SELECT id FROM financial_categories WHERE name='رواتب' AND type='expense'")
    )).scalar_one_or_none()
    if not cat_id:
        cat_id = (await db.execute(
            text("INSERT INTO financial_categories (name, type, color) VALUES ('رواتب','expense','#dc2626') RETURNING id")
        )).scalar_one()

    # The month's salaries as one approved expense (payment_method 'payroll': paid from the payroll
    # screen, never through the expenses screen).
    marker = f"HR payroll month {month}"
    expense_id = (await db.execute(
        text("SELECT id FROM expenses WHERE notes=:n AND status <> 'cancelled' LIMIT 1"), {"n": marker}
    )).scalar_one_or_none()
    # A month whose nets are all zero still has something for the ledger when salaries were earned
    # (an advance recovered from them, an absence withheld): its expense (of 0) keys that entry.
    earned = total > 0 or bool(await db.scalar(text("""
        SELECT EXISTS (SELECT 1 FROM hr_payroll_entries
                       WHERE period_id = :p AND COALESCE(base_salary, 0) + COALESCE(overtime_pay, 0)
                             + COALESCE(bonus_payment, 0) + COALESCE(bonus, 0) > 0)
    """), {"p": period["id"]}))
    if expense_id is None and earned:
        expense_id = (await db.execute(
            text("""
                INSERT INTO expenses (category_id, amount, description, date, status, payment_method, created_by,
                                      approved_by, approved_at, notes)
                VALUES (:cid, :amt, :desc, :dt, 'approved', 'payroll', :by, :by, now(), :notes)
                RETURNING id
            """),
            {
                "cid": cat_id,
                "amt": total,
                "desc": f"رواتب شهر {month}",
                "dt": month_range(month)[0],
                "by": current_user_id,
                "notes": marker,
            },
        )).scalar_one()
    await db.execute(text("UPDATE hr_payroll_periods SET expense_id=:e, approved_amount=:t WHERE id=:p"),
                     {"e": expense_id, "t": total, "p": period["id"]})
    await _carry_advances(db, period["id"], month, current_user_id)

    # The ledger posts the month's salaries in this transaction, keyed by the expense of this approval
    # (a reopened month makes a new one, so each approval has its own entry; ADR-014 D3).
    if expense_id is not None:
        await notify("payroll.approved", db, period_id=period["id"], month=month, expense_id=expense_id,
                     user_id=current_user_id)
    await update_period_status(db, month, "approved", current_user_id)
    return float(total)


CARRIED_NOTE = "سلفة مرحّلة من رواتب شهر {month} (لم يغطها صافي الراتب)"


async def _carry_advances(db: AsyncSession, period_id, month: str, user_id) -> None:
    """The advances a month couldn't deduct become open advances of the next month (HR-9), dated its
    first day, linked to this period. No cash moves and nothing is posted: the ledger kept them in
    the employee's advances when this month recovered only the rest. The next month must be open."""
    rows = (await db.execute(text("""
        SELECT employee_id, advances_carried FROM hr_payroll_entries
        WHERE period_id = :p AND advances_carried > 0 ORDER BY employee_id
    """), {"p": period_id})).all()
    if not rows:
        return
    nxt = next_month(month)
    await ensure_month_open(db, nxt, "السلف المرحّلة إليه من الشهر السابق")
    for employee_id, amount in rows:
        advance_id = (await db.execute(text("""
            INSERT INTO hr_advances (employee_id, amount, date, note, created_by, record_type, status, carried_from_period_id)
            VALUES (:e, :a, :d, :note, :by, 'سلفة', 'active', :p) RETURNING id
        """), {"e": employee_id, "a": amount, "d": month_range(nxt)[0], "note": CARRIED_NOTE.format(month=month),
               "by": user_id, "p": period_id})).scalar_one()
        await db.execute(text("""
            INSERT INTO hr_audit_log (action_type, entity_type, entity_id, performed_by, reason, details)
            VALUES ('carry', 'advance', :e, :by, :reason, CAST(:det AS jsonb))
        """), {"e": str(employee_id), "by": user_id, "reason": CARRIED_NOTE.format(month=month),
               "det": json.dumps({"id": str(advance_id), "amount": str(amount), "from": month, "to": nxt})})


async def _cancel_carried(db: AsyncSession, period_id, month: str, user_id) -> None:
    """Reopening a month takes back the advances it carried to the next one (refused when that
    month is approved or paid: they were deducted there)."""
    if not await db.scalar(text("SELECT 1 FROM hr_advances WHERE carried_from_period_id = :p AND status <> 'cancelled' LIMIT 1"),
                           {"p": period_id}):
        return
    await ensure_month_open(db, next_month(month), "السلف المرحّلة إليه من الشهر السابق")
    await db.execute(text("""
        UPDATE hr_advances SET status='cancelled', cancelled_at=now(), cancelled_by=:by, cancel_reason=:reason, updated_at=now()
        WHERE carried_from_period_id = :p AND status <> 'cancelled'
    """), {"p": period_id, "by": user_id or None, "reason": f"إعادة فتح رواتب شهر {month}"})


async def pay_payroll_period(db: AsyncSession, month: str, current_user_id: str, *,
                             safe_id=None, wallet_id=None) -> float:
    """Pay an approved month: exactly the approved total leaves the chosen safe or wallet, once,
    recorded against the payroll period (ADR-014 D4). The approved expense keeps its amount."""
    from app.activities.general.modules.finance.services import payments

    period = await _lock_period(db, month)
    status = (period or {}).get("status") or "draft"
    if status == "paid":
        raise BusinessError("تم صرف رواتب هذا الشهر بالفعل")
    if status != "approved":
        raise BusinessError("لا يمكن صرف الشهر إلا بعد الاعتماد")
    approved = period.get("approved_amount")
    if approved is None and period.get("expense_id"):  # approved before v97
        approved = (await db.execute(text("SELECT amount FROM expenses WHERE id=:id"),
                                     {"id": period["expense_id"]})).scalar()
    entries_total = await _payroll_total(db, month)
    total = Decimal(str(approved)) if approved is not None else entries_total
    if entries_total != total:
        # The ledger pays each employee's approved net: entries that no longer add up to the
        # approved total were changed behind the approval.
        raise ConflictError("رواتب الشهر لا تطابق المبلغ المعتمد — أعد فتح الشهر واعتمده من جديد")
    if total > 0:
        payments.check_source(safe_id, wallet_id, "حدد الخزنة أو المحفظة التي تُصرف منها الرواتب")
        await payments.money_out(db, total, safe_id=safe_id, wallet_id=wallet_id, ref_type="payroll",
                                 ref_id=period["id"], note=f"صرف رواتب شهر {month}", user_id=current_user_id)
    else:
        safe_id = wallet_id = None
    await db.execute(text("""
        UPDATE hr_payroll_periods SET safe_id=:sid, wallet_id=:wid, paid_amount=:amt WHERE id=:p
    """), {"sid": safe_id, "wid": wallet_id, "amt": total, "p": period["id"]})
    if period.get("expense_id"):
        await db.execute(text("UPDATE expenses SET safe_id=:sid, wallet_id=:wid WHERE id=:id"),
                         {"sid": safe_id, "wid": wallet_id, "id": period["expense_id"]})
    if total > 0:
        await notify("payroll.paid", db, period_id=period["id"], month=month, safe_id=safe_id, wallet_id=wallet_id,
                     user_id=current_user_id)
    await update_period_status(db, month, "paid", current_user_id)
    return float(total)


async def reopen_payroll_period(db: AsyncSession, month: str, current_user_id: str | None = None) -> None:
    """Reopen a month for recalculation. A paid month can't be reopened (its money has left);
    reopening an approved month cancels its pending salaries expense."""
    period = await _lock_period(db, month)
    status = (period or {}).get("status")
    if status == "paid":
        raise BusinessError("لا يمكن إعادة فتح شهر تم صرفه")
    if period is None:
        return
    if status == "approved":
        await _cancel_carried(db, period["id"], month, current_user_id)
    # An approved (never paid) month's salaries entry in the ledger is reversed; the expense below
    # was never posted on its own (payroll is posted with payroll), so nothing is reversed twice.
    if status == "approved" and period.get("expense_id"):
        await notify("payroll.reopened", db, period_id=period["id"], month=month, expense_id=period["expense_id"],
                     user_id=current_user_id)
    # The month's pending salaries expense (expenses approved before v81 are found by their marker).
    await db.execute(text("""
        UPDATE expenses SET status='cancelled', cancelled_at=now(), cancelled_by=:by,
            cancel_reason='إعادة فتح شهر الرواتب'
        WHERE status='approved' AND (id = :id OR (CAST(:id AS uuid) IS NULL AND notes = :marker))
    """), {"by": current_user_id or None, "id": period.get("expense_id"), "marker": f"HR payroll month {month}"})
    await db.execute(text("""
        UPDATE hr_payroll_periods SET status='draft', expense_id=NULL, approved_amount=NULL, approved_by=NULL,
            approved_at=NULL, updated_at=now()
        WHERE id=:p
    """), {"p": period["id"]})
    await db.execute(text("UPDATE hr_payroll_entries SET status='draft' WHERE period_id=:p"), {"p": period["id"]})
    await db.commit()


async def update_payroll_entry(
    db: AsyncSession,
    payroll_id,
    bonus,
    deductions,
    drawer_variance,
    notes: str | None,
    current_user_id=None,
) -> float:
    """Set an entry's manual adjustments while its month is a draft or in review (the period
    locked). The net is composed again from the engine's prorated base, as calculate does."""
    period_id = (await db.execute(text("SELECT period_id FROM hr_payroll_entries WHERE id=:id"),
                                  {"id": payroll_id})).scalar_one_or_none()
    if period_id is None:
        raise NotFoundError("سجل الراتب غير موجود")
    period = (await db.execute(text("SELECT month, status FROM hr_payroll_periods WHERE id=:p FOR UPDATE"),
                               {"p": period_id})).mappings().one()
    if period["status"] not in EDITABLE_STATUSES:
        raise ConflictError(f"رواتب شهر {period['month']} معتمدة أو مصروفة — لا يمكن تعديلها إلا بعد إعادة فتح الشهر")
    row = (await db.execute(text("SELECT * FROM hr_payroll_entries WHERE id=:id FOR UPDATE"),
                            {"id": payroll_id})).mappings().one()

    base_pay = row["base_pay"]
    if base_pay is None:
        # Calculated before v97: the prorated base the stored net was composed from.
        base_pay = (_d(row["net_salary"]) - _d(row["drawer_variance"]) + _d(row["lateness_deduction"])
                    + _d(row["deductions"]) + _d(row["advances"]) - _d(row["overtime_pay"])
                    - _d(row["bonus_payment"]) - _d(row["bonus"]))
        base_pay = min(max(Decimal("0"), base_pay), _d(row["base_salary"]))
    net_salary, carried = settle(base_pay=base_pay, lateness_deduction=row["lateness_deduction"], deductions=deductions,
                                 advances=row["advances"], overtime_pay=row["overtime_pay"],
                                 bonus_payment=row["bonus_payment"], bonus=bonus, drawer_variance=drawer_variance)

    await db.execute(
        text("""
            UPDATE hr_payroll_entries
            SET bonus=:bonus, bonuses=:bonus, deductions=:ded, drawer_variance=:var, net_salary=:net,
                advances_carried=:carried, notes=:notes
            WHERE id=:id
        """),
        {"id": payroll_id, "bonus": bonus, "ded": deductions, "var": drawer_variance, "net": net_salary,
         "carried": carried, "notes": notes or ""},
    )
    await db.execute(text("""
        INSERT INTO hr_audit_log (action_type, entity_type, entity_id, performed_by, reason, details)
        VALUES ('update', 'payroll_entry', :id, :by, 'تعديل راتب', CAST(:det AS jsonb))
    """), {"id": str(payroll_id), "by": current_user_id, "det": json.dumps({
        "month": period["month"], "employee_id": str(row["employee_id"]),
        "bonus": {"from": str(row["bonus"]), "to": str(bonus)},
        "deductions": {"from": str(row["deductions"]), "to": str(deductions)},
        "drawer_variance": {"from": str(row["drawer_variance"]), "to": str(drawer_variance)},
        "net_salary": {"from": str(row["net_salary"]), "to": str(net_salary)}})})
    await db.commit()
    return float(net_salary)


async def get_daily_breakdown(db: AsyncSession, payroll_id) -> dict:
    """A payroll entry's days (the engine's daily breakdown) and how its net was composed."""
    row = (await db.execute(text("""
        SELECT pe.*, e.name AS employee, p.month, p.status AS period_status
        FROM hr_payroll_entries pe JOIN hr_employees e ON pe.employee_id = e.id
        JOIN hr_payroll_periods p ON p.id = pe.period_id
        WHERE pe.id = :id
    """), {"id": payroll_id})).mappings().first()
    if not row:
        raise NotFoundError("سجل الراتب غير موجود")
    money_keys = ("base_salary", "base_pay", "lateness_deduction", "overtime_pay", "bonus_payment", "bonus", "deductions",
                  "advances", "advances_carried", "drawer_variance", "net_salary", "hourly_rate")
    return {"employee": row["employee"], "month": row["month"], "period_status": row["period_status"],
            "breakdown": row["daily_breakdown"],
            "entry": {**{k: str(row[k]) if row[k] is not None else None for k in money_keys},
                      **{k: row[k] for k in ("working_days", "absent_days", "vacation_days", "lateness_minutes",
                                             "early_leave_minutes", "missing_scan_minutes", "bonus_days", "notes")},
                      "total_hours": str(row["total_hours"]) if row["total_hours"] is not None else None,
                      "overtime_hours": str(row["overtime_hours"]) if row["overtime_hours"] is not None else None}}
