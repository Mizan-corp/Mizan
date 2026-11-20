"""HR / Payroll router. Everything here shows or changes pay (salaries, payroll, attendance,
advances, shifts): it needs the `payroll` permission; approving or reopening a month needs
`payroll:approve`, paying it `payroll:pay`. Reports open in a browser tab with a print token."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_print_user, require_perm
from app.platform.auth.models.user import User
from app.platform.permissions.access import can
from app.activities.general.modules.hr.schemas import (
    MONTH_PATTERN,
    AdvanceCancel,
    AdvanceCreate,
    AttendanceCreate,
    EmployeeCreate,
    EmployeeUpdate,
    HRSettingsUpdate,
    PayrollCalculate,
    PayrollPay,
    PayrollUpdate,
    ShiftCreate,
    ShiftUpdate,
)
from app.activities.general.modules.hr.services import advances as advances_service
from app.activities.general.modules.hr.services import employees as employees_service
from app.activities.general.modules.hr.services import attendance as hr_attendance_service
from app.activities.general.modules.hr.services import payroll as payroll_service
from app.activities.general.modules.hr.services import payslips

router = APIRouter(prefix="/hr", tags=["hr"])

PAYROLL = "payroll"
APPROVE = "payroll:approve"
PAY = "payroll:pay"
Month = Annotated[str, Query(pattern=MONTH_PATTERN, description="YYYY-MM")]
OptionalMonth = Annotated[str | None, Query(pattern=MONTH_PATTERN, description="YYYY-MM")]


def _rows(result) -> list[dict]:
    return [dict(r) for r in result.mappings().all()]


Page = Annotated[int, Query(ge=1, le=100000)]
PageSize = Annotated[int, Query(ge=1, le=200)]


async def _paged(db: AsyncSession, select_sql: str, from_where: str, params: dict, order: str, page: int,
                 page_size: int) -> dict:
    """{items, total, page, page_size}: one page of a list, and how many rows it has in all."""
    total = (await db.execute(text(f"SELECT COUNT(*) {from_where}"), params)).scalar_one()
    items = _rows(await db.execute(text(f"SELECT {select_sql} {from_where} ORDER BY {order} LIMIT :lim OFFSET :off"),
                                   {**params, "lim": page_size, "off": (page - 1) * page_size}))
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/audit-log")
async def get_audit_log(entity_type: Annotated[str | None, Query(max_length=32)] = None, page: Page = 1,
                        page_size: PageSize = 50, db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    """The HR audit trail, newest first, paged; `entity_type`: employee, payroll_entry, advance…"""
    where, params = "WHERE (CAST(:et AS text) IS NULL OR a.entity_type = :et)", {"et": entity_type}
    out = await _paged(db, """a.id, a.action_type, a.entity_type, a.entity_id, a.reason, a.details, a.created_at,
               u.full_name as performed_by_name, e.name AS employee_name""",
                       f"""FROM hr_audit_log a LEFT JOIN users u ON a.performed_by=u.id
                           LEFT JOIN hr_employees e ON a.entity_type IN ('employee', 'advance') AND e.id::text = a.entity_id
                           {where}""", params, "a.created_at DESC, a.id", page, page_size)
    for d in out["items"]:
        d['created_at'] = d['created_at'].isoformat() if d['created_at'] else None
    return out


SHIFT_NOT_FOUND = "الوردية غير موجودة"


@router.get("/shifts")
async def list_shifts(db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    """Every shift, the stopped ones too (they still name some employees' and days' shifts), with
    how many active employees work it."""
    return _rows(await db.execute(text("""
        SELECT s.*, (SELECT COUNT(*) FROM hr_employees e WHERE e.shift_id = s.id AND e.is_active) AS employees
        FROM hr_shifts s ORDER BY s.is_active DESC, s.start_time, s.name
    """)))


@router.post("/shifts")
async def create_shift(data: ShiftCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    sid = str(int(uuid.uuid4().int % 10**10))
    await db.execute(text("INSERT INTO hr_shifts (id, name, start_time, end_time, description) VALUES (:id,:name,:st,:et,:desc)"),
                     {'id': sid, 'name': data.name, 'st': data.start_time, 'et': data.end_time, 'desc': data.description})
    await db.commit()
    return {'id': sid, 'name': data.name}


@router.put("/shifts/{shift_id}")
async def update_shift(shift_id: Annotated[str, Path(max_length=32)], data: ShiftUpdate, db: AsyncSession = Depends(get_db),
                       _=Depends(require_perm(PAYROLL))):
    """Change only the fields sent. The new hours count from the next calculation; an approved
    month keeps what it was approved with."""
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    row = (await db.execute(text("SELECT * FROM hr_shifts WHERE id = :id FOR UPDATE"), {"id": shift_id})).mappings().first()
    if row is None:
        raise HTTPException(404, SHIFT_NOT_FOUND)
    if not changes:
        return dict(row)
    sets = ", ".join(f"{k} = :{k}" for k in changes)
    row = (await db.execute(text(f"UPDATE hr_shifts SET {sets}, updated_at = now() WHERE id = :id RETURNING *"),
                            {**changes, "id": shift_id})).mappings().one()
    await db.commit()
    return dict(row)


@router.delete("/shifts/{shift_id}", status_code=204)
async def delete_shift(shift_id: Annotated[str, Path(max_length=32)], db: AsyncSession = Depends(get_db),
                       _=Depends(require_perm(PAYROLL))):
    """An unused shift is deleted; one that employees or attendance days name is stopped instead."""
    if not await db.scalar(text("SELECT 1 FROM hr_shifts WHERE id = :id FOR UPDATE"), {"id": shift_id}):
        raise HTTPException(404, SHIFT_NOT_FOUND)
    used = await db.scalar(text("""
        SELECT EXISTS (SELECT 1 FROM hr_employees WHERE shift_id = :id)
            OR EXISTS (SELECT 1 FROM hr_attendance WHERE shift_override = :id)
    """), {"id": shift_id})
    if used:
        await db.execute(text("UPDATE hr_shifts SET is_active = false, updated_at = now() WHERE id = :id"), {"id": shift_id})
    else:
        await db.execute(text("DELETE FROM hr_shifts WHERE id = :id"), {"id": shift_id})
    await db.commit()


@router.get("/settings")
async def get_hr_settings(db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    """Every payroll setting, typed, with its default when never saved."""
    return await payroll_service.hr_settings(db)


@router.put("/settings")
async def update_hr_settings(data: HRSettingsUpdate, db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    for k, v in data.settings.model_dump(exclude_none=True).items():
        # Flags are stored as the engine reads them ("True"/"False").
        await db.execute(text("INSERT INTO hr_settings (key, value) VALUES (:k,:v) ON CONFLICT (tenant_id, key) DO UPDATE SET value=EXCLUDED.value"),
                         {'k': k, 'v': str(v)})
    await db.commit()
    return await payroll_service.hr_settings(db)


# ── Employees ─────────────────────────────────────────────────────────────
PUBLIC_EMPLOYEE_FIELDS = ("id", "emp_code", "name", "position", "is_active")


@router.get("/employees")
async def list_employees(include_inactive: bool = False, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_perm(PAYROLL, "accounting:view", "accounting:journal"))):
    """The active employees (`include_inactive`: the stopped ones too, for `payroll`). Accountants
    without `payroll` (who pick an employee as a journal line's party) get names only, without pay."""
    full = can(current_user, PAYROLL)
    rows = _rows(await db.execute(text("""
        SELECT e.*, s.name AS shift_name FROM hr_employees e LEFT JOIN hr_shifts s ON s.id = e.shift_id
        WHERE (:all OR e.is_active) ORDER BY e.is_active DESC, e.name
    """), {"all": include_inactive and full}))
    if full:
        return rows
    return [{k: r.get(k) for k in PUBLIC_EMPLOYEE_FIELDS} for r in rows]


@router.post("/employees")
async def create_employee(data: EmployeeCreate, db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    row = await employees_service.create_employee(db, data.model_dump())
    await db.commit()
    return row


@router.put("/employees/{emp_id}")
async def update_employee(emp_id: uuid.UUID, data: EmployeeUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm(PAYROLL))):
    if not await employees_service.update_employee(db, emp_id, data.model_dump(exclude_unset=True), current_user):
        return {"detail": "no changes"}
    await db.commit()
    return {"detail": "updated"}


@router.delete("/employees/{emp_id}", status_code=204)
async def delete_employee(emp_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    result = await db.execute(text("UPDATE hr_employees SET is_active=FALSE WHERE id=:id"), {'id': emp_id})
    if result.rowcount == 0:
        raise HTTPException(404, "الموظف غير موجود")
    await db.commit()


# ── Attendance ─────────────────────────────────────────────────────────────
@router.get("/attendance")
async def list_attendance(employee_id: uuid.UUID | None = None, month: OptionalMonth = None,
                          page: Page = 1, page_size: PageSize = 50,
                          db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    """Attendance days, newest first, paged: {items, total, page, page_size}."""
    q = "FROM hr_attendance a JOIN hr_employees e ON a.employee_id=e.id WHERE 1=1"
    params = {}
    if employee_id:
        q += " AND a.employee_id=:eid"
        params['eid'] = employee_id
    if month:
        q += " AND a.work_date >= :start AND a.work_date < :end"
        params['start'], params['end'] = payroll_service.month_range(month)
    return await _paged(db, "a.*, e.name as emp_name", q, params, "a.work_date DESC, e.name, a.id", page, page_size)


@router.post("/attendance")
async def add_attendance(data: AttendanceCreate, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_perm(PAYROLL))):
    att_id = await employees_service.save_attendance(
        db, data.employee_id, data.work_date, data.check_in, data.check_out, data.status, data.notes, current_user,
        edit_reason=data.edit_reason, excuse_no_late=data.excuse_no_late, excuse_no_early=data.excuse_no_early,
        excuse_allow_overtime=data.excuse_allow_overtime, shift_override=data.shift_override)
    await db.commit()
    return {"detail": "saved", "id": str(att_id)}


@router.post("/attendance/import-csv")
async def import_attendance_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm(PAYROLL)),
):
    content = await file.read(hr_attendance_service.MAX_CSV_BYTES + 1)
    return await hr_attendance_service.import_attendance_csv_stream(db, content)


# ── Payroll ────────────────────────────────────────────────────────────────
@router.get("/payroll")
async def list_payroll(month: OptionalMonth = None, db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
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
    return _rows(await db.execute(text(q), params))


@router.post("/payroll/calculate")
async def calculate_payroll(
    data: PayrollCalculate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm(PAYROLL)),
):
    """Calculate payroll for all (or one) employee using the full engine."""
    return await payroll_service.calculate_payroll_month(
        db,
        month=data.month,
        current_user_id=str(current_user.id),
        employee_id=data.employee_id,
    )


@router.get("/payroll/period")
async def get_payroll_period(month: Month, db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    """The month's period (read only: a month nobody calculated yet is a draft without an id)."""
    return await payroll_service.get_period(db, month)


@router.post("/payroll/period/submit")
async def submit_payroll_period(
    month: Month,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm(PAYROLL)),
):
    await payroll_service.submit_payroll_period(db, month, str(current_user.id))
    return {"detail": "submitted"}


@router.post("/payroll/period/approve")
async def approve_payroll_period(
    month: Month,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm(APPROVE)),
):
    total = await payroll_service.approve_payroll_period(db, month, str(current_user.id))
    return {"detail": "approved", "total": float(total)}


@router.post("/payroll/period/pay")
async def pay_payroll_period(
    month: Month,
    data: PayrollPay | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm(PAY)),
):
    """Pay the approved month from a safe (or bank account) or wallet."""
    data = data or PayrollPay()
    total = await payroll_service.pay_payroll_period(db, month, str(current_user.id),
                                                     safe_id=data.safe_id, wallet_id=data.wallet_id)
    return {"detail": "paid", "total": total}


@router.post("/payroll/period/reopen")
async def reopen_payroll_period(
    month: Month,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm(APPROVE)),
):
    await payroll_service.reopen_payroll_period(db, month, str(current_user.id))
    return {"detail": "reopened"}


@router.get("/payroll/{payroll_id}/breakdown")
async def get_daily_breakdown(payroll_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    """Get daily attendance breakdown for a payroll record."""
    return await payroll_service.get_daily_breakdown(db, payroll_id)


@router.put("/payroll/{payroll_id}")
async def update_payroll(
    payroll_id: uuid.UUID,
    data: PayrollUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_perm(PAYROLL)),
):
    """Manual adjustments on a payroll entry, while its month is a draft or in review."""
    net_salary = await payroll_service.update_payroll_entry(
        db,
        payroll_id=payroll_id,
        bonus=data.bonus,
        deductions=data.deductions,
        drawer_variance=data.drawer_variance,
        notes=data.notes,
        current_user_id=current_user.id,
    )
    return {"detail": "updated", "net_salary": net_salary}


# ── Advances ───────────────────────────────────────────────────────────────
@router.get("/advances")
async def list_advances(employee_id: uuid.UUID | None = None, month: OptionalMonth = None,
                        page: Page = 1, page_size: PageSize = 50,
                        db: AsyncSession = Depends(get_db), _=Depends(require_perm(PAYROLL))):
    """Advances, deductions and bonuses, newest first, paged: {items, total, page, page_size}."""
    q = "FROM hr_advances a JOIN hr_employees e ON a.employee_id=e.id WHERE 1=1"
    params = {}
    if employee_id:
        q += " AND a.employee_id=:eid"
        params['eid'] = employee_id
    if month:
        q += " AND a.date >= :start AND a.date < :end"
        params['start'], params['end'] = payroll_service.month_range(month)
    return await _paged(db, "a.*, e.name as emp_name", q, params, "a.date DESC, a.created_at DESC, a.id", page, page_size)


@router.post("/advances")
async def add_advance(data: AdvanceCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_perm(PAYROLL))):
    """An advance (سلفة) is cash paid to the employee now, from a safe or wallet, and deducted from
    the month's salary. A deduction (خصم) or bonus (مكافأة) only changes the salary: no cash moves."""
    advance_id = await advances_service.add_record(db, data, current_user)
    await db.commit()
    return {"detail": "saved", "id": str(advance_id)}


@router.post("/advances/{advance_id}/cancel")
async def cancel_advance(advance_id: uuid.UUID, data: AdvanceCancel | None = None, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(require_perm(PAYROLL))):
    """Cancel an advance, deduction or bonus of a month not yet approved. An advance's cash goes
    back to its safe or wallet and its ledger entry is reversed."""
    row = await advances_service.cancel_record(db, advance_id, (data or AdvanceCancel()).reason, current_user)
    await db.commit()
    return row


# ── Reports (print token) ──────────────────────────────────────────────────
async def _report_auth(user=Depends(get_print_user)):
    """Payroll and attendance reports open in a browser tab with a print token: the workspace is
    bound from it, and they need the payroll permission."""
    if not can(user, PAYROLL):
        raise HTTPException(403, "Insufficient permissions")
    return user


@router.get("/payroll/report/monthly")
async def payroll_monthly_report(month: Month, db: AsyncSession = Depends(get_db), _=Depends(_report_auth)):
    """The month's payroll: the stored entries (the only source once the month is approved)."""
    return HTMLResponse(content=await payslips.monthly_report(db, month))


@router.get("/payroll/report/employee/{emp_id}")
async def employee_report(emp_id: uuid.UUID, month: Month, report_type: str = Query('detailed', pattern="^(detailed|ticket)$"),
                          db: AsyncSession = Depends(get_db), _=Depends(_report_auth)):
    """An employee's detailed report or payslip (report_type=ticket) for the month."""
    return HTMLResponse(content=await payslips.employee_report(db, emp_id, month, report_type))


@router.get("/attendance/report")
async def attendance_report(month: Month, db: AsyncSession = Depends(get_db), _=Depends(_report_auth)):
    return HTMLResponse(content=await payslips.attendance_report(db, month))
