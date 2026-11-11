"""Employees and attendance: updates, manual attendance, device punches. Callers commit."""
import json
import uuid
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

EMPLOYEE_FIELDS = ("name", "user_id", "position", "monthly_salary", "shift_schedule", "hire_date", "is_active")


async def _require_employee(db: AsyncSession, employee_id) -> dict:
    row = (await db.execute(text("SELECT * FROM hr_employees WHERE id = :id FOR UPDATE"), {"id": employee_id})).mappings().first()
    if not row:
        raise HTTPException(404, "Employee not found")
    return dict(row)


async def update_employee(db: AsyncSession, employee_id: uuid.UUID, values: dict, user) -> bool:
    """Apply the sent fields; a salary change is recorded in the HR audit log. False if nothing changed."""
    values = {k: v for k, v in values.items() if k in EMPLOYEE_FIELDS}
    if not values:
        return False
    before = await _require_employee(db, employee_id)
    sets = ", ".join(f"{k} = :p_{k}" for k in values)
    await db.execute(text(f"UPDATE hr_employees SET {sets} WHERE id = :id"), {"id": employee_id, **{f"p_{k}": v for k, v in values.items()}})
    if "monthly_salary" in values and str(before.get("monthly_salary")) != str(values["monthly_salary"]):
        await db.execute(text("""
            INSERT INTO hr_audit_log (action_type, entity_type, entity_id, performed_by, reason, details)
            VALUES ('update', 'employee', :eid, :by, 'تعديل الراتب', :det)
        """), {"eid": str(employee_id), "by": str(user.id), "det": json.dumps(
            {"monthly_salary": {"from": str(before.get("monthly_salary")), "to": str(values["monthly_salary"])}})})
    return True


def _at(value, work_date: date) -> datetime | None:
    """A time typed by hand ("08:30" or a datetime) on the given day."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    s = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.combine(work_date, datetime.strptime(s, fmt).time())
        except ValueError:
            continue
    return None


async def save_attendance(db: AsyncSession, employee_id, work_date: date, check_in, check_out, status: str, notes: str | None) -> None:
    """Manual attendance for one employee and day (replaces that day)."""
    await _require_employee(db, employee_id)
    await db.execute(text("""
        INSERT INTO hr_attendance (employee_id, work_date, check_in, check_out, status, notes)
        VALUES (:eid, :dt, :ci, :co, :st, :notes)
        ON CONFLICT (employee_id, work_date) DO UPDATE
        SET check_in = EXCLUDED.check_in, check_out = EXCLUDED.check_out, status = EXCLUDED.status, notes = EXCLUDED.notes
    """), {"eid": employee_id, "dt": work_date, "ci": _at(check_in, work_date), "co": _at(check_out, work_date),
           "st": status, "notes": notes or ""})
