"""The patient's chart beyond the encounter list: vitals trends (#42). Every read here is clinical:
it needs access to the patient's record (service.require_clinical_access) and is logged."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.healthcare.modules.healthcare_clinic import service as access
from app.activities.healthcare.modules.healthcare_clinic.models import ClinicEncounter, ClinicLabOrder, ClinicPatient
from app.db.base import get_db
from app.dependencies import get_current_user
from app.platform.auth.models.user import User

router = APIRouter()

GLUCOSE_TESTS = ("%glucose%", "%سكر%", "%FBS%", "%RBS%", "%blood sugar%")


async def patient_or_404(db: AsyncSession, tenant_id, patient_id: str) -> ClinicPatient:
    patient = (await db.execute(select(ClinicPatient).where(
        ClinicPatient.id == patient_id, ClinicPatient.tenant_id == tenant_id))).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="الملف الطبي للمريض غير موجود")
    return patient


def _day(value: str | None, fallback) -> str:
    """The encounter's date as YYYY-MM-DD (encounter_date is free text; its creation date otherwise)."""
    try:
        return date.fromisoformat((value or "")[:10]).isoformat()
    except ValueError:
        return fallback.date().isoformat() if fallback else ""


def _num(value) -> float | None:
    """A vital only when it was really measured: 0 or empty means not recorded."""
    return float(value) if value not in (None, "") and float(value) > 0 else None


@router.get("/patients/{patient_id}/vitals-history")
async def vitals_history(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per encounter, oldest first: blood pressure, heart rate, SpO2, temperature and blood glucose;
    plus blood glucose results from the lab (reported, numeric). For the trend charts."""
    patient = await patient_or_404(db, current_user.tenant_id, patient_id)
    how = await access.require_clinical_access(db, current_user, patient.id)
    encounters = (await db.execute(select(ClinicEncounter).where(
        ClinicEncounter.tenant_id == current_user.tenant_id, ClinicEncounter.patient_id == patient.id,
    ).order_by(ClinicEncounter.created_at))).scalars().all()
    points = sorted(({
        "encounter_id": e.id, "encounter_ref": e.encounter_ref, "date": _day(e.encounter_date, e.created_at),
        "bp_systolic": _num(e.bp_systolic), "bp_diastolic": _num(e.bp_diastolic), "heart_rate": _num(e.heart_rate),
        "spo2": _num(e.spo2), "temperature": _num(e.temperature), "blood_glucose": _num(e.blood_glucose),
    } for e in encounters), key=lambda p: p["date"])
    labs = (await db.execute(select(ClinicLabOrder).where(
        ClinicLabOrder.tenant_id == current_user.tenant_id, ClinicLabOrder.patient_id == patient.id,
        ClinicLabOrder.status == "reported", ClinicLabOrder.numeric_value.is_not(None),
        or_(*[ClinicLabOrder.test_name.ilike(t) for t in GLUCOSE_TESTS]),
    ).order_by(ClinicLabOrder.created_at))).scalars().all()
    glucose_labs = [{"order_ref": lab.order_ref, "test_name": lab.test_name, "value": lab.numeric_value, "unit": lab.unit,
                     "date": (lab.signed_off_at or lab.collected_at or lab.created_at).date().isoformat()} for lab in labs]
    await access.log_access(db, current_user, "vitals", how, patient.id, len(points) + len(glucose_labs))
    return {"patient_id": patient.id, "patient_name": patient.full_name, "points": points, "glucose_labs": glucose_labs}
