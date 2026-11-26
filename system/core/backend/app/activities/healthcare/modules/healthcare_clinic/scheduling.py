"""Healthcare & Clinic/Hospital ERP: departments, rooms, doctors' rosters and booking rules (#36).

- Times are "HH:MM" (24h). Appointments booked before #36 hold free text such as "11:30 AM";
  `parse_slot` reads both, `normalize_slot` refuses what it can't read for new bookings.
- An appointment lasts its doctor's roster slot on that weekday (DEFAULT_SLOT_MINUTES without one).
- No two non-cancelled appointments overlap for the same doctor or the same room on the same date.
- A doctor with a roster is booked only inside it (department and room come from the roster);
  a doctor without one is booked freely, as before.
"""
from __future__ import annotations

import re
import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.healthcare.modules.healthcare_clinic.models import (
    ClinicAppointment,
    ClinicDepartment,
    ClinicDoctorSchedule,
    ClinicRoom,
)

DEFAULT_SLOT_MINUTES = 15
FREE_STATUSES = ("cancelled",)
WEEKDAYS_AR = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")
DEFAULT_DEPARTMENTS = (
    ("IM", "الباطنة العامة", "internal_medicine"),
    ("PED", "طب الأطفال", "pediatrics"),
    ("OBG", "النساء والتوليد", "obstetrics_gynecology"),
    ("ORTH", "العظام", "orthopedics"),
    ("DERM", "الجلدية", "dermatology"),
    ("ENT", "الأنف والأذن والحنجرة", "otolaryngology"),
    ("DENT", "الأسنان", "dentistry"),
)

_SLOT = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.|ص|م|صباحا|صباحًا|مساء|مساءً)?\s*$", re.IGNORECASE)
_PM = ("pm", "p.m.", "م", "مساء", "مساءً")


def parse_slot(value: str | None) -> int | None:
    """Minutes after midnight for "14:30", "2:30 PM", "02:30 م"; None when unreadable."""
    m = _SLOT.match(value or "")
    if not m:
        return None
    hour, minute, mer = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if minute > 59:
        return None
    if mer:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if mer in _PM else 0)
    elif hour > 23:
        return None
    return hour * 60 + minute


def fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def normalize_slot(value: str) -> str:
    minutes = parse_slot(value)
    if minutes is None:
        raise HTTPException(status_code=400, detail=f"وقت الموعد غير صالح: «{value}». اكتبه بصيغة 24 ساعة مثل 14:30")
    return fmt(minutes)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="تاريخ الموعد غير صالح (YYYY-MM-DD)")


# ── Department master ─────────────────────────────────────────────────────────────────────────

async def ensure_default_departments(db: AsyncSession, tenant_id) -> None:
    """A clinic with no departments gets the usual ones (idempotent; the unique code index keeps
    two first visits at once from doubling them)."""
    if await db.scalar(select(func.count(ClinicDepartment.id)).where(ClinicDepartment.tenant_id == tenant_id)):
        return
    await db.execute(insert(ClinicDepartment).values([
        {"id": str(uuid.uuid4()), "tenant_id": tenant_id, "code": code, "name": name, "specialty_code": spec, "active": True}
        for code, name, spec in DEFAULT_DEPARTMENTS
    ]).on_conflict_do_nothing(index_elements=["tenant_id", "code"]))
    await db.commit()


async def department(db: AsyncSession, tenant_id, department_id: str, *, active_only: bool = True) -> ClinicDepartment:
    dep = (await db.execute(select(ClinicDepartment).where(
        ClinicDepartment.id == department_id, ClinicDepartment.tenant_id == tenant_id))).scalar_one_or_none()
    if not dep or (active_only and not dep.active):
        raise HTTPException(status_code=400, detail="القسم المختار غير موجود أو موقوف")
    return dep


async def room(db: AsyncSession, tenant_id, room_id: str) -> ClinicRoom:
    r = (await db.execute(select(ClinicRoom).where(ClinicRoom.id == room_id, ClinicRoom.tenant_id == tenant_id))).scalar_one_or_none()
    if not r or not r.active:
        raise HTTPException(status_code=400, detail="غرفة الكشف المختارة غير موجودة أو موقوفة")
    return r


async def department_by_name(db: AsyncSession, tenant_id, name: str) -> ClinicDepartment | None:
    return (await db.execute(select(ClinicDepartment).where(
        ClinicDepartment.tenant_id == tenant_id, ClinicDepartment.name == name.strip()).limit(1))).scalar_one_or_none()


# ── Rosters ───────────────────────────────────────────────────────────────────────────────────

async def schedules_for(db: AsyncSession, tenant_id, doctor_ids: list, weekday: int | None = None) -> list[ClinicDoctorSchedule]:
    if not doctor_ids:
        return []
    q = select(ClinicDoctorSchedule).where(
        ClinicDoctorSchedule.tenant_id == tenant_id, ClinicDoctorSchedule.active.is_(True),
        ClinicDoctorSchedule.doctor_user_id.in_(doctor_ids))
    if weekday is not None:
        q = q.where(ClinicDoctorSchedule.weekday == weekday)
    return list((await db.execute(q.order_by(ClinicDoctorSchedule.start_time))).scalars())


def _covering(schedules: list[ClinicDoctorSchedule], doctor_id, minutes: int) -> ClinicDoctorSchedule | None:
    for s in schedules:
        if str(s.doctor_user_id) == str(doctor_id) and parse_slot(s.start_time) <= minutes < parse_slot(s.end_time):
            return s
    return None


async def check_schedule_free(db: AsyncSession, tenant_id, doctor_id, room_id: str | None, weekday: int,
                              start: str, end: str, exclude_id: str | None = None) -> None:
    """A roster row may not overlap another of the same doctor, or of the same room, on the weekday."""
    q = select(ClinicDoctorSchedule).where(
        ClinicDoctorSchedule.tenant_id == tenant_id, ClinicDoctorSchedule.active.is_(True),
        ClinicDoctorSchedule.weekday == weekday,
        or_(ClinicDoctorSchedule.doctor_user_id == doctor_id,
            *([ClinicDoctorSchedule.room_id == room_id] if room_id else [])),
    )
    if exclude_id:
        q = q.where(ClinicDoctorSchedule.id != exclude_id)
    for s in (await db.execute(q)).scalars():
        if s.start_time < end and start < s.end_time:
            who = "الطبيب" if s.doctor_user_id == doctor_id else "الغرفة"
            raise HTTPException(status_code=409, detail=f"يتعارض هذا الجدول مع جدول آخر لنفس {who} يوم {WEEKDAYS_AR[weekday]} (من {s.start_time} إلى {s.end_time})")


# ── Booking ───────────────────────────────────────────────────────────────────────────────────

async def _day_appointments(db: AsyncSession, tenant_id, day: str, doctor_id, doctor_name: str, room_id: str | None,
                            exclude_id: str | None) -> list[ClinicAppointment]:
    if doctor_id:
        conds = [ClinicAppointment.doctor_user_id == doctor_id]
    else:  # older bookings by name only
        conds = [ClinicAppointment.doctor_user_id.is_(None) & (ClinicAppointment.doctor_name == doctor_name)]
    if room_id:
        conds.append(ClinicAppointment.room_id == room_id)
    q = select(ClinicAppointment).where(
        ClinicAppointment.tenant_id == tenant_id, ClinicAppointment.appointment_date == day,
        ClinicAppointment.status.notin_(FREE_STATUSES), or_(*conds))
    if exclude_id:
        q = q.where(ClinicAppointment.id != exclude_id)
    return list((await db.execute(q)).scalars())


async def _durations(db: AsyncSession, tenant_id, weekday: int, appts: list[ClinicAppointment]) -> dict[str, int]:
    """Each appointment's length: its doctor's roster slot at that time, else the default."""
    doctor_ids = list({a.doctor_user_id for a in appts if a.doctor_user_id})
    schedules = await schedules_for(db, tenant_id, doctor_ids, weekday)
    out = {}
    for a in appts:
        start = parse_slot(a.time_slot)
        s = _covering(schedules, a.doctor_user_id, start) if start is not None and a.doctor_user_id else None
        out[a.id] = s.slot_minutes if s else DEFAULT_SLOT_MINUTES
    return out


async def check_no_overlap(db: AsyncSession, tenant_id, *, day: str, slot: str, minutes: int, doctor_id, doctor_name: str,
                           room_id: str | None, exclude_id: str | None = None) -> None:
    """Refuse (409) when the doctor or the room already has a non-cancelled appointment overlapping
    [slot, slot + minutes) on that date. Older free-text times are read with parse_slot."""
    start = parse_slot(slot)
    appts = await _day_appointments(db, tenant_id, day, doctor_id, doctor_name, room_id, exclude_id)
    lengths = await _durations(db, tenant_id, parse_date(day).weekday(), appts)
    for a in appts:
        other = parse_slot(a.time_slot)
        if other is None or not (other < start + minutes and start < other + lengths[a.id]):
            continue
        same_doctor = (str(a.doctor_user_id) == str(doctor_id)) if doctor_id else (a.doctor_user_id is None and a.doctor_name == doctor_name)
        what = f"للطبيب {a.doctor_name}" if same_doctor else "في نفس غرفة الكشف"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"يوجد موعد آخر {what} بتاريخ {day} الساعة {fmt(other)} ({a.appointment_ref}). اختر وقتاً آخر.")


async def resolve_booking(db: AsyncSession, tenant_id, *, doctor_id, day: str, slot: str,
                          department_id: str | None, room_id: str | None) -> dict:
    """Where and how long: {"slot", "minutes", "department_id", "room_id"}. A doctor with a roster
    is booked only inside it, in the roster's department and room."""
    minutes_from_midnight = parse_slot(slot)
    weekday = parse_date(day).weekday()
    if doctor_id:
        all_rows = await schedules_for(db, tenant_id, [doctor_id])
        if all_rows:
            day_rows = [s for s in all_rows if s.weekday == weekday and (not department_id or s.department_id == department_id)]
            s = _covering(day_rows, doctor_id, minutes_from_midnight)
            if not s:
                hours = "، ".join(f"من {r.start_time} إلى {r.end_time}" for r in day_rows) or "لا يعمل في هذا اليوم"
                raise HTTPException(status_code=400, detail=f"الوقت خارج جدول الطبيب يوم {WEEKDAYS_AR[weekday]} ({hours})")
            if (minutes_from_midnight - parse_slot(s.start_time)) % s.slot_minutes:
                raise HTTPException(status_code=400, detail=f"اختر بداية فترة من جدول الطبيب (كل {s.slot_minutes} دقيقة من {s.start_time})")
            return {"slot": fmt(minutes_from_midnight), "minutes": s.slot_minutes,
                    "department_id": s.department_id, "room_id": s.room_id or room_id}
    return {"slot": fmt(minutes_from_midnight), "minutes": DEFAULT_SLOT_MINUTES,
            "department_id": department_id, "room_id": room_id}


async def slots(db: AsyncSession, tenant_id, doctor_id, day: str, department_id: str | None = None) -> list[dict]:
    """The doctor's roster slots on that date, each with whether it is still free."""
    weekday = parse_date(day).weekday()
    rows = [s for s in await schedules_for(db, tenant_id, [doctor_id], weekday)
            if not department_id or s.department_id == department_id]
    if not rows:
        return []
    rooms = {r.id: r.name for r in (await db.execute(select(ClinicRoom).where(
        ClinicRoom.id.in_([s.room_id for s in rows if s.room_id])))).scalars()} if any(s.room_id for s in rows) else {}
    room_ids = [s.room_id for s in rows if s.room_id]
    booked = list((await db.execute(select(ClinicAppointment).where(
        ClinicAppointment.tenant_id == tenant_id, ClinicAppointment.appointment_date == day,
        ClinicAppointment.status.notin_(FREE_STATUSES),
        or_(ClinicAppointment.doctor_user_id == doctor_id, *([ClinicAppointment.room_id.in_(room_ids)] if room_ids else [])),
    ))).scalars())
    lengths = await _durations(db, tenant_id, weekday, booked)
    taken = [(parse_slot(a.time_slot), lengths[a.id], a) for a in booked if parse_slot(a.time_slot) is not None]
    out = []
    for s in rows:
        t, end = parse_slot(s.start_time), parse_slot(s.end_time)
        while t + s.slot_minutes <= end:
            busy = any(o < t + s.slot_minutes and t < o + n and (str(a.doctor_user_id) == str(doctor_id) or (s.room_id and a.room_id == s.room_id))
                       for o, n, a in taken)
            out.append({"time": fmt(t), "minutes": s.slot_minutes, "available": not busy,
                        "department_id": s.department_id, "room_id": s.room_id, "room_name": rooms.get(s.room_id)})
            t += s.slot_minutes
    return out
