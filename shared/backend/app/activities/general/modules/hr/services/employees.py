"""Employees and attendance: create, update, manual attendance. Callers commit."""
import json
import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.hr.services.payroll import ensure_month_open, month_of

EMPLOYEE_FIELDS = ("name", "user_id", "position", "monthly_salary", "shift_schedule", "shift_id", "hire_date",
                   "is_active", "ignore_lateness", "max_lateness_before_overtime_cancellation")
DUPLICATE_CODE = "كود الموظف مستخدم لموظف آخر"


async def _require_employee(db: AsyncSession, employee_id) -> dict:
    row = (await db.execute(text("SELECT * FROM hr_employees WHERE id = :id FOR UPDATE"), {"id": employee_id})).mappings().first()
    if not row:
        raise HTTPException(404, "الموظف غير موجود")
    return dict(row)


async def _code_taken(db: AsyncSession, code: str | None, except_id=None) -> bool:
    if not code:
        return False
    return (await db.execute(text("SELECT 1 FROM hr_employees WHERE emp_code = :c AND id IS DISTINCT FROM :id"),
                             {"c": code, "id": except_id})).first() is not None


async def _check_shift(db: AsyncSession, shift_id: str | None) -> None:
    """A shift chosen for an employee is one of the workspace's (404 otherwise)."""
    if shift_id and not await db.scalar(text("SELECT 1 FROM hr_shifts WHERE id = :id"), {"id": shift_id}):
        raise HTTPException(404, "الوردية غير موجودة")


async def create_employee(db: AsyncSession, values: dict) -> dict:
    """A new employee; a code another employee of the workspace has is a 409."""
    await _check_shift(db, values.get("shift_id"))
    code = (values.get("emp_code") or "").strip() or None
    if await _code_taken(db, code):
        raise HTTPException(409, DUPLICATE_CODE)
    row = (await db.execute(text("""
        INSERT INTO hr_employees (emp_code, user_id, name, position, monthly_salary, shift_schedule, shift_id, hire_date,
                                  ignore_lateness, max_lateness_before_overtime_cancellation)
        VALUES (:code, :uid, :name, :pos, :sal, :shift, :shift_id, :hire, :ignore, :max_late) RETURNING *
    """), {"code": code, "uid": values.get("user_id"), "name": values["name"], "pos": values.get("position") or "",
           "sal": values.get("monthly_salary") or 0, "shift": values.get("shift_schedule") or "",
           "shift_id": values.get("shift_id"), "hire": values.get("hire_date"),
           "ignore": bool(values.get("ignore_lateness")),
           "max_late": values.get("max_lateness_before_overtime_cancellation", 30)})).mappings().one()
    return dict(row)


async def update_employee(db: AsyncSession, employee_id: uuid.UUID, values: dict, user) -> bool:
    """Apply the sent fields; a salary change is recorded in the HR audit log. False if nothing changed."""
    values = {k: v for k, v in values.items() if k in EMPLOYEE_FIELDS}
    if not values:
        return False
    before = await _require_employee(db, employee_id)
    await _check_shift(db, values.get("shift_id"))
    if "name" in values and not values["name"]:
        values.pop("name")
    sets = ", ".join(f"{k} = :p_{k}" for k in values)
    await db.execute(text(f"UPDATE hr_employees SET {sets} WHERE id = :id"), {"id": employee_id, **{f"p_{k}": v for k, v in values.items()}})
    if "monthly_salary" in values and str(before.get("monthly_salary")) != str(values["monthly_salary"]):
        await db.execute(text("""
            INSERT INTO hr_audit_log (action_type, entity_type, entity_id, performed_by, reason, details)
            VALUES ('update', 'employee', :eid, :by, 'تعديل الراتب', CAST(:det AS jsonb))
        """), {"eid": str(employee_id), "by": str(user.id), "det": json.dumps(
            {"monthly_salary": {"from": str(before.get("monthly_salary")), "to": str(values["monthly_salary"])}})})
    return True


def _at(value, work_date: date) -> datetime | None:
    """A time typed by hand ("08:30" or a datetime) on the given day: the wall-clock time marked
    UTC, as the payroll engine reads attendance (it drops the zone)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC)
    s = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.combine(work_date, datetime.strptime(s, fmt).time(), tzinfo=UTC)
        except ValueError:
            continue
    raise HTTPException(400, f"وقت غير صالح: {s[:16]}")


async def save_attendance(db: AsyncSession, employee_id, work_date: date, check_in, check_out, status: str,
                          notes: str | None, user=None, *, edit_reason: str | None = None,
                          excuse_no_late: bool = False, excuse_no_early: bool = False,
                          excuse_allow_overtime: bool = False, shift_override: str | None = None) -> uuid.UUID:
    """Manual attendance for one employee and day (replaces that day). Refused when the month's
    payroll is approved or paid. The day is marked edited, by whom and why, so a later CSV
    import keeps it."""
    await ensure_month_open(db, month_of(work_date), "الحضور")
    await _require_employee(db, employee_id)
    ci, co = _at(check_in, work_date), _at(check_out, work_date)
    if ci and co and co <= ci:
        co += timedelta(days=1)  # a night shift ends the next morning
    return (await db.execute(text("""
        INSERT INTO hr_attendance (employee_id, work_date, check_in, check_out, status, notes, edited, edited_by,
                                   edit_reason, excuse_no_late, excuse_no_early, excuse_allow_overtime, shift_override)
        VALUES (:eid, :dt, :ci, :co, :st, :notes, TRUE, :by, :reason, :nl, :ne, :ot, :so)
        ON CONFLICT (employee_id, work_date) DO UPDATE
        SET check_in = EXCLUDED.check_in, check_out = EXCLUDED.check_out, status = EXCLUDED.status,
            notes = EXCLUDED.notes, edited = TRUE, edited_by = EXCLUDED.edited_by, edit_reason = EXCLUDED.edit_reason,
            excuse_no_late = EXCLUDED.excuse_no_late, excuse_no_early = EXCLUDED.excuse_no_early,
            excuse_allow_overtime = EXCLUDED.excuse_allow_overtime, shift_override = EXCLUDED.shift_override,
            updated_at = now()
        RETURNING id
    """), {"eid": employee_id, "dt": work_date, "ci": ci, "co": co, "st": status, "notes": notes or "",
           "by": str(user.id) if user is not None else None, "reason": edit_reason or "تعديل يدوي",
           "nl": excuse_no_late, "ne": excuse_no_early, "ot": excuse_allow_overtime,
           "so": shift_override})).scalar_one()
