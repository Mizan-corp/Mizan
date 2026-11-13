"""HR / Payroll router"""
import asyncio
import json
import uuid
from datetime import date
from functools import partial

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.base import get_db
from app.dependencies import get_print_user, get_current_user, require_perm
from app.platform.auth.models.user import User
from app.activities.general.modules.hr.schemas import (
    AdvanceCreate,
    AttendanceCreate,
    EmployeeCreate,
    EmployeeUpdate,
    HRSettingsUpdate,
    PayrollCalculate,
    PayrollUpdate,
    ShiftCreate,
)
from app.activities.general.modules.hr.services import employees as employees_service
from app.activities.general.modules.hr.services import attendance as hr_attendance_service
from app.activities.general.modules.hr.services import payroll as payroll_service

router = APIRouter(prefix="/hr", tags=["hr"])


@router.get("/audit-log")
async def get_audit_log(db: AsyncSession = Depends(get_db), _=Depends(require_perm("payroll"))):
    r = await db.execute(text("""
        SELECT a.id, a.action_type, a.entity_type, a.entity_id, a.reason, a.details, a.created_at,
               u.full_name as performed_by_name
        FROM hr_audit_log a LEFT JOIN users u ON a.performed_by=u.id
        ORDER BY a.created_at DESC LIMIT 500
    """))
    cols = ['id','action_type','entity_type','entity_id','reason','details','created_at','performed_by_name']
    rows = r.fetchall()
    result = []
    for row in rows:
        d = dict(zip(cols, row, strict=False))
        d['created_at'] = d['created_at'].isoformat() if d['created_at'] else None
        result.append(d)
    return result


@router.get("/shifts")
async def list_shifts(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    r = await db.execute(text("SELECT * FROM hr_shifts ORDER BY start_time"))
    cols = r.keys()
    return [dict(zip(cols, row, strict=False)) for row in r.fetchall()]


@router.post("/shifts")
async def create_shift(data: ShiftCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("payroll"))):
    sid = str(int(uuid.uuid4().int % 10**10))
    await db.execute(text("INSERT INTO hr_shifts (id, name, start_time, end_time, description) VALUES (:id,:name,:st,:et,:desc)"),
                     {'id': sid, 'name': data.name, 'st': data.start_time, 'et': data.end_time, 'desc': data.description})
    await db.commit()
    return {'id': sid, 'name': data.name}


@router.get("/settings")
async def get_hr_settings(db: AsyncSession = Depends(get_db), _=Depends(require_perm("payroll"))):
    r = await db.execute(text("SELECT key, value FROM hr_settings"))
    return {row[0]: row[1] for row in r.fetchall()}


@router.put("/settings")
async def update_hr_settings(data: HRSettingsUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("payroll"))):
    for k, v in data.settings.items():
        await db.execute(text("INSERT INTO hr_settings (key, value) VALUES (:k,:v) ON CONFLICT (tenant_id, key) DO UPDATE SET value=EXCLUDED.value"),
                         {'k': k, 'v': str(v)})
    await db.commit()
    return {"detail": "saved"}


# ── Employees ─────────────────────────────────────────────────────────────
@router.get("/employees")
async def list_employees(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    r = await db.execute(text("SELECT * FROM hr_employees WHERE is_active=TRUE ORDER BY name"))
    cols = r.keys()
    return [dict(zip(cols, row, strict=False)) for row in r.fetchall()]


@router.post("/employees")
async def create_employee(data: EmployeeCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("payroll"))):
    r = await db.execute(text("""
        INSERT INTO hr_employees (emp_code, user_id, name, position, monthly_salary, shift_schedule, hire_date)
        VALUES (:code, :uid, :name, :pos, :sal, :shift, :hire) RETURNING *
    """), {'code': data.emp_code, 'uid': data.user_id, 'name': data.name, 'pos': data.position or '',
           'sal': data.monthly_salary, 'shift': data.shift_schedule or '',
           'hire': data.hire_date})
    await db.commit()
    row = r.fetchone()
    return dict(zip(r.keys(), row, strict=False))


@router.put("/employees/{emp_id}")
async def update_employee(emp_id: uuid.UUID, data: EmployeeUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("payroll"))):
    if not await employees_service.update_employee(db, emp_id, data.model_dump(exclude_unset=True), current_user):
        return {"detail": "no changes"}
    await db.commit()
    return {"detail": "updated"}


@router.delete("/employees/{emp_id}", status_code=204)
async def delete_employee(emp_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("payroll"))):
    result = await db.execute(text("UPDATE hr_employees SET is_active=FALSE WHERE id=:id"), {'id': emp_id})
    if result.rowcount == 0:
        raise HTTPException(404, "Employee not found")
    await db.commit()


# ── Attendance ─────────────────────────────────────────────────────────────
@router.get("/attendance")
async def list_attendance(employee_id: str | None = None, month: str | None = None,
                          db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    q = "SELECT a.*, e.name as emp_name FROM hr_attendance a JOIN hr_employees e ON a.employee_id=e.id WHERE 1=1"
    params = {}
    if employee_id:
        q += " AND a.employee_id=:eid"
        params['eid'] = uuid.UUID(employee_id)
    if month:
        q += " AND TO_CHAR(a.work_date,'YYYY-MM')=:month"
        params['month'] = month
    q += " ORDER BY a.work_date DESC"
    r = await db.execute(text(q), params)
    cols = r.keys()
    return [dict(zip(cols, row, strict=False)) for row in r.fetchall()]


@router.post("/attendance")
async def add_attendance(data: AttendanceCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm("payroll"))):
    await employees_service.save_attendance(db, data.employee_id, data.work_date, data.check_in, data.check_out,
                                            data.status, data.notes)
    await db.commit()
    return {"detail": "saved"}


@router.post("/attendance/import-csv")
async def import_attendance_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("payroll")),
):
    content = await file.read()
    return await hr_attendance_service.import_attendance_csv_stream(db, content)


# ── Payroll ────────────────────────────────────────────────────────────────
@router.get("/payroll")
async def list_payroll(month: str | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    q = """
        SELECT pe.*, e.name as emp_name, e.position, p.month as period_month, p.status as period_status
        FROM hr_payroll_entries pe
        JOIN hr_payroll_periods p ON pe.period_id = p.id
        JOIN hr_employees e ON pe.employee_id = e.id
        WHERE 1=1
    """
    params = {}
    if month:
        q += " AND p.month=:month"
        params['month'] = month
    q += " ORDER BY e.name"
    r = await db.execute(text(q), params)
    cols = r.keys()
    return [dict(zip(cols, row, strict=False)) for row in r.fetchall()]


@router.post("/payroll/calculate")
async def calculate_payroll(
    data: PayrollCalculate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("payroll")),
):
    """Calculate payroll for all (or one) employee using the full engine."""
    return await payroll_service.calculate_payroll_month(
        db,
        month=data.month,
        current_user_id=str(current_user.id),
        employee_id=data.employee_id,
    )


@router.get("/payroll/period")
async def get_payroll_period(month: str, db: AsyncSession = Depends(get_db), _=Depends(require_perm("payroll"))):
    row = (await db.execute(text("SELECT * FROM hr_payroll_periods WHERE month=:m"), {"m": month})).mappings().fetchone()
    if not row:
        await db.execute(text("INSERT INTO hr_payroll_periods (month, status) VALUES (:m, 'draft') ON CONFLICT DO NOTHING"), {"m": month})
        await db.commit()
        row = (await db.execute(text("SELECT * FROM hr_payroll_periods WHERE month=:m"), {"m": month})).mappings().fetchone()
    return dict(row)


@router.post("/payroll/period/submit")
async def submit_payroll_period(
    month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("payroll")),
):
    await payroll_service.submit_payroll_period(db, month, str(current_user.id))
    return {"detail": "submitted"}


@router.post("/payroll/period/approve")
async def approve_payroll_period(
    month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("payroll")),
):
    total = await payroll_service.approve_payroll_period(db, month, str(current_user.id))
    return {"detail": "approved", "total": float(total)}


@router.post("/payroll/period/pay")
async def pay_payroll_period(
    month: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm("payroll")),
):
    await payroll_service.pay_payroll_period(db, month, str(current_user.id))
    return {"detail": "paid"}


@router.post("/payroll/period/reopen")
async def reopen_payroll_period(
    month: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_perm("payroll")),
):
    await payroll_service.reopen_payroll_period(db, month)
    return {"detail": "reopened"}


@router.get("/payroll/{payroll_id}/breakdown")
async def get_daily_breakdown(payroll_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """Get daily attendance breakdown for a payroll record."""
    r = await db.execute(text("SELECT pe.daily_breakdown, e.name FROM hr_payroll_entries pe JOIN hr_employees e ON pe.employee_id=e.id WHERE pe.id=:id"), {'id': payroll_id})
    row = r.fetchone()
    if not row:
        raise NotFoundError()
    return {'employee': row[1], 'breakdown': row[0]}


@router.put("/payroll/{payroll_id}")
async def update_payroll(
    payroll_id: uuid.UUID,
    data: PayrollUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_perm("payroll")),
):
    """Update manual adjustments on a payroll entry."""
    net_salary = await payroll_service.update_payroll_entry(
        db,
        payroll_id=str(payroll_id),
        bonus=float(data.bonus),
        deductions=float(data.deductions),
        drawer_variance=float(data.drawer_variance),
        status=data.status,
        notes=data.notes or "",
    )
    return {"detail": "updated", "net_salary": net_salary}


# ── Advances ───────────────────────────────────────────────────────────────
@router.get("/advances")
async def list_advances(employee_id: str | None = None, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    q = "SELECT a.*, e.name as emp_name FROM hr_advances a JOIN hr_employees e ON a.employee_id=e.id WHERE 1=1"
    params = {}
    if employee_id:
        q += " AND a.employee_id=:eid"
        params['eid'] = uuid.UUID(employee_id)
    q += " ORDER BY a.date DESC"
    r = await db.execute(text(q), params)
    cols = r.keys()
    return [dict(zip(cols, row, strict=False)) for row in r.fetchall()]


@router.post("/advances")
async def add_advance(data: AdvanceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm("payroll"))):
    record_type = data.record_type
    adv_date = data.date or date.today()
    await db.execute(text("""
        INSERT INTO hr_advances (employee_id, amount, date, note, created_by, record_type)
        VALUES (:eid, :amt, :dt, :note, :by, :rt)
    """), {'eid': data.employee_id, 'amt': data.amount,
           'dt': adv_date, 'note': data.note or '',
           'by': current_user.id, 'rt': record_type})
    await db.execute(text("""
        INSERT INTO hr_audit_log (action_type, entity_type, entity_id, performed_by, reason, details)
        VALUES ('create', 'advance', :eid, :by, :note, CAST(:det AS jsonb))
    """), {'eid': str(data.employee_id), 'by': current_user.id,
           'note': data.note or '', 'det': json.dumps({"type": record_type, "amount": float(data.amount)})})
    await db.commit()
    return {"detail": "saved"}


async def _report_auth(user=Depends(get_print_user)):
    """Payroll and attendance reports open in a browser tab with a print token: the workspace is
    bound from it, and they need the payroll permission (they used to accept any token, bind no
    workspace and check nothing)."""
    from app.platform.permissions.access import can

    if not can(user, "payroll"):
        raise HTTPException(403, "Insufficient permissions")
    return user


@router.get("/payroll/report/monthly")
async def payroll_monthly_report(month: str, db: AsyncSession = Depends(get_db), _=Depends(_report_auth)):
    """Generate HTML payroll report for all employees — matches Qt ReportGenerator.generate_payroll_report()"""
    from app.activities.general.modules.hr.services.reports import ReportGenerator
    from app.activities.general.modules.hr.services.payroll_engine import calculate_payroll

    settings = {r[0]: r[1] for r in (await db.execute(text("SELECT key, value FROM hr_settings"))).fetchall()}
    shifts_map = {r[0]: {'id': r[0], 'name': r[1], 'start_time': r[2], 'end_time': r[3]}
                  for r in (await db.execute(text("SELECT id, name, start_time, end_time FROM hr_shifts"))).fetchall()}

    emps = (await db.execute(text("""
        SELECT id,emp_code,name,position,monthly_salary,shift_schedule,shift_id,hire_date,
               ignore_lateness,max_lateness_before_overtime_cancellation FROM hr_employees WHERE is_active=TRUE
    """))).fetchall()
    emp_cols = ['id','emp_code','name','position','monthly_salary','shift_schedule','shift_id','hire_date','ignore_lateness','max_lateness_before_overtime_cancellation']

    payrolls = []
    for emp_row in emps:
        emp = dict(zip(emp_cols, emp_row, strict=False))
        att_rows = (await db.execute(text("""
            SELECT check_in,check_out,status,edited,edited_by,edit_reason,
                   excuse_no_late,excuse_no_early,excuse_allow_overtime,shift_override
            FROM hr_attendance WHERE employee_id=:eid AND TO_CHAR(work_date,'YYYY-MM')=:month
        """), {'eid': emp['id'], 'month': month})).fetchall()
        att_cols = ['check_in','check_out','status','edited','edited_by','edit_reason','excuse_no_late','excuse_no_early','excuse_allow_overtime','shift_override']
        attendances = [dict(zip(att_cols, r, strict=False)) for r in att_rows]
        adv = float((await db.execute(text("SELECT COALESCE(SUM(amount),0) FROM hr_advances WHERE employee_id=:eid AND TO_CHAR(date,'YYYY-MM')=:month"), {'eid': emp['id'], 'month': month})).scalar() or 0)
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            partial(calculate_payroll, emp, attendances, settings, shifts_map, advance=adv, month=month),
        )
        result['emp_id'] = str(emp.get('emp_code') or emp['id'])
        result['emp_name'] = emp['name']
        result['position'] = emp['position']
        result['base_salary'] = float(emp['monthly_salary'])
        result['month'] = month
        # Map field names to Qt format
        result['final_salary'] = result['net_salary']
        result['overtime_payment'] = result['overtime_pay']
        result['bonus_payment'] = result.get('bonus_payment', 0)
        result['deduction'] = result.get('deductions', 0)
        result['advance'] = result.get('advances', 0)
        # Qt ReportGenerator required fields
        days = 26
        result.get('total_hours', 0) / max(result.get('working_days', 1), 1)
        result['scheduled_month_hours'] = days * 12  # default 12h shift
        result['effective_days_in_month'] = days
        result['days_in_month'] = days
        result['shift_length'] = 12
        result['hourly_rate'] = result.get('hourly_rate', 0)
        result['actual_working_days'] = result.get('actual_working_days', result.get('working_days', 0))
        result['vacation_days'] = result.get('vacation_days', 0)
        result['normal_hours_worked'] = result.get('total_hours', 0) - result.get('overtime_hours', 0)
        result['lateness_deduction'] = result.get('lateness_deduction', 0)
        result['late_penalty_multiplier'] = 2.0
        result['early_leave_minutes'] = result.get('early_leave_minutes', 0)
        result['missing_scan_minutes'] = result.get('missing_scan_minutes', 0)
        result['penalty_hours'] = 0
        result['bonus_days'] = result.get('bonus_days', 0)
        result['base_pay_prorated'] = result['net_salary'] + result.get('advances', 0) + result.get('lateness_deduction', 0) - result.get('overtime_pay', 0)
        result['ignore_lateness'] = bool(emp.get('ignore_lateness', False))
        payrolls.append(result)

    html = ReportGenerator.generate_payroll_report(payrolls, month)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


@router.get("/payroll/report/employee/{emp_id}")
async def employee_report(emp_id: uuid.UUID, month: str, report_type: str = 'detailed',
                          db: AsyncSession = Depends(get_db), _=Depends(_report_auth)):
    """Generate individual employee HTML report — matches Qt generate_employee_report() and generate_payslip_ticket()"""
    from app.activities.general.modules.hr.services.reports import Attendance, Employee, ReportGenerator
    from app.activities.general.modules.hr.services.payroll_engine import calculate_payroll

    settings = {r[0]: r[1] for r in (await db.execute(text("SELECT key, value FROM hr_settings"))).fetchall()}
    shifts_map = {r[0]: {'id': r[0], 'name': r[1], 'start_time': r[2], 'end_time': r[3]}
                  for r in (await db.execute(text("SELECT id, name, start_time, end_time FROM hr_shifts"))).fetchall()}

    emp_row = (await db.execute(text("""
        SELECT id,emp_code,name,position,monthly_salary,shift_schedule,shift_id,hire_date,
               ignore_lateness,max_lateness_before_overtime_cancellation FROM hr_employees WHERE id=:id
    """), {'id': emp_id})).fetchone()
    if not emp_row:
        raise NotFoundError()
    emp_cols = ['id','emp_code','name','position','monthly_salary','shift_schedule','shift_id','hire_date','ignore_lateness','max_lateness_before_overtime_cancellation']
    emp = dict(zip(emp_cols, emp_row, strict=False))

    att_rows = (await db.execute(text("""
        SELECT work_date,check_in,check_out,status,edited,edited_by,edit_reason,
               excuse_no_late,excuse_no_early,excuse_allow_overtime,shift_override
        FROM hr_attendance WHERE employee_id=:eid AND TO_CHAR(work_date,'YYYY-MM')=:month
        ORDER BY work_date
    """), {'eid': emp_id, 'month': month})).fetchall()
    att_cols = ['work_date','check_in','check_out','status','edited','edited_by','edit_reason','excuse_no_late','excuse_no_early','excuse_allow_overtime','shift_override']
    attendances = [dict(zip(att_cols, r, strict=False)) for r in att_rows]

    adv_rows = (await db.execute(text("SELECT amount, date, note FROM hr_advances WHERE employee_id=:eid AND TO_CHAR(date,'YYYY-MM')=:month"), {'eid': emp_id, 'month': month})).fetchall()
    adv_total = sum(float(r[0]) for r in adv_rows)
    finances = [{'type': 'سلفة', 'amount': float(r[0]), 'date': str(r[1]), 'note': r[2] or ''} for r in adv_rows]

    result = await asyncio.get_running_loop().run_in_executor(
        None,
        partial(calculate_payroll, emp, attendances, settings, shifts_map, advance=adv_total, month=month),
    )
    result['emp_name'] = emp['name']
    result['position'] = emp['position']
    result['base_salary'] = float(emp['monthly_salary'])
    result['month'] = month
    result['final_salary'] = result['net_salary']
    result['overtime_payment'] = result['overtime_pay']
    result['deduction'] = result.get('deductions', 0)
    result['advance'] = adv_total
    result['scheduled_month_hours'] = 26 * 12
    result['effective_days_in_month'] = 26
    result['days_in_month'] = 26
    result['shift_length'] = 12
    result['actual_working_days'] = result.get('actual_working_days', result.get('working_days', 0))
    result['vacation_days'] = result.get('vacation_days', 0)
    result['normal_hours_worked'] = result.get('total_hours', 0) - result.get('overtime_hours', 0)
    result['lateness_deduction'] = result.get('lateness_deduction', 0)
    result['late_penalty_multiplier'] = 2.0
    result['early_leave_minutes'] = result.get('early_leave_minutes', 0)
    result['missing_scan_minutes'] = result.get('missing_scan_minutes', 0)
    result['penalty_hours'] = 0
    result['bonus_days'] = result.get('bonus_days', 0)
    result['bonus_payment'] = result.get('bonus_payment', 0)
    result['base_pay_prorated'] = result['net_salary'] + adv_total + result.get('lateness_deduction', 0) - result.get('overtime_pay', 0)
    result['ignore_lateness'] = bool(emp.get('ignore_lateness', False))

    # Build Employee and Attendance objects for Qt ReportGenerator
    employee_obj = Employee(
        emp_id=str(emp['emp_code'] or emp['id']),
        name=emp['name'], position=emp['position'],
        monthly_salary=float(emp['monthly_salary']),
        shift=emp['shift_schedule'] or '',
        hire_date=str(emp['hire_date']) if emp['hire_date'] else None,
        ignore_lateness=bool(emp['ignore_lateness'])
    )
    att_objs = []
    for a in attendances:
        ci = a['check_in']
        co = a['check_out']
        wd = a.get('work_date')
        if ci and hasattr(ci, 'replace'):
            ci = ci.replace(tzinfo=None)
        elif wd:
            # No check_in recorded — use work_date at midnight so the day appears in report
            from datetime import date as _d2
            from datetime import datetime as _dt2
            ci = _dt2.combine(wd if isinstance(wd, _d2) else _d2.fromisoformat(str(wd)), _dt2.min.time())
        if co and hasattr(co, 'replace'):
            co = co.replace(tzinfo=None)
        att_objs.append(Attendance(
            str(emp['emp_code'] or emp['id']), ci, co,
            status=a.get('status','present') if a.get('status') != 'present' else 'regular',
            excuse_no_late=bool(a.get('excuse_no_late', False)),
            excuse_no_early=bool(a.get('excuse_no_early', False)),
            excuse_allow_overtime=bool(a.get('excuse_allow_overtime', False)),
            edited=bool(a.get('edited', False)),
            edit_reason=a.get('edit_reason', '')
        ))

    if report_type == 'ticket':
        html = ReportGenerator.generate_payslip_ticket(employee_obj, result, finances=finances)
    else:
        html = ReportGenerator.generate_employee_report(employee_obj, att_objs, result, finances=finances)

    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


@router.get("/attendance/report")
async def attendance_report(month: str, db: AsyncSession = Depends(get_db), _=Depends(_report_auth)):
    """Generate HTML attendance report — matches Qt generate_attendance_report()"""
    from app.activities.general.modules.hr.services.reports import ReportGenerator

    rows = (await db.execute(text("""
        SELECT e.name, e.emp_code, a.work_date, a.check_in, a.check_out, a.status,
               a.edited, a.edit_reason
        FROM hr_attendance a JOIN hr_employees e ON a.employee_id=e.id
        WHERE TO_CHAR(a.work_date,'YYYY-MM')=:month
        ORDER BY e.name, a.work_date
    """), {'month': month})).fetchall()

    report_rows = []
    for r in rows:
        ci = r[3]
        co = r[4]
        if ci and hasattr(ci, 'replace'):
            ci = ci.replace(tzinfo=None)
        if co and hasattr(co, 'replace'):
            co = co.replace(tzinfo=None)
        report_rows.append({
            'name': r[0], 'uid': r[1] or '', 'date': str(r[2]),
            'checkin': ci.isoformat() if ci else None,
            'checkout': co.isoformat() if co else None,
            'status': r[5] or 'present',
            'edited': bool(r[6]), 'edit_reason': r[7] or ''
        })

    html = ReportGenerator.generate_attendance_report(report_rows, month)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)
