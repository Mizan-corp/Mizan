"""Healthcare & Clinic/Hospital ERP: business logic.

Functions take the database session and plain values, do one business operation in one
transaction, and raise HTTPException with an Arabic message for the user. Routers and other
modules call these; they never reach into another module's tables.

Patient-level clinical access (#113): who may read and write a patient's clinical record.
- Clinical data (encounters, prescriptions, lab orders, allergies, chronic conditions, blood
  group) is read only by holders of clinic:doctor, clinic:nurse or clinic:all_patients; the
  umbrella "clinic" permission doesn't open it.
- clinic:all_patients, or the module setting patient_access = "all", opens every patient.
- Otherwise: active care-team membership, or an unexpired, unrevoked break-glass grant.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.healthcare.modules.healthcare_clinic.models import (
    ClinicAccessGrant,
    ClinicAccessLog,
    ClinicCareTeam,
)
from app.platform.permissions.access import can

CLINICIAN_PERMS = ("clinic:doctor", "clinic:nurse")
CLINICAL_READ_PERMS = (*CLINICIAN_PERMS, "clinic:all_patients")
CLINICAL_FIELDS = ("allergies", "chronic_conditions", "blood_group")
BREAK_GLASS_MINUTES = 60
NO_ACCESS = "لا تملك صلاحية الاطلاع على الملف الطبي لهذا المريض: لست ضمن فريق رعايته. في الحالات الطارئة استخدم «الوصول الطارئ» مع ذكر السبب، ويُسجَّل ذلك ويُراجع."


def is_clinician(user) -> bool:
    return can(user, *CLINICIAN_PERMS)


def reads_clinical(user) -> bool:
    return can(user, *CLINICAL_READ_PERMS)


def queue_reader(user, perm: str) -> bool:
    """Pharmacy and lab work queues: a non-clinician holding the queue permission sees every row of
    that queue. Clinicians (who often hold these too) go through their patient access."""
    return can(user, perm) and not is_clinician(user)


async def patient_access_setting(db: AsyncSession) -> str:
    from app.framework.loader import registry

    try:
        values = (await registry.get_settings(db, "healthcare_clinic"))["values"]
    except KeyError:
        return "team"
    return "all" if values.get("patient_access") == "all" else "team"


async def access_scope(db: AsyncSession, user) -> str | None:
    """'all' / 'setting' (every patient), 'team' (per patient), None (no clinical data)."""
    if not reads_clinical(user):
        return None
    if can(user, "clinic:all_patients"):
        return "all"
    if is_clinician(user) and await patient_access_setting(db) == "all":
        return "setting"
    return "team" if is_clinician(user) else None


def _team_ids(user):
    return select(ClinicCareTeam.patient_id).where(ClinicCareTeam.user_id == user.id, ClinicCareTeam.ended_at.is_(None))


def _grant_ids(user):
    return select(ClinicAccessGrant.patient_id).where(
        ClinicAccessGrant.user_id == user.id,
        ClinicAccessGrant.revoked_at.is_(None),
        ClinicAccessGrant.starts_at <= func.now(),
        ClinicAccessGrant.expires_at > func.now(),
    )


def accessible_condition(user, column):
    """SQL condition: the patient column is one this user reaches through team or break-glass."""
    return or_(column.in_(_team_ids(user)), column.in_(_grant_ids(user)))


async def access_by_patient(db: AsyncSession, user, patient_ids: list[str]) -> dict[str, str]:
    """{patient_id: how} for the patients this user reads clinically, among patient_ids."""
    scope = await access_scope(db, user)
    if scope is None or not patient_ids:
        return {}
    if scope in ("all", "setting"):
        return {pid: scope for pid in patient_ids}
    out: dict[str, str] = {}
    for pid in (await db.execute(_grant_ids(user).where(ClinicAccessGrant.patient_id.in_(patient_ids)))).scalars():
        out[pid] = "break_glass"
    for pid in (await db.execute(_team_ids(user).where(ClinicCareTeam.patient_id.in_(patient_ids)))).scalars():
        out[pid] = "team"
    return out


async def clinical_access(db: AsyncSession, user, patient_id: str) -> str | None:
    """How this user reads the patient's clinical record: 'all', 'setting', 'team', 'break_glass' or None."""
    return (await access_by_patient(db, user, [patient_id])).get(patient_id)


async def require_clinical_access(db: AsyncSession, user, patient_id: str) -> str:
    how = await clinical_access(db, user, patient_id)
    if not how:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NO_ACCESS)
    return how


async def log_access(db: AsyncSession, user, resource: str, how: str, patient_id: str | None = None, rows: int = 0) -> None:
    db.add(ClinicAccessLog(
        tenant_id=user.tenant_id, user_id=user.id, user_name=(user.full_name or user.username or "")[:128],
        patient_id=patient_id, resource=resource, how=how, rows=rows,
    ))
    await db.commit()


async def clinicians(db: AsyncSession, tenant_id, user_id=None, department_id: str | None = None) -> list[dict]:
    """Active users of the workspace whose roles hold clinic:doctor or clinic:nurse; with a
    department, only those on its active roster (#36)."""
    rows = (await db.execute(text("""
        SELECT u.id, u.full_name, u.username,
               string_agg(DISTINCT r.name, '، ') AS role_name,
               bool_or(r.grants ? 'clinic:doctor') AS is_doctor
        FROM users u
        JOIN user_role_assignments a ON a.user_id = u.id AND a.is_active
        JOIN sys_roles r ON r.id = a.role_id
        WHERE u.tenant_id = :t AND u.is_active
          AND (r.grants ? 'clinic:doctor' OR r.grants ? 'clinic:nurse')
          AND (CAST(:u AS uuid) IS NULL OR u.id = CAST(:u AS uuid))
          AND (CAST(:d AS text) IS NULL OR EXISTS (
                SELECT 1 FROM clinic_doctor_schedules s
                WHERE s.doctor_user_id = u.id AND s.department_id = CAST(:d AS text) AND s.active))
        GROUP BY u.id, u.full_name, u.username
        ORDER BY u.full_name
    """), {"t": tenant_id, "u": str(user_id) if user_id else None, "d": department_id})).mappings().all()
    return [{"id": str(r["id"]), "full_name": r["full_name"] or r["username"], "role": r["role_name"],
             "is_doctor": bool(r["is_doctor"])} for r in rows]


async def clinician(db: AsyncSession, tenant_id, user_id) -> dict:
    try:
        uid = uuid.UUID(str(user_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="المستخدم المختار غير صالح")
    found = await clinicians(db, tenant_id, uid)
    if not found:
        raise HTTPException(status_code=400, detail="المستخدم المختار ليس طبيباً أو ممرضاً في مساحة العمل")
    return found[0]


async def refuse_self_assignment(db: AsyncSession, actor, patient_id: str, user_id) -> None:
    """Joining a care team opens the record, so a clinician can't add themselves to a patient they
    don't already reach (that is what break-glass is for); someone else assigns them."""
    if str(user_id) == str(actor.id) and not await clinical_access(db, actor, patient_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="لا يمكنك إضافة نفسك إلى فريق رعاية مريض لا تملك الوصول إلى ملفه؛ يضيفك موظف الاستقبال أو الإدارة، أو استخدم «الوصول الطارئ»")


async def add_to_care_team(db: AsyncSession, tenant_id, patient_id: str, user_id, role: str, added_by) -> ClinicCareTeam | None:
    """Adds the member unless already active on the team (returns None then). Doesn't commit."""
    existing = (await db.execute(select(ClinicCareTeam).where(
        ClinicCareTeam.patient_id == patient_id, ClinicCareTeam.user_id == user_id, ClinicCareTeam.ended_at.is_(None),
    ))).scalar_one_or_none()
    if existing:
        return None
    member = ClinicCareTeam(tenant_id=tenant_id, patient_id=patient_id, user_id=user_id, role=role, added_by=added_by)
    db.add(member)
    await db.flush()
    return member


async def notify_privacy_officers(db: AsyncSession, tenant_id, title: str, body: str, data: dict) -> None:
    """An in-app notification to every user whose roles hold clinic:privacy. Doesn't commit."""
    from app.platform.notifications.models.notification import Notification

    ids = (await db.execute(text("""
        SELECT DISTINCT u.id FROM users u
        JOIN user_role_assignments a ON a.user_id = u.id AND a.is_active
        JOIN sys_roles r ON r.id = a.role_id
        WHERE u.tenant_id = :t AND u.is_active AND r.grants ? 'clinic:privacy'
    """), {"t": tenant_id})).scalars().all()
    for uid in ids:
        db.add(Notification(tenant_id=tenant_id, user_id=uid, type="clinic_break_glass", severity="warning",
                            title=title, body=body, link="/clinic?tab=privacy", data_json=data, is_read=False))


async def notify_users(db: AsyncSession, tenant_id, user_ids, *, type: str, title: str, body: str, link: str,
                       data: dict, severity: str = "info") -> None:
    """An in-app notification to each of these users. Doesn't commit."""
    from app.platform.notifications.models.notification import Notification

    for uid in {u for u in user_ids if u}:
        db.add(Notification(tenant_id=tenant_id, user_id=uid, type=type, severity=severity,
                            title=title, body=body, link=link, data_json=data, is_read=False))
