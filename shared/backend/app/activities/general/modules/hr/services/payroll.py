"""Payroll service — business logic extracted from hr.py router."""
import asyncio
import json
from datetime import date
from decimal import Decimal
from functools import partial

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError
from app.activities.general.modules.hr.services.payroll_engine import calculate_payroll as calc_engine


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


async def get_period_status(db: AsyncSession, month: str) -> str | None:
    """Get status of a payroll period."""
    return (await db.execute(
        text("SELECT status FROM hr_payroll_periods WHERE month=:m"), {"m": month}
    )).scalar_one_or_none()


async def load_hr_settings(db: AsyncSession) -> dict:
    rows = await db.execute(text("SELECT key, value FROM hr_settings"))
    return {r[0]: r[1] for r in rows.fetchall()}


async def load_shifts_map(db: AsyncSession) -> dict:
    shifts_rows = await db.execute(
        text("SELECT id, name, start_time, end_time FROM hr_shifts")
    )
    return {
        r[0]: {"id": r[0], "name": r[1], "start_time": r[2], "end_time": r[3]}
        for r in shifts_rows.fetchall()
    }


async def load_active_employees(db: AsyncSession, employee_id: str | None = None) -> list[dict]:
    emp_q = """
        SELECT id, emp_code, name, position, monthly_salary, shift_schedule, shift_id,
               hire_date, ignore_lateness, max_lateness_before_overtime_cancellation
        FROM hr_employees WHERE is_active=TRUE
    """
    if employee_id:
        emp_q += " AND id=:eid"
        emps = await db.execute(text(emp_q), {"eid": employee_id})
    else:
        emps = await db.execute(text(emp_q))
    emp_cols = [
        "id", "emp_code", "name", "position", "monthly_salary", "shift_schedule",
        "shift_id", "hire_date", "ignore_lateness", "max_lateness_before_overtime_cancellation"
    ]
    return [dict(zip(emp_cols, r, strict=False)) for r in emps.fetchall()]


async def load_attendance_for_month(
    db: AsyncSession, employee_id: str, month: str
) -> list[dict]:
    att_rows = await db.execute(
        text("""
            SELECT check_in, check_out, status, edited, edited_by, edit_reason,
                   excuse_no_late, excuse_no_early, excuse_allow_overtime, shift_override
            FROM hr_attendance WHERE employee_id=:eid AND TO_CHAR(work_date,'YYYY-MM')=:month
        """),
        {"eid": employee_id, "month": month},
    )
    att_cols = [
        "check_in", "check_out", "status", "edited", "edited_by", "edit_reason",
        "excuse_no_late", "excuse_no_early", "excuse_allow_overtime", "shift_override"
    ]
    return [dict(zip(att_cols, r, strict=False)) for r in att_rows.fetchall()]


BONUS_TYPES = ("مكافأة", "bonus")
DEDUCTION_TYPES = ("خصم", "deduction")


def record_kind(record_type: str | None) -> str:
    """An HR money record is a bonus (مكافأة), a deduction (خصم) or, otherwise, an advance (سلفة)."""
    if record_type in BONUS_TYPES:
        return "bonus"
    if record_type in DEDUCTION_TYPES:
        return "deduction"
    return "advance"


async def load_hr_records_for_month(db: AsyncSession, employee_id: str, month: str) -> dict[str, float]:
    """The month's advances, deductions and bonuses, summed separately: advances and deductions
    lower the salary, bonuses raise it."""
    rows = (await db.execute(
        text("""
            SELECT record_type, COALESCE(SUM(amount),0) FROM hr_advances
            WHERE employee_id=:eid AND TO_CHAR(date,'YYYY-MM')=:month
            GROUP BY record_type
        """),
        {"eid": employee_id, "month": month},
    )).all()
    totals = {"advance": 0.0, "deduction": 0.0, "bonus": 0.0}
    for record_type, amount in rows:
        totals[record_kind(record_type)] += float(amount or 0)
    return totals


async def load_advances_for_month(
    db: AsyncSession, employee_id: str, month: str
) -> float:
    """The month's advances only (not deductions or bonuses)."""
    return (await load_hr_records_for_month(db, employee_id, month))["advance"]


async def calculate_employee_payroll(
    emp: dict,
    attendances: list[dict],
    settings: dict,
    shifts_map: dict,
    advance: float,
    month: str,
    bonus: float = 0,
    deduction: float = 0,
) -> dict:
    """Run payroll engine for a single employee."""
    return await asyncio.get_running_loop().run_in_executor(
        None,
        partial(calc_engine, emp, attendances, settings, shifts_map, bonus=bonus, deduction=deduction,
                advance=advance, month=month),
    )


async def save_payroll_entry(
    db: AsyncSession,
    period_id: str,
    employee_id: str,
    result: dict,
    current_user_id: str,
) -> None:
    """Upsert payroll entry for an employee in a period."""
    await db.execute(
        text("""
            INSERT INTO hr_payroll_entries (
                period_id, employee_id, base_salary, working_days, actual_working_days,
                absent_days, vacation_days, total_hours, lateness_minutes, early_leave_minutes,
                missing_scan_minutes, lateness_deduction, overtime_hours, overtime_pay,
                bonus_days, bonus_payment, bonuses, bonus, deductions, advances, drawer_variance, net_salary,
                hourly_rate, daily_breakdown, created_by, status
            ) VALUES (
                :pid, :eid, :base, :wd, :awd, :abd, :vd, :th, :lm, :elm, :msm, :ld, :oth, :otp,
                :bd, :bp, :bonus, :bonus, :ded, :adv, 0, :net, :hr, CAST(:db AS jsonb), :by, 'draft'
            )
            ON CONFLICT (period_id, employee_id) DO UPDATE SET
                working_days=EXCLUDED.working_days, actual_working_days=EXCLUDED.actual_working_days,
                absent_days=EXCLUDED.absent_days, total_hours=EXCLUDED.total_hours,
                lateness_minutes=EXCLUDED.lateness_minutes, lateness_deduction=EXCLUDED.lateness_deduction,
                overtime_hours=EXCLUDED.overtime_hours, overtime_pay=EXCLUDED.overtime_pay,
                bonus_days=EXCLUDED.bonus_days, bonus_payment=EXCLUDED.bonus_payment,
                bonuses=EXCLUDED.bonuses, bonus=EXCLUDED.bonus, deductions=EXCLUDED.deductions,
                advances=EXCLUDED.advances, net_salary=EXCLUDED.net_salary,
                hourly_rate=EXCLUDED.hourly_rate, daily_breakdown=EXCLUDED.daily_breakdown,
                status=EXCLUDED.status
        """),
        {
            "pid": period_id, "eid": employee_id, "base": result["base_salary"],
            "wd": result["working_days"], "awd": result["actual_working_days"],
            "abd": result["absent_days"], "vd": result["vacation_days"],
            "th": result["total_hours"], "lm": result["lateness_minutes"],
            "elm": result["early_leave_minutes"], "msm": result["missing_scan_minutes"],
            "ld": result["lateness_deduction"], "oth": result["overtime_hours"],
            "otp": result["overtime_pay"], "bd": result["bonus_days"],
            "bp": result["bonus_payment"], "bonus": result["bonus"],
            "ded": result["deductions"], "adv": result["advances"],
            "net": result["net_salary"], "hr": result["hourly_rate"],
            "db": json.dumps(result["daily_breakdown"], ensure_ascii=False),
            "by": current_user_id,
        },
    )


async def calculate_payroll_month(
    db: AsyncSession,
    month: str,
    current_user_id: str,
    employee_id: str | None = None,
) -> dict:
    """Calculate payroll for all (or one) employee(s) for a month."""
    # Check period status
    period_status = await get_period_status(db, month)
    if period_status == "paid":
        raise BusinessError("تم صرف رواتب هذا الشهر بالفعل — لا يمكن إعادة الحساب")
    if period_status == "approved":
        raise BusinessError("تم اعتماد رواتب هذا الشهر — لا يمكن إعادة الحساب إلا بعد إعادة فتح الشهر")

    period_id = await get_or_create_period(db, month)

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
        await save_payroll_entry(db, period_id, eid, result, current_user_id)

        results.append({
            "name": emp["name"], "net": result["net_salary"],
            "working_days": result["working_days"], "lateness_min": result["lateness_minutes"],
            "overtime_h": result["overtime_hours"]
        })

    await db.commit()
    return {"month": month, "employees": len(results), "total": sum(r["net"] for r in results), "detail": results}


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
    status = await get_period_status(db, month) or "draft"
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


async def _lock_period(db: AsyncSession, month: str) -> dict | None:
    row = (await db.execute(text("SELECT * FROM hr_payroll_periods WHERE month=:m FOR UPDATE"), {"m": month})).mappings().first()
    return dict(row) if row else None


async def approve_payroll_period(db: AsyncSession, month: str, current_user_id: str) -> float:
    """Approve the month's salaries: records them as an approved expense whose payment is still
    pending. No money moves here; paying the month (pay_payroll_period) moves it, once."""
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
    if expense_id is None and total > 0:
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
                "dt": date(int(month[:4]), int(month[5:7]), 1),
                "by": current_user_id,
                "notes": marker,
            },
        )).scalar_one()
    await db.execute(text("UPDATE hr_payroll_periods SET expense_id=:e WHERE month=:m"), {"e": expense_id, "m": month})

    await update_period_status(db, month, "approved", current_user_id)
    return float(total)


async def pay_payroll_period(db: AsyncSession, month: str, current_user_id: str, *,
                             safe_id=None, wallet_id=None) -> float:
    """Pay an approved month: the total net salaries leave the chosen safe or wallet, once,
    recorded against the payroll period (ADR-014 D4)."""
    from app.activities.general.modules.finance.services import payments

    period = await _lock_period(db, month)
    status = (period or {}).get("status") or "draft"
    if status == "paid":
        raise BusinessError("تم صرف رواتب هذا الشهر بالفعل")
    if status != "approved":
        raise BusinessError("لا يمكن صرف الشهر إلا بعد الاعتماد")
    total = await _payroll_total(db, month)
    if total > 0:
        payments.check_source(safe_id, wallet_id, "حدد الخزنة أو المحفظة التي تُصرف منها الرواتب")
        await payments.money_out(db, total, safe_id=safe_id, wallet_id=wallet_id, ref_type="payroll",
                                 ref_id=period["id"], note=f"صرف رواتب شهر {month}", user_id=current_user_id)
    else:
        safe_id = wallet_id = None
    await db.execute(text("""
        UPDATE hr_payroll_periods SET safe_id=:sid, wallet_id=:wid, paid_amount=:amt WHERE month=:m
    """), {"sid": safe_id, "wid": wallet_id, "amt": total, "m": month})
    if period.get("expense_id"):
        await db.execute(text("UPDATE expenses SET safe_id=:sid, wallet_id=:wid, amount=:amt WHERE id=:id"),
                         {"sid": safe_id, "wid": wallet_id, "amt": total, "id": period["expense_id"]})
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
    # The month's pending salaries expense (expenses approved before v81 are found by their marker).
    await db.execute(text("""
        UPDATE expenses SET status='cancelled', cancelled_at=now(), cancelled_by=:by,
            cancel_reason='إعادة فتح شهر الرواتب'
        WHERE status='approved' AND (id = :id OR (CAST(:id AS uuid) IS NULL AND notes = :marker))
    """), {"by": current_user_id or None, "id": period.get("expense_id"), "marker": f"HR payroll month {month}"})
    await db.execute(text("""
        UPDATE hr_payroll_periods SET status='draft', expense_id=NULL, approved_by=NULL, approved_at=NULL,
            updated_at=now()
        WHERE month=:m
    """), {"m": month})
    await db.execute(text("""
        UPDATE hr_payroll_entries SET status='draft'
        WHERE period_id = (SELECT id FROM hr_payroll_periods WHERE month=:m)
    """), {"m": month})
    await db.commit()


async def update_payroll_entry(
    db: AsyncSession,
    payroll_id: str,
    bonus: float,
    deductions: float,
    drawer_variance: float,
    status: str,
    notes: str,
) -> float:
    """Update manual adjustments on a payroll entry."""
    row = (await db.execute(
        text("""
            SELECT base_salary, lateness_deduction, overtime_pay, bonus_payment, advances
            FROM hr_payroll_entries WHERE id=:id
        """),
        {"id": payroll_id},
    )).mappings().fetchone()
    if not row:
        raise BusinessError("سجل الراتب غير موجود")

    base_salary = float(row["base_salary"] or 0)
    lateness_deduction = float(row["lateness_deduction"] or 0)
    overtime_pay = float(row["overtime_pay"] or 0)
    engine_bonus = float(row["bonus_payment"] or 0)
    advances = float(row["advances"] or 0)

    net_salary = (
        base_salary
        - lateness_deduction
        - float(deductions)
        - advances
        + overtime_pay
        + engine_bonus
        + float(bonus)
        + float(drawer_variance)
    )
    net_salary = max(0, round(net_salary, 2))

    await db.execute(
        text("""
            UPDATE hr_payroll_entries
            SET bonus=:bonus, deductions=:ded, drawer_variance=:var,
                net_salary=:net, status=:status, notes=:notes
            WHERE id=:id
        """),
        {
            "id": payroll_id,
            "bonus": bonus,
            "ded": deductions,
            "var": drawer_variance,
            "net": net_salary,
            "status": status,
            "notes": notes or "",
        },
    )
    await db.commit()
    return net_salary


async def get_daily_breakdown(db: AsyncSession, payroll_id: str) -> dict:
    """Get daily attendance breakdown for a payroll record."""
    r = await db.execute(
        text("SELECT pe.daily_breakdown, e.name FROM hr_payroll_entries pe JOIN hr_employees e ON pe.employee_id=e.id WHERE pe.id=:id"),
        {"id": payroll_id},
    )
    row = r.fetchone()
    if not row:
        raise BusinessError("سجل الراتب غير موجود")
    return {"employee": row[1], "breakdown": row[0]}
