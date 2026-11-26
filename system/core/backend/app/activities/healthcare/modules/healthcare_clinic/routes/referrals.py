"""Referrals between departments and doctors (#45).

- A doctor who reaches the patient's record refers them to a department (optionally a doctor in
  it), with a priority, the reason and triage notes, and the encounter it came from.
- The receiving side: the named doctor, or with none named the doctors on the department's roster
  (any doctor when the department has no roster yet). They see the reason and triage notes.
- Accepting puts the receiving doctor on the patient's care team (consultant): from then on they
  read the whole record. The encounter summary on a referral is a clinical read: shown only to
  those who reach the record, and logged.
- clinic:manage sees every referral for coordination, without the clinical text.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.healthcare.modules.healthcare_clinic import scheduling as sched
from app.activities.healthcare.modules.healthcare_clinic import service as access
from app.activities.healthcare.modules.healthcare_clinic.guards import _has_clinic_perm, require_clinic_doctor
from app.activities.healthcare.modules.healthcare_clinic.models import (
    ClinicDepartment,
    ClinicDoctorSchedule,
    ClinicEncounter,
    ClinicPatient,
    ClinicReferral,
)
from app.db.base import get_db
from app.dependencies import get_current_user
from app.platform.audit.service import log as audit_log
from app.platform.auth.models.user import User
from app.platform.permissions.access import can

router = APIRouter()

PRIORITY_AR = {"routine": "عادية", "urgent": "عاجلة", "emergency": "طارئة"}
STATUS_AR = {"pending": "بانتظار الرد", "accepted": "مقبولة", "declined": "مرفوضة", "completed": "مكتملة"}


class ReferralCreate(BaseModel):
    patient_id: str
    to_department_id: str
    to_doctor_user_id: str | None = None
    priority: Literal["routine", "urgent", "emergency"] = "routine"
    reason: str = Field(..., min_length=5, max_length=2000)
    triage_notes: str = Field("", max_length=4000)
    encounter_id: str | None = None


class ReferralResponse(BaseModel):
    note: str = Field("", max_length=1000)


def _my_departments(user):
    return select(ClinicDoctorSchedule.department_id).where(
        ClinicDoctorSchedule.doctor_user_id == user.id, ClinicDoctorSchedule.active.is_(True))


def _incoming_condition(user):
    """Referrals this doctor receives: named to them, or to a department they're rostered in (or
    one with no roster yet) with no doctor named."""
    no_roster = ~exists().where(ClinicDoctorSchedule.department_id == ClinicReferral.to_department_id,
                                ClinicDoctorSchedule.active.is_(True))
    return and_(
        ClinicReferral.from_doctor_user_id.is_distinct_from(user.id),
        or_(ClinicReferral.to_doctor_user_id == user.id,
            and_(ClinicReferral.to_doctor_user_id.is_(None),
                 or_(ClinicReferral.to_department_id.in_(_my_departments(user)), no_roster))),
    )


async def _is_recipient(db: AsyncSession, user, ref: ClinicReferral) -> bool:
    if not can(user, "clinic:doctor"):
        return False
    return bool(await db.scalar(select(ClinicReferral.id).where(ClinicReferral.id == ref.id, _incoming_condition(user))))


async def _rows_out(db: AsyncSession, user, rows: list[ClinicReferral]) -> list[dict]:
    if not rows:
        return []
    tid = user.tenant_id
    patients = {p.id: p for p in (await db.execute(select(ClinicPatient).where(
        ClinicPatient.id.in_({r.patient_id for r in rows})))).scalars()}
    deps = {d.id: d.name for d in (await db.execute(select(ClinicDepartment).where(ClinicDepartment.tenant_id == tid))).scalars()}
    names = {c["id"]: c["full_name"] for c in await access.clinicians(db, tid)}
    incoming: set[str] = set()
    if can(user, "clinic:doctor"):
        incoming = set((await db.execute(select(ClinicReferral.id).where(
            ClinicReferral.id.in_([r.id for r in rows]), _incoming_condition(user)))).scalars())
    out = []
    for r in rows:
        mine = r.from_doctor_user_id == user.id or r.id in incoming
        p = patients.get(r.patient_id)
        out.append({
            "id": r.id, "referral_ref": r.referral_ref, "patient_id": r.patient_id,
            "patient_name": p.full_name if p else "—", "patient_mrn": p.patient_mrn if p else "",
            "from_doctor_user_id": str(r.from_doctor_user_id) if r.from_doctor_user_id else None,
            "from_doctor_name": r.from_doctor_name,
            "to_department_id": r.to_department_id, "to_department_name": deps.get(r.to_department_id, "—"),
            "to_doctor_user_id": str(r.to_doctor_user_id) if r.to_doctor_user_id else None,
            "to_doctor_name": names.get(str(r.to_doctor_user_id)) if r.to_doctor_user_id else None,
            "priority": r.priority, "status": r.status, "encounter_id": r.encounter_id,
            # The clinical text is for the two sides of the referral, not for coordination.
            "reason": r.reason if mine else None, "triage_notes": r.triage_notes if mine else None,
            "response_note": r.response_note, "responded_at": r.responded_at, "created_at": r.created_at,
            "direction": "outgoing" if r.from_doctor_user_id == user.id else "incoming" if r.id in incoming else None,
            "can_respond": r.id in incoming and r.status == "pending",
            "can_complete": r.status == "accepted" and (r.to_doctor_user_id == user.id or r.from_doctor_user_id == user.id),
        })
    return out


async def _referral_or_404(db: AsyncSession, tenant_id, referral_id: str) -> ClinicReferral:
    r = (await db.execute(select(ClinicReferral).where(ClinicReferral.id == referral_id,
                                                       ClinicReferral.tenant_id == tenant_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="الإحالة غير موجودة")
    return r


async def _can_see(db, user, r: ClinicReferral) -> bool:
    return r.from_doctor_user_id == user.id or _has_clinic_perm(user, "clinic:manage") or await _is_recipient(db, user, r)


@router.get("/referrals")
async def list_referrals(
    box: Literal["incoming", "outgoing", "all"] = "incoming",
    status_filter: str | None = Query(None, alias="status"),
    patient_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(ClinicReferral).where(ClinicReferral.tenant_id == current_user.tenant_id)
    if box == "incoming":
        if not can(current_user, "clinic:doctor"):
            return []
        q = q.where(_incoming_condition(current_user))
    elif box == "outgoing":
        q = q.where(ClinicReferral.from_doctor_user_id == current_user.id)
    elif not _has_clinic_perm(current_user, "clinic:manage"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="عرض جميع الإحالات لإدارة العيادة (clinic:manage)")
    if status_filter:
        q = q.where(ClinicReferral.status == status_filter)
    if patient_id:
        q = q.where(ClinicReferral.patient_id == patient_id)
    rows = list((await db.execute(q.order_by(ClinicReferral.created_at.desc()).limit(limit))).scalars())
    out = await _rows_out(db, current_user, rows)
    shown = sum(1 for r in out if r["reason"] is not None)
    if shown:
        await access.log_access(db, current_user, "referrals", "referral", patient_id, shown)
    return out


@router.post("/referrals")
async def create_referral(
    payload: ReferralCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_doctor),
):
    tid = current_user.tenant_id
    patient = (await db.execute(select(ClinicPatient).where(ClinicPatient.id == payload.patient_id,
                                                            ClinicPatient.tenant_id == tid))).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="الملف الطبي للمريض غير موجود")
    await access.require_clinical_access(db, current_user, patient.id)
    dep = await sched.department(db, tid, payload.to_department_id)
    to_doctor = None
    if payload.to_doctor_user_id:
        to_doctor = await access.clinician(db, tid, payload.to_doctor_user_id)
        if not to_doctor["is_doctor"]:
            raise HTTPException(status_code=400, detail="تُوجَّه الإحالة إلى طبيب")
        if to_doctor["id"] == str(current_user.id):
            raise HTTPException(status_code=400, detail="لا يمكنك إحالة المريض إلى نفسك")
        rostered = {c["id"] for c in await access.clinicians(db, tid, department_id=dep.id)}
        if rostered and to_doctor["id"] not in rostered:
            raise HTTPException(status_code=400, detail=f"الطبيب المختار ليس ضمن جدول قسم {dep.name}")
    if payload.encounter_id:
        enc = await db.scalar(select(ClinicEncounter.id).where(ClinicEncounter.id == payload.encounter_id,
                                                               ClinicEncounter.patient_id == patient.id))
        if not enc:
            raise HTTPException(status_code=400, detail="الكشف المختار لا يخص هذا المريض")
    ref = ClinicReferral(
        tenant_id=tid, referral_ref=f"REF-{uuid.uuid4().hex[:6].upper()}", patient_id=patient.id,
        from_doctor_user_id=current_user.id, from_doctor_name=(current_user.full_name or current_user.username or "")[:128],
        to_department_id=dep.id, to_doctor_user_id=uuid.UUID(to_doctor["id"]) if to_doctor else None,
        priority=payload.priority, reason=payload.reason.strip(), triage_notes=payload.triage_notes.strip(),
        encounter_id=payload.encounter_id or None,
    )
    db.add(ref)
    await db.flush()
    recipients = [ref.to_doctor_user_id] if ref.to_doctor_user_id else [
        uuid.UUID(c["id"]) for c in await access.clinicians(db, tid, department_id=dep.id) if c["is_doctor"]]
    await access.notify_users(
        db, tid, [u for u in recipients if u != current_user.id], type="clinic_referral",
        severity="warning" if ref.priority != "routine" else "info",
        title=f"إحالة {PRIORITY_AR[ref.priority]} إلى {dep.name}",
        body=f"{ref.from_doctor_name} أحال المريض {patient.full_name} ({ref.referral_ref})",
        link="/clinic?tab=referrals", data={"referral_id": ref.id, "patient_id": patient.id},
    )
    await audit_log(db, "clinic_referral", "create", current_user.id, current_user.full_name, None,
                    {"referral_ref": ref.referral_ref, "patient_id": patient.id, "to_department": dep.id,
                     "to_doctor": to_doctor["id"] if to_doctor else None, "priority": ref.priority},
                    f"إحالة المريض {patient.full_name} إلى {dep.name} ({PRIORITY_AR[ref.priority]})")
    await db.commit()
    return (await _rows_out(db, current_user, [ref]))[0]


@router.get("/referrals/{referral_id}")
async def get_referral(
    referral_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The referral and, for those who reach the patient's record, the encounter it came from (or
    the patient's latest), logged as a clinical read."""
    r = await _referral_or_404(db, current_user.tenant_id, referral_id)
    if not await _can_see(db, current_user, r):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="هذه الإحالة ليست موجهة إليك")
    out = (await _rows_out(db, current_user, [r]))[0]
    how = await access.clinical_access(db, current_user, r.patient_id)
    out["record_access"] = bool(how)
    out["last_encounter"] = None
    if how:
        q = select(ClinicEncounter).where(ClinicEncounter.tenant_id == current_user.tenant_id,
                                          ClinicEncounter.patient_id == r.patient_id)
        enc = None
        if r.encounter_id:
            enc = (await db.execute(q.where(ClinicEncounter.id == r.encounter_id))).scalar_one_or_none()
        if enc is None:
            enc = (await db.execute(q.order_by(ClinicEncounter.created_at.desc()).limit(1))).scalar_one_or_none()
        if enc:
            out["last_encounter"] = {k: getattr(enc, k) for k in (
                "id", "encounter_ref", "encounter_date", "doctor_name", "department", "bp_systolic", "bp_diastolic",
                "heart_rate", "temperature", "spo2", "chief_complaint", "icd10_code", "icd10_description", "clinical_notes")}
        await access.log_access(db, current_user, "referral", how, r.patient_id, 1 if enc else 0)
    elif out["reason"] is not None:
        await access.log_access(db, current_user, "referral", "referral", r.patient_id, 1)
    return out


async def _respond(db: AsyncSession, user: User, referral_id: str, new_status: str, note: str) -> ClinicReferral:
    r = await _referral_or_404(db, user.tenant_id, referral_id)
    if r.status != "pending":
        raise HTTPException(status_code=409, detail=f"تم الرد على هذه الإحالة بالفعل ({STATUS_AR.get(r.status, r.status)})")
    if not await _is_recipient(db, user, r):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="هذه الإحالة ليست موجهة إليك أو إلى قسمك")
    r.status, r.responded_by, r.responded_at, r.response_note = new_status, user.id, datetime.now(UTC), note.strip()
    return r


@router.post("/referrals/{referral_id}/accept")
async def accept_referral(
    referral_id: str,
    payload: ReferralResponse = ReferralResponse(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_doctor),
):
    """Accept: the receiving doctor joins the patient's care team, and the patient's record with
    the referral's triage notes is theirs to read."""
    r = await _respond(db, current_user, referral_id, "accepted", payload.note)
    r.to_doctor_user_id = current_user.id
    await access.add_to_care_team(db, current_user.tenant_id, r.patient_id, current_user.id, "consultant", current_user.id)
    patient_name = await db.scalar(select(ClinicPatient.full_name).where(ClinicPatient.id == r.patient_id))
    await access.notify_users(db, current_user.tenant_id, [r.from_doctor_user_id], type="clinic_referral",
                              title="قُبلت الإحالة", body=f"{current_user.full_name} قبل إحالة المريض {patient_name} ({r.referral_ref})",
                              link="/clinic?tab=referrals", data={"referral_id": r.id}, severity="success")
    await audit_log(db, "clinic_referral", "accept", current_user.id, current_user.full_name, None,
                    {"referral_ref": r.referral_ref, "patient_id": r.patient_id},
                    f"قبول الإحالة {r.referral_ref} وإضافة {current_user.full_name} إلى فريق رعاية المريض {patient_name}")
    await db.commit()
    return (await _rows_out(db, current_user, [r]))[0]


@router.post("/referrals/{referral_id}/decline")
async def decline_referral(
    referral_id: str,
    payload: ReferralResponse,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_doctor),
):
    if len(payload.note.strip()) < 3:
        raise HTTPException(status_code=400, detail="اذكر سبب الاعتذار عن الإحالة")
    r = await _respond(db, current_user, referral_id, "declined", payload.note)
    await access.notify_users(db, current_user.tenant_id, [r.from_doctor_user_id], type="clinic_referral",
                              title="اعتُذر عن الإحالة", body=f"{current_user.full_name}: {r.response_note} ({r.referral_ref})",
                              link="/clinic?tab=referrals", data={"referral_id": r.id}, severity="warning")
    await audit_log(db, "clinic_referral", "decline", current_user.id, current_user.full_name, None,
                    {"referral_ref": r.referral_ref, "note": r.response_note}, f"الاعتذار عن الإحالة {r.referral_ref}")
    await db.commit()
    return (await _rows_out(db, current_user, [r]))[0]


@router.post("/referrals/{referral_id}/complete")
async def complete_referral(
    referral_id: str,
    payload: ReferralResponse = ReferralResponse(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_clinic_doctor),
):
    r = await _referral_or_404(db, current_user.tenant_id, referral_id)
    if r.status != "accepted":
        raise HTTPException(status_code=409, detail="تُكمَل الإحالة المقبولة فقط")
    if current_user.id not in (r.to_doctor_user_id, r.from_doctor_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="يكمل الإحالة الطبيب المستقبل أو المحيل")
    r.status = "completed"
    if payload.note.strip():
        r.response_note = payload.note.strip()
    await audit_log(db, "clinic_referral", "complete", current_user.id, current_user.full_name, None,
                    {"referral_ref": r.referral_ref}, f"إكمال الإحالة {r.referral_ref}")
    await db.commit()
    return (await _rows_out(db, current_user, [r]))[0]
