"""Departments, rooms and doctors' rosters (#36). Everyone in the clinic reads them (booking);
clinic:manage changes them."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.healthcare.modules.healthcare_clinic import scheduling as sched
from app.activities.healthcare.modules.healthcare_clinic import service as access
from app.activities.healthcare.modules.healthcare_clinic.guards import require_clinic_manage
from app.activities.healthcare.modules.healthcare_clinic.models import (
    ClinicDepartment,
    ClinicDoctorSchedule,
    ClinicRoom,
)
from app.db.base import get_db
from app.dependencies import get_current_user
from app.platform.audit.service import log as audit_log
from app.platform.auth.models.user import User

router = APIRouter()


class DepartmentIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=16)
    name: str = Field(..., min_length=2, max_length=64)
    specialty_code: str = Field("", max_length=32)
    active: bool = True


class RoomIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    department_id: str | None = None
    active: bool = True


class ScheduleIn(BaseModel):
    doctor_user_id: str
    department_id: str
    room_id: str | None = None
    weekday: int = Field(..., ge=0, le=6)
    start_time: str
    end_time: str
    slot_minutes: int = Field(15, ge=5, le=240)
    active: bool = True


def _out(obj) -> dict:
    return {c.key: getattr(obj, c.key) for c in obj.__mapper__.column_attrs}


async def _audit(db, user: User, entity: str, action: str, data: dict, text: str) -> None:
    await audit_log(db, entity, action, user.id, user.full_name, None, data, text)


# ── Departments ───────────────────────────────────────────────────────────────────────────────

@router.get("/departments")
async def list_departments(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The department master; a clinic with none gets the usual departments on first read."""
    await sched.ensure_default_departments(db, current_user.tenant_id)
    q = select(ClinicDepartment).where(ClinicDepartment.tenant_id == current_user.tenant_id)
    if not include_inactive:
        q = q.where(ClinicDepartment.active.is_(True))
    return [_out(d) for d in (await db.execute(q.order_by(ClinicDepartment.name))).scalars()]


async def _code_free(db, tenant_id, code: str, exclude_id: str | None = None) -> None:
    q = select(ClinicDepartment.id).where(ClinicDepartment.tenant_id == tenant_id, ClinicDepartment.code == code)
    if exclude_id:
        q = q.where(ClinicDepartment.id != exclude_id)
    if await db.scalar(q):
        raise HTTPException(status_code=409, detail=f"رمز القسم {code} مستخدم لقسم آخر")


@router.post("/departments")
async def create_department(
    payload: DepartmentIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_manage),
):
    code = payload.code.strip().upper()
    await _code_free(db, current_user.tenant_id, code)
    dep = ClinicDepartment(tenant_id=current_user.tenant_id, code=code, name=payload.name.strip(),
                           specialty_code=payload.specialty_code.strip(), active=payload.active)
    db.add(dep)
    await db.flush()
    await _audit(db, current_user, "clinic_department", "create", {"id": dep.id, "code": code}, f"إضافة قسم {dep.name}")
    await db.commit()
    return _out(dep)


@router.put("/departments/{department_id}")
async def update_department(
    department_id: str,
    payload: DepartmentIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_manage),
):
    dep = await sched.department(db, current_user.tenant_id, department_id, active_only=False)
    code = payload.code.strip().upper()
    await _code_free(db, current_user.tenant_id, code, dep.id)
    dep.code, dep.name, dep.specialty_code, dep.active = code, payload.name.strip(), payload.specialty_code.strip(), payload.active
    await _audit(db, current_user, "clinic_department", "update", {"id": dep.id, "code": code, "active": dep.active},
                 f"تعديل القسم {dep.name}")
    await db.commit()
    return _out(dep)


# ── Rooms ─────────────────────────────────────────────────────────────────────────────────────

@router.get("/rooms")
async def list_rooms(
    department_id: str | None = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(ClinicRoom).where(ClinicRoom.tenant_id == current_user.tenant_id)
    if department_id:
        q = q.where(ClinicRoom.department_id == department_id)
    if not include_inactive:
        q = q.where(ClinicRoom.active.is_(True))
    return [_out(r) for r in (await db.execute(q.order_by(ClinicRoom.name))).scalars()]


@router.post("/rooms")
async def create_room(
    payload: RoomIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_manage),
):
    if payload.department_id:
        await sched.department(db, current_user.tenant_id, payload.department_id)
    r = ClinicRoom(tenant_id=current_user.tenant_id, name=payload.name.strip(), department_id=payload.department_id or None,
                   active=payload.active)
    db.add(r)
    await db.flush()
    await _audit(db, current_user, "clinic_room", "create", {"id": r.id}, f"إضافة غرفة كشف {r.name}")
    await db.commit()
    return _out(r)


@router.put("/rooms/{room_id}")
async def update_room(
    room_id: str,
    payload: RoomIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_manage),
):
    r = (await db.execute(select(ClinicRoom).where(ClinicRoom.id == room_id, ClinicRoom.tenant_id == current_user.tenant_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="غرفة الكشف غير موجودة")
    if payload.department_id:
        await sched.department(db, current_user.tenant_id, payload.department_id)
    r.name, r.department_id, r.active = payload.name.strip(), payload.department_id or None, payload.active
    await _audit(db, current_user, "clinic_room", "update", {"id": r.id, "active": r.active}, f"تعديل غرفة الكشف {r.name}")
    await db.commit()
    return _out(r)


# ── Rosters ───────────────────────────────────────────────────────────────────────────────────

async def _schedule_out(db, tenant_id, rows: list[ClinicDoctorSchedule]) -> list[dict]:
    doctors = {c["id"]: c["full_name"] for c in await access.clinicians(db, tenant_id)}
    deps = {d.id: d.name for d in (await db.execute(select(ClinicDepartment).where(ClinicDepartment.tenant_id == tenant_id))).scalars()}
    rooms = {r.id: r.name for r in (await db.execute(select(ClinicRoom).where(ClinicRoom.tenant_id == tenant_id))).scalars()}
    return [{**_out(s), "doctor_user_id": str(s.doctor_user_id), "doctor_name": doctors.get(str(s.doctor_user_id), "—"),
             "department_name": deps.get(s.department_id), "room_name": rooms.get(s.room_id),
             "weekday_name": sched.WEEKDAYS_AR[s.weekday]} for s in rows]


@router.get("/schedules")
async def list_schedules(
    doctor_user_id: uuid.UUID | None = None,
    department_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(ClinicDoctorSchedule).where(ClinicDoctorSchedule.tenant_id == current_user.tenant_id)
    if doctor_user_id:
        q = q.where(ClinicDoctorSchedule.doctor_user_id == doctor_user_id)
    if department_id:
        q = q.where(ClinicDoctorSchedule.department_id == department_id)
    rows = list((await db.execute(q.order_by(ClinicDoctorSchedule.weekday, ClinicDoctorSchedule.start_time))).scalars())
    return await _schedule_out(db, current_user.tenant_id, rows)


async def _validated(db, tenant_id, payload: ScheduleIn) -> dict:
    doctor = await access.clinician(db, tenant_id, payload.doctor_user_id)
    if not doctor["is_doctor"]:
        raise HTTPException(status_code=400, detail="الجداول للأطباء فقط")
    await sched.department(db, tenant_id, payload.department_id)
    if payload.room_id:
        await sched.room(db, tenant_id, payload.room_id)
    start, end = sched.normalize_slot(payload.start_time), sched.normalize_slot(payload.end_time)
    if start >= end:
        raise HTTPException(status_code=400, detail="وقت نهاية الجدول يجب أن يكون بعد بدايته")
    if sched.parse_slot(end) - sched.parse_slot(start) < payload.slot_minutes:
        raise HTTPException(status_code=400, detail="مدة الجدول أقصر من فترة الكشف الواحدة")
    return {"doctor_user_id": uuid.UUID(doctor["id"]), "department_id": payload.department_id, "room_id": payload.room_id or None,
            "weekday": payload.weekday, "start_time": start, "end_time": end, "slot_minutes": payload.slot_minutes,
            "active": payload.active, "_doctor_name": doctor["full_name"]}


@router.post("/schedules")
async def create_schedule(
    payload: ScheduleIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_manage),
):
    v = await _validated(db, current_user.tenant_id, payload)
    name = v.pop("_doctor_name")
    if v["active"]:
        await sched.check_schedule_free(db, current_user.tenant_id, v["doctor_user_id"], v["room_id"], v["weekday"],
                                        v["start_time"], v["end_time"])
    s = ClinicDoctorSchedule(tenant_id=current_user.tenant_id, **v)
    db.add(s)
    await db.flush()
    await _audit(db, current_user, "clinic_schedule", "create", {"id": s.id, "doctor": name},
                 f"جدول للطبيب {name} يوم {sched.WEEKDAYS_AR[s.weekday]} من {s.start_time} إلى {s.end_time}")
    await db.commit()
    return (await _schedule_out(db, current_user.tenant_id, [s]))[0]


async def _schedule_or_404(db, tenant_id, schedule_id: str) -> ClinicDoctorSchedule:
    s = (await db.execute(select(ClinicDoctorSchedule).where(
        ClinicDoctorSchedule.id == schedule_id, ClinicDoctorSchedule.tenant_id == tenant_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="الجدول غير موجود")
    return s


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    payload: ScheduleIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_manage),
):
    s = await _schedule_or_404(db, current_user.tenant_id, schedule_id)
    v = await _validated(db, current_user.tenant_id, payload)
    name = v.pop("_doctor_name")
    if v["active"]:
        await sched.check_schedule_free(db, current_user.tenant_id, v["doctor_user_id"], v["room_id"], v["weekday"],
                                        v["start_time"], v["end_time"], exclude_id=s.id)
    for k, val in v.items():
        setattr(s, k, val)
    await _audit(db, current_user, "clinic_schedule", "update", {"id": s.id, "doctor": name}, f"تعديل جدول الطبيب {name}")
    await db.commit()
    return (await _schedule_out(db, current_user.tenant_id, [s]))[0]


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_manage),
):
    s = await _schedule_or_404(db, current_user.tenant_id, schedule_id)
    await _audit(db, current_user, "clinic_schedule", "delete", {"id": s.id, "doctor_user_id": str(s.doctor_user_id)},
                 f"حذف جدول يوم {sched.WEEKDAYS_AR[s.weekday]} من {s.start_time} إلى {s.end_time}")
    await db.delete(s)
    await db.commit()


@router.get("/schedule/slots")
async def list_slots(
    doctor_user_id: uuid.UUID,
    date: str = Query(..., description="YYYY-MM-DD"),
    department_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The doctor's roster slots on that date and whether each is free; empty when the doctor has
    no roster that day (the booking form then takes a free time)."""
    return {"slots": await sched.slots(db, current_user.tenant_id, doctor_user_id, date, department_id),
            "has_roster": bool(await sched.schedules_for(db, current_user.tenant_id, [doctor_user_id]))}
