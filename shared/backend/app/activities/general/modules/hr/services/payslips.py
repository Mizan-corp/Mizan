"""The payroll reports (the month's payroll, an employee's detailed report and payslip).

They show what the month's payroll holds: the stored hr_payroll_entries and their daily breakdown.
An approved or paid month is shown only from them (what was approved and paid, whatever attendance
or salaries say today). A month not calculated yet is previewed with the engine."""
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.hr.services import payroll as payroll_service
from app.activities.general.modules.hr.services.payroll_engine import parse_shift, setting_number
from app.activities.general.modules.hr.services.reports import Employee, ReportGenerator

KIND_LABEL = {"advance": "سلفة", "deduction": "خصم", "bonus": "مكافأة"}


def _f(value) -> float:
    return float(value or 0)


async def _stored_entries(db: AsyncSession, month: str, employee_id=None) -> list[dict]:
    cols = ", ".join(f"e.{c} AS emp_{c}" for c in payroll_service.EMPLOYEE_COLUMNS)
    q = f"""
        SELECT pe.*, {cols}
        FROM hr_payroll_entries pe
        JOIN hr_payroll_periods p ON pe.period_id = p.id
        JOIN hr_employees e ON pe.employee_id = e.id
        WHERE p.month = :m
    """
    params = {"m": month}
    if employee_id is not None:
        q += " AND pe.employee_id = :eid"
        params["eid"] = employee_id
    rows = (await db.execute(text(q + " ORDER BY e.name"), params)).mappings().all()
    out = []
    for r in rows:
        r = dict(r)
        emp = {c: r.pop(f"emp_{c}") for c in payroll_service.EMPLOYEE_COLUMNS}
        out.append({"emp": emp, "entry": r})
    return out


def _from_entry(entry: dict) -> dict:
    """A stored entry in the engine's result shape."""
    base_pay = entry.get("base_pay")
    if base_pay is None:  # calculated before v97: what the stored net was composed from
        base_pay = (_f(entry["net_salary"]) - _f(entry.get("drawer_variance")) + _f(entry["lateness_deduction"])
                    + _f(entry["deductions"]) + _f(entry["advances"]) - _f(entry["overtime_pay"])
                    - _f(entry["bonus_payment"]) - _f(entry["bonus"]))
    return {
        "base_salary": _f(entry["base_salary"]), "base_pay": _f(base_pay), "hourly_rate": _f(entry["hourly_rate"]),
        "working_days": int(entry["working_days"] or 0), "actual_working_days": int(entry["actual_working_days"] or 0),
        "vacation_days": int(entry["vacation_days"] or 0), "absent_days": int(entry["absent_days"] or 0),
        "total_hours": _f(entry["total_hours"]), "lateness_minutes": int(entry["lateness_minutes"] or 0),
        "early_leave_minutes": int(entry["early_leave_minutes"] or 0),
        "missing_scan_minutes": int(entry["missing_scan_minutes"] or 0),
        "lateness_deduction": _f(entry["lateness_deduction"]), "overtime_hours": _f(entry["overtime_hours"]),
        "overtime_pay": _f(entry["overtime_pay"]), "bonus_days": int(entry["bonus_days"] or 0),
        "bonus_payment": _f(entry["bonus_payment"]), "bonus": _f(entry["bonus"]),
        "deductions": _f(entry["deductions"]), "advances": _f(entry["advances"]),
        "drawer_variance": _f(entry.get("drawer_variance")), "net_salary": _f(entry["net_salary"]),
        "daily_breakdown": entry.get("daily_breakdown") or [],
    }


def _report_fields(result: dict, emp: dict, settings: dict, shifts_map: dict, month: str) -> dict:
    """The fields the report templates read, from an engine result or a stored entry."""
    days = max(1, int(setting_number(settings, "days_in_month", 26)))
    start_h, end_h = parse_shift(emp.get("shift_schedule") or "", shifts_map)
    shift_length = (end_h - start_h) if end_h > start_h else (24 - start_h + end_h)
    out = dict(result)
    out.update({
        "emp_id": str(emp.get("emp_code") or emp["id"]), "emp_name": emp["name"], "position": emp.get("position") or "",
        "month": month, "final_salary": result["net_salary"], "overtime_payment": result["overtime_pay"],
        "deduction": result.get("deductions", 0), "advance": result.get("advances", 0),
        "scheduled_month_hours": days * shift_length, "effective_days_in_month": days, "days_in_month": days,
        "shift_length": shift_length,
        "normal_hours_worked": max(0.0, result.get("total_hours", 0) - result.get("overtime_hours", 0)),
        "late_penalty_multiplier": setting_number(settings, "late_penalty_multiplier", 2.0), "penalty_hours": 0,
        "base_pay_prorated": result.get("base_pay", 0), "ignore_lateness": bool(emp.get("ignore_lateness")),
        "daily": result.get("daily_breakdown") or [],
    })
    return out


async def _live(db: AsyncSession, emp: dict, settings: dict, shifts_map: dict, month: str) -> dict:
    attendances = await payroll_service.load_attendance_for_month(db, emp["id"], month)
    records = await payroll_service.load_hr_records_for_month(db, emp["id"], month)
    return await payroll_service.calculate_employee_payroll(
        emp, attendances, settings, shifts_map, records["advance"], month, bonus=records["bonus"],
        deduction=records["deduction"])


async def monthly_report(db: AsyncSession, month: str) -> str:
    status = await payroll_service.get_period_status(db, month)
    settings = await payroll_service.load_hr_settings(db)
    shifts_map = await payroll_service.load_shifts_map(db)
    stored = await _stored_entries(db, month)
    if stored or status in payroll_service.LOCKED_STATUSES:
        payrolls = [_report_fields(_from_entry(s["entry"]), s["emp"], settings, shifts_map, month) for s in stored]
    else:
        payrolls = [_report_fields(await _live(db, emp, settings, shifts_map, month), emp, settings, shifts_map, month)
                    for emp in await payroll_service.load_active_employees(db)]
    return ReportGenerator.generate_payroll_report(payrolls, month)


async def employee_report(db: AsyncSession, emp_id, month: str, report_type: str = "detailed") -> str:
    status = await payroll_service.get_period_status(db, month)
    settings = await payroll_service.load_hr_settings(db)
    shifts_map = await payroll_service.load_shifts_map(db)
    stored = await _stored_entries(db, month, emp_id)
    if stored:
        emp, result = stored[0]["emp"], _from_entry(stored[0]["entry"])
    else:
        emp = (await db.execute(text(
            f"SELECT {', '.join(payroll_service.EMPLOYEE_COLUMNS)} FROM hr_employees WHERE id=:id"),
            {"id": emp_id})).mappings().first()
        if not emp:
            raise HTTPException(404, "الموظف غير موجود")
        if status in payroll_service.LOCKED_STATUSES:
            raise HTTPException(404, f"لا يوجد راتب لهذا الموظف في شهر {month}")
        emp = dict(emp)
        result = await _live(db, emp, settings, shifts_map, month)
    payroll = _report_fields(result, emp, settings, shifts_map, month)

    start, end = payroll_service.month_range(month)
    adv_rows = (await db.execute(text("""
        SELECT amount, date, note, record_type FROM hr_advances
        WHERE employee_id=:eid AND date >= :start AND date < :end AND status <> 'cancelled' ORDER BY date
    """), {"eid": emp["id"], "start": start, "end": end})).all()
    finances = [{"type": KIND_LABEL[payroll_service.record_kind(r[3])], "amount": float(r[0]), "date": str(r[1]),
                 "note": r[2] or ""} for r in adv_rows]

    employee_obj = Employee(
        emp_id=str(emp["emp_code"] or emp["id"]), name=emp["name"], position=emp.get("position") or "",
        monthly_salary=float(payroll["base_salary"]), shift=emp.get("shift_schedule") or "",
        hire_date=str(emp["hire_date"]) if emp.get("hire_date") else None,
        ignore_lateness=bool(emp.get("ignore_lateness")),
    )
    if report_type == "ticket":
        return ReportGenerator.generate_payslip_ticket(employee_obj, payroll, finances=finances)
    # The days come from the payroll's daily breakdown (payroll["daily"]).
    return ReportGenerator.generate_employee_report(employee_obj, [], payroll, finances=finances)


async def attendance_report(db: AsyncSession, month: str) -> str:
    start, end = payroll_service.month_range(month)
    rows = (await db.execute(text("""
        SELECT e.name, e.emp_code, a.work_date, a.check_in, a.check_out, a.status, a.edited, a.edit_reason
        FROM hr_attendance a JOIN hr_employees e ON a.employee_id=e.id
        WHERE a.work_date >= :start AND a.work_date < :end
        ORDER BY e.name, a.work_date
    """), {"start": start, "end": end})).fetchall()

    report_rows = []
    for r in rows:
        ci = r[3].replace(tzinfo=None) if r[3] else None
        co = r[4].replace(tzinfo=None) if r[4] else None
        report_rows.append({
            "name": r[0], "uid": r[1] or "", "date": str(r[2]),
            "checkin": ci.isoformat() if ci else None, "checkout": co.isoformat() if co else None,
            "status": r[5] or "present", "edited": bool(r[6]), "edit_reason": r[7] or "",
        })
    return ReportGenerator.generate_attendance_report(report_rows, month)
