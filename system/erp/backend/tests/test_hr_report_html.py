"""PLAT-5: the HR report HTML escapes every text users typed (names, codes, positions, notes,
statuses, times, the month)."""


# ── PLAT-5: report HTML escapes every text ───────────────────────────────────────────────

def test_report_html_escapes_what_users_typed():
    from app.activities.general.modules.hr.services.reports import Employee, ReportGenerator

    x = '<img src=x onerror=alert(1)>'
    payroll = {
        "emp_id": x, "emp_name": x, "position": x, "month": x, "base_salary": 1000.0, "working_days": 1,
        "actual_working_days": 1, "vacation_days": 0, "lateness_minutes": 0, "early_leave_minutes": 0,
        "missing_scan_minutes": 0, "lateness_deduction": 0.0, "advance": 0.0, "overtime_hours": 0.0,
        "overtime_payment": 0.0, "bonus_payment": 0.0, "bonus": 0.0, "deduction": 0.0, "final_salary": 100.0,
        "hourly_rate": 1.0, "scheduled_month_hours": 208, "shift_length": 8, "bonus_days": 0,
        "daily": [{"date": "2025-02-03", "status": x, "check_in": x, "check_out": None, "work_hours": 1,
                   "late_minutes": 0, "early_minutes": 0, "overtime_hours": 0, "note": x}],
    }
    employee = Employee(x, x, x, 1000.0, x)
    finances = [{"type": t, "amount": 5.0, "date": x, "note": x} for t in ("سلفة", "خصم", "مكافأة")]
    pages = [
        ReportGenerator.generate_payroll_report([payroll], x),
        ReportGenerator.generate_employee_report(employee, [], payroll, finances=finances),
        ReportGenerator.generate_payslip_ticket(employee, payroll, finances=finances),
        ReportGenerator.generate_attendance_report(
            [{"name": x, "uid": x, "date": x, "checkin": x, "checkout": x, "status": x, "edited": True,
              "edit_reason": x}], x),
    ]
    for page in pages:
        assert "<img" not in page
