"""API Router for Healthcare & Clinic/Hospital ERP module (HLT-01..12)."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework.activation import require_module
from app.db.base import get_db
from app.dependencies import get_current_user
from app.activities.general.modules.inventory.models.product import Category, Product
from app.activities.general.modules.sales.models.sale import Sale, SaleItem, SaleMode, SaleStatus
from app.activities.general.modules.sales.services.sales import _add_payment as add_sale_payment
from app.activities.general.modules.pos.models import DrawerTransaction, DrawerTxType, Shift, ShiftStatus
from app.platform.auth.models.user import User
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.platform.audit.service import log as audit_log
from app.platform.permissions.access import can
from app.activities.healthcare.modules.healthcare_clinic.models import (
    ClinicAccessGrant,
    ClinicAccessLog,
    ClinicAppointment,
    ClinicCareTeam,
    ClinicEncounter,
    ClinicInpatientBed,
    ClinicInsuranceClaim,
    ClinicInvoice,
    ClinicLabOrder,
    ClinicPatient,
    ClinicPrescription,
)
from app.activities.healthcare.modules.healthcare_clinic.schemas import (
    BreakGlassRequest,
    BreakGlassReview,
    CareTeamAdd,
)
from app.activities.healthcare.modules.healthcare_clinic import service as access


async def get_current_tenant_id(user: User = Depends(get_current_user)) -> uuid.UUID:
    return user.tenant_id


# ─── RBAC / ABAC Permissions Enforcement ───────────────────────────────────
# Each helper checks the permission its name says (#131). The umbrella "clinic" (admin, manager)
# passes them all; the standard clinical roles don't hold it. Patient-level access to clinical
# data is separate and never follows the umbrella (service.py, #113).
def _has_clinic_perm(user: User, *perms: str) -> bool:
    """With no specific permission asked, 'clinic:view' is enough."""
    granted = getattr(user, "effective_permissions", frozenset())
    if "clinic" in granted:
        return True
    if not perms:
        return "clinic:view" in granted
    return any(p in granted for p in perms)


def _clinic_guard(*perms: str, detail: str):
    async def guard(current_user: User = Depends(get_current_user)) -> User:
        if not _has_clinic_perm(current_user, *perms):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        return current_user
    return guard


# Everyone in the clinic: the patient list (demographics), appointments, beds, summary.
require_clinic_view = _clinic_guard(detail="لا تملك صلاحية الوصول إلى العيادات")
# Front desk: register and edit patients, cancel and reschedule, care teams.
require_clinic_manage = _clinic_guard("clinic:manage", detail="لا تملك صلاحية إدارة المواعيد وملفات المرضى (clinic:manage)")
# Booking: the front desk, and doctors booking follow-ups.
require_clinic_booking = _clinic_guard("clinic:manage", "clinic:doctor", detail="لا تملك صلاحية حجز المواعيد")
# Moving a patient through the queue (waiting, in consultation, completed).
require_clinic_queue = _clinic_guard("clinic:manage", "clinic:doctor", "clinic:nurse",
                                     detail="لا تملك صلاحية تحديث حالة الموعد في قائمة الانتظار")
# Examining, prescribing and ordering tests.
require_clinic_doctor = _clinic_guard("clinic:doctor", detail="لا تملك صلاحية الطبيب السريري (clinic:doctor)")
# The ward: admitting, discharging and readying beds.
require_clinic_ward = _clinic_guard("clinic:nurse", "clinic:manage", detail="لا تملك صلاحية إدارة أسرّة التنويم (clinic:nurse)")
require_clinic_dispense = _clinic_guard("clinic:dispense", detail="لا تملك صلاحية صرف الأدوية والصيدلية (clinic:dispense)")
# Recording and signing off lab results.
require_clinic_lab = _clinic_guard("clinic:lab", detail="لا تملك صلاحية تسجيل نتائج المختبر (clinic:lab)")
require_clinic_billing = _clinic_guard("clinic:billing", detail="لا تملك صلاحية فواتير العيادة (clinic:billing)")


logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/clinic",
    tags=["Healthcare & Clinic ERP"],
    dependencies=[Depends(require_clinic_view), Depends(require_module("healthcare_clinic"))],
)


# ─── Pydantic Schemas ────────────────────────────────────────────────────────
class PatientCreate(BaseModel):
    patient_mrn: str
    full_name: str
    national_id: str
    phone: str
    gender: str
    date_of_birth: str
    blood_group: str = "A+"
    allergies: str = "لا توجد حساسيات مسجلة"
    chronic_conditions: str = "لا توجد أمراض مزمنة"
    insurance_provider: str = "نقدي / غير مؤمن"
    insurance_policy_no: str = "N/A"
    copay_percent: float = 0.0


class PatientUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    blood_group: str | None = None
    allergies: str | None = None
    chronic_conditions: str | None = None
    insurance_provider: str | None = None
    insurance_policy_no: str | None = None
    copay_percent: float | None = None


class AppointmentCreate(BaseModel):
    patient_id: str
    patient_name: str = ""
    doctor_user_id: str | None = None
    doctor_name: str = ""
    department: str
    appointment_date: str
    time_slot: str
    consultation_fee: float = 250.0
    chief_complaint: str = ""


class AppointmentStatusUpdate(BaseModel):
    status: str  # scheduled, waiting, in_consultation, completed, cancelled, no_show


class AppointmentCancelRequest(BaseModel):
    reason: str = Field(..., min_length=2, description="سبب إلغاء الموعد")


class AppointmentRescheduleRequest(BaseModel):
    new_date: str = Field(..., description="تاريخ الموعد الجديد YYYY-MM-DD")
    new_time_slot: str = Field(..., description="الوقت الجديد للموعد")


class EncounterCreate(BaseModel):
    patient_id: str
    patient_name: str
    doctor_name: str
    department: str
    encounter_date: str
    bp_systolic: int = 120
    bp_diastolic: int = 80
    heart_rate: int = 72
    temperature: float = 37.0
    spo2: int = 98
    chief_complaint: str
    icd10_code: str
    icd10_description: str
    clinical_notes: str


class PrescriptionCreate(BaseModel):
    encounter_ref: str = ""
    patient_id: str
    patient_name: str
    doctor_name: str
    issue_date: str
    medication_name: str
    dosage: str
    frequency: str
    duration_days: int = 7
    quantity: int = 1
    instructions: str = ""
    allergy_override: bool = False


class PrescriptionDispenseRequest(BaseModel):
    quantity: int = 1
    notes: str | None = None


class LabOrderCreate(BaseModel):
    patient_id: str
    patient_name: str
    doctor_name: str
    test_name: str
    category: str
    specimen_barcode: str
    reference_range: str = "Normal"
    test_fee: float = 150.0


class LabResultUpdate(BaseModel):
    result_value: str
    numeric_value: float | None = None
    unit: str = ""
    is_critical: bool = False
    is_signed_off: bool = True


class BedAdmitRequest(BaseModel):
    patient_id: str | None = None
    patient_name: str
    admission_date: str


class InvoiceCreate(BaseModel):
    patient_id: str
    patient_name: str
    appointment_id: str | None = None
    encounter_ref: str = ""
    charges: list[dict[str, Any]]  # [{description, amount}]
    copay_percent: float = 0.0


class InvoicePayRequest(BaseModel):
    amount: float
    payment_method: str = "cash"


class ClaimCreate(BaseModel):
    patient_id: str
    patient_name: str
    invoice_id: str | None = None
    insurance_provider: str
    policy_no: str = "N/A"
    copay_percent: float = 0.0
    claimed_amount: float
    notes: str = ""


class ClaimStatusUpdate(BaseModel):
    status: str  # submitted, approved, rejected, paid
    approved_amount: float | None = None
    notes: str = ""


# ─── Internal Financial & Billing Integration Helpers ───────────────────────
async def _ensure_insurance_claim(
    db: AsyncSession,
    tenant_id: str,
    patient: ClinicPatient,
    invoice: ClinicInvoice,
    current_user: User,
) -> ClinicInsuranceClaim | None:
    """Auto-generate an insurance claim if the invoice has an insurance covered amount."""
    if invoice.insurance_amount <= 0 or not patient.insurance_provider or "نقدي" in patient.insurance_provider:
        return None

    # Check if a claim already exists for this invoice
    existing = await db.execute(
        select(ClinicInsuranceClaim).where(
            ClinicInsuranceClaim.invoice_id == invoice.id,
            ClinicInsuranceClaim.tenant_id == tenant_id,
        )
    )
    if existing.scalar_one_or_none():
        return None

    claim = ClinicInsuranceClaim(
        tenant_id=tenant_id,
        claim_ref=f"CLM-{uuid.uuid4().hex[:6].upper()}",
        patient_id=patient.id,
        patient_name=patient.full_name,
        invoice_id=invoice.id,
        insurance_provider=patient.insurance_provider,
        policy_no=patient.insurance_policy_no or "N/A",
        copay_percent=patient.copay_percent,
        claimed_amount=invoice.insurance_amount,
        approved_amount=0.0,
        status="submitted",
        created_by=current_user.full_name,
        notes=f"مطالبة تأمينية تلقائية لفاتورة الخدمات رقم {invoice.invoice_ref}",
    )
    db.add(claim)
    await audit_log(
        db,
        "clinic_insurance_claim",
        "create_auto_claim",
        current_user.id,
        current_user.full_name,
        None,
        {"claim_ref": claim.claim_ref, "claimed_amount": invoice.insurance_amount},
        f"إنشاء مطالبة تأمينية تلقائية {claim.claim_ref}",
    )
    return claim


async def _record_invoice_payment(
    db: AsyncSession,
    tenant_id: str,
    inv: ClinicInvoice,
    amount: Decimal,
    method: str,
    current_user: User,
) -> Sale | None:
    """A clinic invoice is one sale (the patient's share), made at its first payment; every payment
    is a payment line on it, and cash goes into the cashier's open drawer as at the POS (ADR-014 D4)."""
    try:
        t_uuid = uuid.UUID(str(tenant_id))
    except Exception:
        return None

    sale = await db.get(Sale, inv.sale_id) if inv.sale_id else None
    if sale is None:
        sale = await _invoice_sale(db, t_uuid, inv, current_user)
        inv.sale_id = sale.id
    sale.paid_amount = (sale.paid_amount or Decimal("0")) + amount
    sale.last_paid_at = datetime.now(UTC)
    await add_sale_payment(db, sale.id, method, amount)
    if method == "cash":
        shift = (await db.execute(
            select(Shift).where(
                Shift.warehouse_id == sale.warehouse_id, Shift.cashier_id == current_user.id,
                Shift.status == ShiftStatus.open,
            ).order_by(Shift.started_at.desc()).limit(1)
        )).scalar_one_or_none()
        if shift:
            db.add(DrawerTransaction(shift_id=shift.id, type=DrawerTxType.sale, amount=amount, ref_id=sale.id,
                                     created_by=current_user.id, note=f"سداد فاتورة {inv.invoice_ref}"))
            if not sale.shift_id:
                sale.shift_id = shift.id
    return sale


async def _invoice_sale(db: AsyncSession, t_uuid: uuid.UUID, inv: ClinicInvoice, current_user: User) -> Sale:

    # Find tenant warehouse
    wh = (await db.execute(
        select(Warehouse).where(Warehouse.tenant_id == t_uuid).order_by(Warehouse.created_at.asc()).limit(1)
    )).scalar_one_or_none()
    if not wh:
        wh = Warehouse(tenant_id=t_uuid, code=f"WH-{uuid.uuid4().hex[:4].upper()}", name="المستودع الطبي الرئيسي", is_active=True)
        db.add(wh)
        await db.flush()

    # Find or create a Service Product for Medical Services
    prod = (await db.execute(
        select(Product).where(Product.tenant_id == t_uuid, Product.name == "خدمات واستشارات طبية").limit(1)
    )).scalar_one_or_none()
    if not prod:
        cat = (await db.execute(
            select(Category).where(Category.tenant_id == t_uuid).limit(1)
        )).scalar_one_or_none()
        if not cat:
            cat = Category(tenant_id=t_uuid, name="الخدمات الطبية والسريرية")
            db.add(cat)
            await db.flush()
        prod = Product(
            tenant_id=t_uuid,
            name="خدمات واستشارات طبية",
            code="SRV-MED-01",
            unit="خدمة",
            retail_price=Decimal("0.0"),
            wholesale_price=Decimal("0.0"),
        )
        db.add(prod)
        await db.flush()

    sale = Sale(
        tenant_id=t_uuid,
        invoice_number=inv.invoice_ref,
        warehouse_id=wh.id,
        cashier_id=current_user.id,
        created_by=current_user.id,
        sale_mode=SaleMode.retail,
        status=SaleStatus.confirmed,
        total=Decimal(str(round(inv.total, 2))),
        discount_amount=Decimal("0.0"),
        net_total=Decimal(str(round(inv.patient_amount, 2))),
        paid_amount=Decimal("0"),
        payment_method=inv.payment_method or "cash",
        notes=f"سداد فاتورة عيادات/مستشفى — المريض: {inv.patient_name} — {inv.invoice_ref}",
    )
    db.add(sale)
    await db.flush()

    # Add charges as sale items
    for c in inv.charges:
        amt = Decimal(str(round(float(c.get("amount", 0.0)), 2)))
        si = SaleItem(
            tenant_id=t_uuid,
            sale_id=sale.id,
            product_id=prod.id,
            qty=Decimal("1.0"),
            unit_price=amt,
            unit_cost=Decimal("0.0"),
            discount=Decimal("0.0"),
        )
        db.add(si)

    return sale


# ─── Summary / KPIs ─────────────────────────────────────────────────────────
@router.get("/summary")
async def get_clinic_summary(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Overview operational & financial KPIs for Clinic / Hospital operations."""
    today = date.today().isoformat()

    patients_count = (await db.execute(
        select(func.count(ClinicPatient.id)).where(ClinicPatient.tenant_id == tenant_id)
    )).scalar() or 0

    appts_today = (await db.execute(
        select(func.count(ClinicAppointment.id)).where(
            ClinicAppointment.tenant_id == tenant_id,
            ClinicAppointment.appointment_date == today,
        )
    )).scalar() or 0

    waiting_queue = (await db.execute(
        select(func.count(ClinicAppointment.id)).where(
            ClinicAppointment.tenant_id == tenant_id,
            ClinicAppointment.appointment_date == today,
            ClinicAppointment.status.in_(["waiting", "in_consultation"]),
        )
    )).scalar() or 0

    total_beds = (await db.execute(
        select(func.count(ClinicInpatientBed.id)).where(ClinicInpatientBed.tenant_id == tenant_id)
    )).scalar() or 0

    occupied_beds = (await db.execute(
        select(func.count(ClinicInpatientBed.id)).where(
            ClinicInpatientBed.tenant_id == tenant_id,
            ClinicInpatientBed.status == "occupied",
        )
    )).scalar() or 0

    pending_labs = (await db.execute(
        select(func.count(ClinicLabOrder.id)).where(
            ClinicLabOrder.tenant_id == tenant_id,
            ClinicLabOrder.status != "reported",
        )
    )).scalar() or 0

    # Financial Aggregations
    invoices_q = await db.execute(
        select(
            func.coalesce(func.sum(ClinicInvoice.total), 0.0),
            func.coalesce(func.sum(ClinicInvoice.paid_amount), 0.0),
            func.coalesce(func.sum(ClinicInvoice.patient_amount), 0.0),
        ).where(ClinicInvoice.tenant_id == tenant_id)
    )
    total_billed, total_paid, total_patient_share = invoices_q.one()

    claims_q = await db.execute(
        select(
            func.coalesce(func.sum(ClinicInsuranceClaim.claimed_amount), 0.0),
            func.coalesce(func.sum(ClinicInsuranceClaim.approved_amount), 0.0),
            func.count(ClinicInsuranceClaim.id),
        ).where(ClinicInsuranceClaim.tenant_id == tenant_id)
    )
    total_claimed, total_approved, total_claims_count = claims_q.one()

    bed_occupancy_pct = round((occupied_beds / total_beds) * 100) if total_beds > 0 else 0

    operational = {
        "total_registered_patients": patients_count,
        "today_appointments_count": appts_today,
        "waiting_queue_count": waiting_queue,
        "total_beds": total_beds,
        "occupied_beds": occupied_beds,
        "bed_occupancy_percent": bed_occupancy_pct,
        "pending_lab_orders_count": pending_labs,
    }
    if not _has_clinic_perm(current_user, "clinic:billing"):
        return operational  # the money figures are billing's
    return {
        **operational,
        "total_revenue_billed": round(float(total_billed), 2),
        "total_revenue_collected": round(float(total_paid), 2),
        "total_revenue_pending": round(float(total_patient_share - total_paid), 2),
        "insurance_claims_total": round(float(total_claimed), 2),
        "insurance_claims_approved": round(float(total_approved), 2),
        "insurance_claims_count": total_claims_count,
    }


# ─── Patient-level clinical access (#113) ───────────────────────────────────
def _row(obj) -> dict[str, Any]:
    return {c.key: getattr(obj, c.key) for c in obj.__mapper__.column_attrs}


def _patient_out(patient: ClinicPatient, how: str | None) -> dict[str, Any]:
    """The patient's demographics for everyone in the clinic; clinical fields only with access."""
    out = _row(patient)
    if not how:
        for f in access.CLINICAL_FIELDS:
            out[f] = None
    out["clinical_access"] = bool(how)
    out["access"] = how
    return out


async def _clinical_list(db: AsyncSession, user: User, model, resource: str, patient_id: str | None,
                         queue_perm: str | None, filters: list, limit: int, offset: int) -> list:
    """A clinical list: one patient's rows (with access), the rows of the patients the user reaches,
    or a whole work queue (pharmacy, lab). Every read that returns rows is logged."""
    query = select(model).where(model.tenant_id == user.tenant_id, *filters)
    if queue_perm and access.queue_reader(user, queue_perm):
        how = "queue"
    elif patient_id:
        how = await access.require_clinical_access(db, user, patient_id)
    else:
        how = await access.access_scope(db, user)
        if how is None:
            return []
        if how == "team":
            query = query.where(access.accessible_condition(user, model.patient_id))
    if patient_id:
        query = query.where(model.patient_id == patient_id)
    rows = (await db.execute(query.order_by(model.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    if rows or patient_id:
        await access.log_access(db, user, resource, how, patient_id, len(rows))
    return list(rows)


async def _get_patient_or_404(db: AsyncSession, tenant_id, patient_id: str) -> ClinicPatient:
    patient = (await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == patient_id, ClinicPatient.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="الملف الطبي للمريض غير موجود")
    return patient


def _require_privacy(user: User) -> None:
    if not can(user, "clinic:privacy"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="لا تملك صلاحية مسؤول الخصوصية الطبية (clinic:privacy)")


@router.get("/clinicians")
async def list_clinicians(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Users of the workspace who act clinically (clinic:doctor or clinic:nurse), for booking and care teams."""
    return await access.clinicians(db, current_user.tenant_id)


@router.post("/patients/{patient_id}/break-glass")
async def break_glass(
    patient_id: str,
    payload: BreakGlassRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not access.is_clinician(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="الوصول الطارئ متاح للأطباء وطاقم التمريض فقط")
    reason = payload.reason.strip()
    if len(reason) < 10:
        raise HTTPException(status_code=400, detail="اذكر سبب الوصول الطارئ بوضوح (10 أحرف على الأقل)")
    patient = await _get_patient_or_404(db, current_user.tenant_id, patient_id)
    now = datetime.now(UTC)
    grant = ClinicAccessGrant(
        tenant_id=current_user.tenant_id, patient_id=patient.id, user_id=current_user.id, reason=reason,
        starts_at=now, expires_at=now + timedelta(minutes=access.BREAK_GLASS_MINUTES),
    )
    db.add(grant)
    await db.flush()
    await audit_log(
        db, "clinic_access_grant", "break_glass", current_user.id, current_user.full_name, None,
        {"grant_id": grant.id, "patient_id": patient.id, "reason": reason, "expires_at": grant.expires_at.isoformat()},
        f"وصول طارئ إلى الملف الطبي للمريض {patient.full_name} — السبب: {reason}",
    )
    await access.notify_privacy_officers(
        db, current_user.tenant_id, "وصول طارئ إلى ملف طبي",
        f"{current_user.full_name} فتح الملف الطبي للمريض {patient.full_name} بالوصول الطارئ. السبب: {reason}",
        {"grant_id": grant.id, "patient_id": patient.id},
    )
    await db.commit()
    return {"id": grant.id, "patient_id": patient.id, "expires_at": grant.expires_at,
            "detail": f"تم فتح الملف الطبي لمدة {access.BREAK_GLASS_MINUTES} دقيقة، ويُسجَّل الوصول ويُراجع"}


@router.get("/patients/{patient_id}/care-team")
async def list_care_team(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_patient_or_404(db, current_user.tenant_id, patient_id)
    if not _has_clinic_perm(current_user, "clinic:manage"):
        await access.require_clinical_access(db, current_user, patient_id)
    rows = (await db.execute(
        select(ClinicCareTeam, User.full_name, User.username)
        .join(User, User.id == ClinicCareTeam.user_id)
        .where(ClinicCareTeam.patient_id == patient_id, ClinicCareTeam.tenant_id == current_user.tenant_id,
               ClinicCareTeam.ended_at.is_(None))
        .order_by(ClinicCareTeam.created_at)
    )).all()
    return [{"id": m.id, "user_id": str(m.user_id), "full_name": name or username, "role": m.role,
             "created_at": m.created_at} for m, name, username in rows]


@router.post("/patients/{patient_id}/care-team")
async def add_care_team_member(
    patient_id: str,
    payload: CareTeamAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_manage),
):
    patient = await _get_patient_or_404(db, current_user.tenant_id, patient_id)
    person = await access.clinician(db, current_user.tenant_id, payload.user_id)
    await access.refuse_self_assignment(db, current_user, patient.id, person["id"])
    member = await access.add_to_care_team(db, current_user.tenant_id, patient.id, uuid.UUID(person["id"]),
                                           payload.role, current_user.id)
    if not member:
        raise HTTPException(status_code=409, detail="هذا المستخدم ضمن فريق رعاية المريض بالفعل")
    await audit_log(
        db, "clinic_care_team", "add_member", current_user.id, current_user.full_name, None,
        {"patient_id": patient.id, "user_id": person["id"], "role": payload.role},
        f"إضافة {person['full_name']} إلى فريق رعاية المريض {patient.full_name}",
    )
    await db.commit()
    return {"id": member.id, "user_id": person["id"], "full_name": person["full_name"], "role": member.role,
            "created_at": member.created_at}


@router.delete("/patients/{patient_id}/care-team/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_care_team_member(
    patient_id: str,
    member_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_manage),
):
    patient = await _get_patient_or_404(db, current_user.tenant_id, patient_id)
    member = (await db.execute(select(ClinicCareTeam).where(
        ClinicCareTeam.id == member_id, ClinicCareTeam.patient_id == patient.id,
        ClinicCareTeam.tenant_id == current_user.tenant_id, ClinicCareTeam.ended_at.is_(None),
    ))).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="العضو غير موجود في فريق رعاية المريض")
    member.ended_at = datetime.now(UTC)
    await audit_log(
        db, "clinic_care_team", "remove_member", current_user.id, current_user.full_name, None,
        {"patient_id": patient.id, "user_id": str(member.user_id), "member_id": member.id},
        f"إزالة عضو من فريق رعاية المريض {patient.full_name}",
    )
    await db.commit()


@router.get("/access-log")
async def list_access_log(
    patient_id: str | None = None,
    user_id: uuid.UUID | None = None,
    since: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_privacy(current_user)
    query = (
        select(ClinicAccessLog, ClinicPatient.full_name)
        .outerjoin(ClinicPatient, ClinicPatient.id == ClinicAccessLog.patient_id)
        .where(ClinicAccessLog.tenant_id == current_user.tenant_id)
    )
    if patient_id:
        query = query.where(ClinicAccessLog.patient_id == patient_id)
    if user_id:
        query = query.where(ClinicAccessLog.user_id == user_id)
    if since:
        query = query.where(ClinicAccessLog.created_at >= since)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (await db.execute(query.order_by(ClinicAccessLog.created_at.desc()).offset(offset).limit(limit))).all()
    return {"total": total or 0, "items": [{**_row(r), "patient_name": name} for r, name in rows]}


@router.get("/break-glass")
async def list_break_glass(
    unreviewed: bool = False,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_privacy(current_user)
    query = (
        select(ClinicAccessGrant, ClinicPatient.full_name, User.full_name)
        .join(ClinicPatient, ClinicPatient.id == ClinicAccessGrant.patient_id)
        .join(User, User.id == ClinicAccessGrant.user_id)
        .where(ClinicAccessGrant.tenant_id == current_user.tenant_id)
    )
    if unreviewed:
        query = query.where(ClinicAccessGrant.reviewed_at.is_(None))
    rows = (await db.execute(query.order_by(ClinicAccessGrant.starts_at.desc()).offset(offset).limit(limit))).all()
    now = datetime.now(UTC)

    def state(g: ClinicAccessGrant) -> str:
        if g.revoked_at:
            return "revoked"
        return "active" if g.expires_at > now else "expired"

    return [{**_row(g), "patient_name": patient_name, "user_name": user_name, "state": state(g)}
            for g, patient_name, user_name in rows]


async def _grant_or_404(db: AsyncSession, tenant_id, grant_id: str) -> ClinicAccessGrant:
    grant = (await db.execute(select(ClinicAccessGrant).where(
        ClinicAccessGrant.id == grant_id, ClinicAccessGrant.tenant_id == tenant_id,
    ))).scalar_one_or_none()
    if not grant:
        raise HTTPException(status_code=404, detail="طلب الوصول الطارئ غير موجود")
    return grant


@router.post("/break-glass/{grant_id}/review")
async def review_break_glass(
    grant_id: str,
    payload: BreakGlassReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_privacy(current_user)
    grant = await _grant_or_404(db, current_user.tenant_id, grant_id)
    grant.reviewed_by = current_user.id
    grant.reviewed_at = datetime.now(UTC)
    grant.review_note = payload.note.strip() or None
    await audit_log(
        db, "clinic_access_grant", "review", current_user.id, current_user.full_name, None,
        {"grant_id": grant.id, "note": grant.review_note}, "مراجعة وصول طارئ إلى ملف طبي",
    )
    await db.commit()
    return _row(grant)


@router.post("/break-glass/{grant_id}/revoke")
async def revoke_break_glass(
    grant_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_privacy(current_user)
    grant = await _grant_or_404(db, current_user.tenant_id, grant_id)
    if not grant.revoked_at:
        grant.revoked_at = datetime.now(UTC)
        await audit_log(
            db, "clinic_access_grant", "revoke", current_user.id, current_user.full_name, None,
            {"grant_id": grant.id}, "إلغاء وصول طارئ إلى ملف طبي",
        )
        await db.commit()
    return _row(grant)


# ─── Patients Master Index (EMR) ────────────────────────────────────────────
MAX_PAGE_SIZE = 100


async def _page(db: AsyncSession, query, page: int, page_size: int) -> tuple[list, int, int]:
    """One page of a list query: (rows, total, pages)."""
    total = await db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return list(rows), total, max(1, -(-total // page_size))


@router.get("/patients")
async def list_patients(
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """A page of the patient index, searched by name, MRN, national id or phone (#39). Clinical
    fields only where the user reaches the patient; the rows read clinically are logged (#113)."""
    query = select(ClinicPatient).where(ClinicPatient.tenant_id == tenant_id)
    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.where(
            or_(
                ClinicPatient.full_name.ilike(s),
                ClinicPatient.patient_mrn.ilike(s),
                ClinicPatient.national_id.ilike(s),
                ClinicPatient.phone.ilike(s),
            )
        )
    query = query.order_by(ClinicPatient.created_at.desc(), ClinicPatient.id)
    patients, total, pages = await _page(db, query, page, page_size)
    reach = await access.access_by_patient(db, current_user, [p.id for p in patients])
    if reach:
        hows = set(reach.values())
        await access.log_access(db, current_user, "patient", hows.pop() if len(hows) == 1 else "team", None, len(reach))
    return {"items": [_patient_out(p, reach.get(p.id)) for p in patients], "total": total, "page": page, "pages": pages}


@router.post("/patients")
async def create_patient(
    payload: PatientCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_manage),
):
    # Check for MRN duplication within tenant
    dup = (await db.execute(
        select(ClinicPatient).where(
            ClinicPatient.tenant_id == tenant_id,
            ClinicPatient.patient_mrn == payload.patient_mrn,
        )
    )).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=400, detail=f"رقم الملف الطبي {payload.patient_mrn} مسجل مسبقاً")

    patient = ClinicPatient(
        tenant_id=tenant_id,
        patient_mrn=payload.patient_mrn,
        full_name=payload.full_name,
        national_id=payload.national_id,
        phone=payload.phone,
        gender=payload.gender,
        date_of_birth=payload.date_of_birth,
        blood_group=payload.blood_group,
        allergies=payload.allergies,
        chronic_conditions=payload.chronic_conditions,
        insurance_provider=payload.insurance_provider,
        insurance_policy_no=payload.insurance_policy_no,
        copay_percent=payload.copay_percent,
        created_by=current_user.full_name,
    )
    db.add(patient)
    await audit_log(
        db,
        "clinic_patient",
        "create_patient",
        current_user.id,
        current_user.full_name,
        None,
        {"patient_mrn": patient.patient_mrn, "full_name": patient.full_name},
        f"تسجيل مريض جديد: {patient.full_name} ({patient.patient_mrn})",
    )
    if access.is_clinician(current_user):
        # A clinician registering a patient is caring for them.
        await db.flush()
        await access.add_to_care_team(db, tenant_id, patient.id, current_user.id,
                                      "attending" if can(current_user, "clinic:doctor") else "nurse", current_user.id)
    await db.commit()
    await db.refresh(patient)
    return _patient_out(patient, await access.clinical_access(db, current_user, patient.id))


@router.get("/patients/{patient_id}")
async def get_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    patient = await _get_patient_or_404(db, tenant_id, patient_id)
    how = await access.clinical_access(db, current_user, patient.id)
    if how:
        await access.log_access(db, current_user, "patient", how, patient.id, 1)
    return _patient_out(patient, how)


@router.put("/patients/{patient_id}")
async def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_manage),
):
    q = await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == patient_id, ClinicPatient.tenant_id == tenant_id)
    )
    patient = q.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="الملف الطبي للمريض غير موجود")

    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if any(f in changes for f in access.CLINICAL_FIELDS):
        await access.require_clinical_access(db, current_user, patient.id)
    for k, v in changes.items():
        setattr(patient, k, v)
    patient.updated_by = current_user.full_name

    await audit_log(
        db,
        "clinic_patient",
        "update_patient",
        current_user.id,
        current_user.full_name,
        None,
        {"patient_id": patient.id, "full_name": patient.full_name},
        f"تحديث بيانات المريض: {patient.full_name}",
    )
    await db.commit()
    await db.refresh(patient)
    return _patient_out(patient, await access.clinical_access(db, current_user, patient.id))


@router.delete("/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_manage),
):
    q = await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == patient_id, ClinicPatient.tenant_id == tenant_id)
    )
    patient = q.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="الملف الطبي للمريض غير موجود")

    name = patient.full_name
    await audit_log(
        db,
        "clinic_patient",
        "delete_patient",
        current_user.id,
        current_user.full_name,
        None,
        {"patient_id": patient_id, "full_name": name},
        f"حذف الملف الطبي للمريض: {name}",
    )
    await db.delete(patient)
    await db.commit()


# ─── Appointments & Scheduling ──────────────────────────────────────────────
@router.get("/appointments")
async def list_appointments(
    search: str | None = None,
    doctor_name: str | None = None,
    appointment_date: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """A page of appointments, searched by patient, doctor or reference, with the filters (#39)."""
    query = select(ClinicAppointment).where(ClinicAppointment.tenant_id == tenant_id)
    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.where(
            or_(
                ClinicAppointment.patient_name.ilike(s),
                ClinicAppointment.appointment_ref.ilike(s),
                ClinicAppointment.doctor_name.ilike(s),
            )
        )
    if doctor_name:
        query = query.where(ClinicAppointment.doctor_name == doctor_name)
    if appointment_date:
        query = query.where(ClinicAppointment.appointment_date == appointment_date)
    if status_filter:
        query = query.where(ClinicAppointment.status == status_filter)

    query = query.order_by(ClinicAppointment.appointment_date.desc(), ClinicAppointment.queue_number.asc(),
                           ClinicAppointment.id)
    rows, total, pages = await _page(db, query, page, page_size)
    return {"items": [_row(a) for a in rows], "total": total, "page": page, "pages": pages}


@router.post("/appointments")
async def create_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_booking),
):
    # Referential integrity check
    patient = (await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == payload.patient_id, ClinicPatient.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="المريض غير مسجل في قاعدة البيانات الطبية")

    doctor = await access.clinician(db, tenant_id, payload.doctor_user_id) if payload.doctor_user_id else None
    if doctor:
        await access.refuse_self_assignment(db, current_user, patient.id, doctor["id"])
    doctor_name = doctor["full_name"] if doctor else payload.doctor_name.strip()
    if not doctor_name:
        raise HTTPException(status_code=400, detail="اختر الطبيب المعالج للموعد")

    ref = f"APT-{uuid.uuid4().hex[:6].upper()}"
    q_count = await db.execute(
        select(func.count(ClinicAppointment.id)).where(
            ClinicAppointment.tenant_id == tenant_id,
            ClinicAppointment.appointment_date == payload.appointment_date,
            ClinicAppointment.doctor_name == doctor_name,
        )
    )
    queue_no = (q_count.scalar() or 0) + 1

    appt = ClinicAppointment(
        tenant_id=tenant_id,
        appointment_ref=ref,
        patient_id=patient.id,
        patient_name=patient.full_name,
        doctor_name=doctor_name,
        doctor_user_id=uuid.UUID(doctor["id"]) if doctor else None,
        department=payload.department,
        appointment_date=payload.appointment_date,
        time_slot=payload.time_slot,
        queue_number=queue_no,
        consultation_fee=payload.consultation_fee,
        chief_complaint=payload.chief_complaint,
        status="scheduled",
        created_by=current_user.full_name,
    )
    db.add(appt)
    if doctor:
        await access.add_to_care_team(db, tenant_id, patient.id, appt.doctor_user_id,
                                      "attending" if doctor["is_doctor"] else "nurse", current_user.id)
    await audit_log(
        db,
        "clinic_appointment",
        "create_appointment",
        current_user.id,
        current_user.full_name,
        None,
        {"appointment_ref": ref, "patient_name": appt.patient_name, "doctor": appt.doctor_name},
        f"حجز موعد جديد: {appt.patient_name} مع {appt.doctor_name} بتاريخ {appt.appointment_date}",
    )
    await db.commit()
    await db.refresh(appt)
    return appt


@router.post("/appointments/{appt_id}/status")
async def update_appointment_status(
    appt_id: str,
    payload: AppointmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_queue),
):
    q = await db.execute(
        select(ClinicAppointment).where(ClinicAppointment.id == appt_id, ClinicAppointment.tenant_id == tenant_id)
    )
    appt = q.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="الموعد الطبي غير موجود")

    old_status = appt.status
    appt.status = payload.status
    appt.updated_by = current_user.full_name

    # Auto-billing when appointment is marked completed
    if payload.status == "completed" and appt.consultation_fee > 0:
        inv_existing = (await db.execute(
            select(ClinicInvoice).where(ClinicInvoice.appointment_id == appt.id, ClinicInvoice.tenant_id == tenant_id)
        )).scalar_one_or_none()

        if not inv_existing:
            patient = (await db.execute(
                select(ClinicPatient).where(ClinicPatient.id == appt.patient_id, ClinicPatient.tenant_id == tenant_id)
            )).scalar_one_or_none()

            copay = patient.copay_percent if patient else 0.0
            total = round(appt.consultation_fee, 2)
            ins_amt = round(total * (copay / 100.0), 2)
            pat_amt = round(total - ins_amt, 2)

            inv = ClinicInvoice(
                tenant_id=tenant_id,
                invoice_ref=f"INV-{uuid.uuid4().hex[:6].upper()}",
                patient_id=appt.patient_id,
                patient_name=appt.patient_name,
                appointment_id=appt.id,
                charges=[{"description": f"رسوم كشف واستشارة — {appt.doctor_name} ({appt.department})", "amount": appt.consultation_fee}],
                total=total,
                copay_percent=copay,
                insurance_amount=ins_amt,
                patient_amount=pat_amt,
                paid_amount=0.0,
                status="pending",
                created_by=current_user.full_name,
            )
            db.add(inv)
            await db.flush()

            if patient and ins_amt > 0:
                await _ensure_insurance_claim(db, tenant_id, patient, inv, current_user)

    await audit_log(
        db,
        "clinic_appointment",
        "update_appointment_status",
        current_user.id,
        current_user.full_name,
        None,
        {"appointment_ref": appt.appointment_ref, "from": old_status, "to": appt.status},
        f"تغيير حالة الموعد {appt.appointment_ref} إلى {appt.status}",
    )
    await db.commit()
    await db.refresh(appt)
    return appt


@router.post("/appointments/{appt_id}/cancel")
async def cancel_appointment(
    appt_id: str,
    payload: AppointmentCancelRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_manage),
):
    q = await db.execute(
        select(ClinicAppointment).where(ClinicAppointment.id == appt_id, ClinicAppointment.tenant_id == tenant_id)
    )
    appt = q.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="الموعد الطبي غير موجود")

    appt.status = "cancelled"
    appt.cancellation_reason = payload.reason
    appt.updated_by = current_user.full_name
    await audit_log(
        db,
        "clinic_appointment",
        "cancel_appointment",
        current_user.id,
        current_user.full_name,
        None,
        {"appointment_ref": appt.appointment_ref, "reason": payload.reason},
        f"إلغاء الموعد {appt.appointment_ref} بسبب: {payload.reason}",
    )
    await db.commit()
    await db.refresh(appt)
    return appt


@router.post("/appointments/{appt_id}/reschedule")
async def reschedule_appointment(
    appt_id: str,
    payload: AppointmentRescheduleRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_manage),
):
    q = await db.execute(
        select(ClinicAppointment).where(ClinicAppointment.id == appt_id, ClinicAppointment.tenant_id == tenant_id)
    )
    appt = q.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="الموعد الطبي غير موجود")

    old_slot = f"{appt.appointment_date} {appt.time_slot}"
    appt.rescheduled_from = old_slot
    appt.appointment_date = payload.new_date
    appt.time_slot = payload.new_time_slot
    appt.reschedule_count = (appt.reschedule_count or 0) + 1
    appt.status = "scheduled"
    appt.updated_by = current_user.full_name
    await audit_log(
        db,
        "clinic_appointment",
        "reschedule_appointment",
        current_user.id,
        current_user.full_name,
        None,
        {"appointment_ref": appt.appointment_ref, "old_slot": old_slot, "new_slot": f"{payload.new_date} {payload.new_time_slot}"},
        f"إعادة جدولة الموعد {appt.appointment_ref} من {old_slot} إلى {payload.new_date} {payload.new_time_slot}",
    )
    await db.commit()
    await db.refresh(appt)
    return appt


# ─── Clinical Encounters & Diagnoses ────────────────────────────────────────
@router.get("/encounters")
async def list_encounters(
    patient_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    return await _clinical_list(db, current_user, ClinicEncounter, "encounters", patient_id, None, [], limit, offset)


@router.post("/encounters")
async def create_encounter(
    payload: EncounterCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_doctor),
):
    # Validate patient existence
    patient = (await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == payload.patient_id, ClinicPatient.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="المريض غير مسجل في النظام")
    await access.require_clinical_access(db, current_user, patient.id)

    ref = f"ENC-{uuid.uuid4().hex[:6].upper()}"
    encounter = ClinicEncounter(
        tenant_id=tenant_id,
        encounter_ref=ref,
        patient_id=patient.id,
        patient_name=patient.full_name,
        doctor_name=payload.doctor_name,
        doctor_user_id=current_user.id,
        department=payload.department,
        encounter_date=payload.encounter_date,
        bp_systolic=payload.bp_systolic,
        bp_diastolic=payload.bp_diastolic,
        heart_rate=payload.heart_rate,
        temperature=payload.temperature,
        spo2=payload.spo2,
        chief_complaint=payload.chief_complaint,
        icd10_code=payload.icd10_code,
        icd10_description=payload.icd10_description,
        clinical_notes=payload.clinical_notes,
        created_by=current_user.full_name,
    )
    db.add(encounter)
    await audit_log(
        db,
        "clinic_encounter",
        "create_encounter",
        current_user.id,
        current_user.full_name,
        None,
        {"encounter_ref": ref, "patient_name": patient.full_name, "icd10": payload.icd10_code},
        f"تسجيل كشف سريري جديد {ref} للمريض {patient.full_name} — تشخيص ICD-10: {payload.icd10_code}",
    )
    await db.commit()
    await db.refresh(encounter)
    return encounter


# ─── Electronic Prescriptions (e-Rx) ────────────────────────────────────────
@router.get("/prescriptions")
async def list_prescriptions(
    patient_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    filters = [ClinicPrescription.status == status_filter] if status_filter else []
    return await _clinical_list(db, current_user, ClinicPrescription, "prescriptions", patient_id,
                                "clinic:dispense", filters, limit, offset)


@router.post("/prescriptions")
async def create_prescription(
    payload: PrescriptionCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_doctor),
):
    patient = (await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == payload.patient_id, ClinicPatient.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="المريض غير مسجل في النظام")
    await access.require_clinical_access(db, current_user, patient.id)

    # Drug allergy cross-check
    if patient.allergies and "لا توجد" not in patient.allergies:
        med_lower = payload.medication_name.lower().strip()
        allergy_lower = patient.allergies.lower()
        # Direct word matching
        if any(word in allergy_lower for word in med_lower.split() if len(word) > 2) and not payload.allergy_override:
            raise HTTPException(
                status_code=400,
                detail=f"تحذير دوائي: المريض لديه حساسية مسجلة تتطابق مع الدواء ({patient.allergies}). يرجى تفعيل التجاوز الطبي بعد مراجعة الطبيب المعالج.",
            )

    ref = f"RX-{uuid.uuid4().hex[:6].upper()}"
    rx = ClinicPrescription(
        tenant_id=tenant_id,
        rx_ref=ref,
        encounter_ref=payload.encounter_ref or f"ENC-{uuid.uuid4().hex[:6].upper()}",
        patient_id=patient.id,
        patient_name=patient.full_name,
        doctor_name=payload.doctor_name,
        doctor_user_id=current_user.id,
        issue_date=payload.issue_date,
        medication_name=payload.medication_name,
        dosage=payload.dosage,
        frequency=payload.frequency,
        duration_days=payload.duration_days,
        quantity=payload.quantity,
        instructions=payload.instructions,
        status="pending",
        created_by=current_user.full_name,
    )
    db.add(rx)
    await audit_log(
        db,
        "clinic_prescription",
        "create_prescription",
        current_user.id,
        current_user.full_name,
        None,
        {"rx_ref": ref, "medication": rx.medication_name, "patient": patient.full_name},
        f"إصدار روشتة طبية رقم {ref} لدواء {rx.medication_name} للمريض {patient.full_name}",
    )
    await db.commit()
    await db.refresh(rx)
    return rx


@router.post("/prescriptions/{rx_id}/dispense")
async def dispense_prescription(
    rx_id: str,
    payload: PrescriptionDispenseRequest = PrescriptionDispenseRequest(),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_dispense),
):
    q = await db.execute(
        select(ClinicPrescription).where(ClinicPrescription.id == rx_id, ClinicPrescription.tenant_id == tenant_id)
    )
    rx = q.scalar_one_or_none()
    if not rx:
        raise HTTPException(status_code=404, detail="الروشتة الطبية غير موجودة")
    if rx.status == "dispensed":
        raise HTTPException(status_code=400, detail="تم صرف هذه الروشتة مسبقاً")

    rx.status = "dispensed"
    rx.dispensed_at = datetime.now(UTC)
    rx.dispensed_by = current_user.full_name
    qty_dispensed = payload.quantity or rx.quantity or 1

    unit_price = 45.0  # default medication price

    # Stock leaves through the one stock path (ADR-006 phase 4): the drug is a product (matched by
    # trade or scientific name); in a pharmacy-tracking workspace its batches go first-expiry-first-out.
    try:
        from app.activities.general.modules.inventory.models.stock import MovementType
        from app.activities.general.modules.inventory.services.stock import apply_movement, get_balance
        from app.activities.pharmacy.modules.pharmacy.models import PharmacyPrescription

        product = (await db.execute(text("""
            SELECT id, retail_price FROM products
            WHERE is_active AND (name ILIKE :m OR extra->>'scientific_name' ILIKE :m) ORDER BY name LIMIT 1
        """), {"m": f"%{rx.medication_name}%"})).first()
        warehouse = await db.scalar(text("SELECT id FROM warehouses WHERE is_active ORDER BY created_at LIMIT 1"))
        if product and warehouse:
            unit_price = float(product.retail_price) if product.retail_price and product.retail_price > 0 else 45.0
            if await get_balance(db, product.id, warehouse, for_update=True) >= qty_dispensed:
                async with db.begin_nested():  # no valid batch: dispensing still records, stock untouched
                    await apply_movement(db, product_id=product.id, warehouse_id=warehouse, movement_type=MovementType.sale,
                                         qty=qty_dispensed, unit_price=unit_price, created_by=current_user.id,
                                         ref_type="clinic_dispense", note=f"صرف روشتة عيادة: {rx.medication_name}")
            db.add(PharmacyPrescription(
                tenant_id=tenant_id,
                rx_number=f"PH-RX-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}",
                patient_name=rx.patient_name, patient_phone="", doctor_name=rx.doctor_name,
                doctor_license="MED-LIC-AUTO", diagnosis="صرف عيادات خارجية", insurance_company="",
                copay_percentage=0.0, total_amount=round(unit_price * qty_dispensed, 2),
                patient_paid=round(unit_price * qty_dispensed, 2), insurance_covered=0.0, status="dispensed",
            ))
    except Exception:
        logger.warning("Clinic dispense: stock not deducted for %s", rx.medication_name, exc_info=True)

    # Create medication invoice
    total_med_cost = round(unit_price * qty_dispensed, 2)
    patient = (await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == rx.patient_id, ClinicPatient.tenant_id == tenant_id)
    )).scalar_one_or_none()

    copay = patient.copay_percent if patient else 0.0
    ins_share = round(total_med_cost * (copay / 100.0), 2)
    pat_share = round(total_med_cost - ins_share, 2)

    inv = ClinicInvoice(
        tenant_id=tenant_id,
        invoice_ref=f"INV-RX-{uuid.uuid4().hex[:6].upper()}",
        patient_id=rx.patient_id,
        patient_name=rx.patient_name,
        encounter_ref=rx.encounter_ref,
        # Neutral line text: billing staff see the invoice, not the medication (#131).
        charges=[{"description": f"صرف أدوية — روشتة {rx.rx_ref}", "amount": total_med_cost}],
        total=total_med_cost,
        copay_percent=copay,
        insurance_amount=ins_share,
        patient_amount=pat_share,
        paid_amount=0.0,
        status="pending",
        created_by=current_user.full_name,
    )
    db.add(inv)
    await db.flush()

    if patient and ins_share > 0:
        await _ensure_insurance_claim(db, tenant_id, patient, inv, current_user)

    await audit_log(
        db,
        "clinic_prescription",
        "dispense_prescription",
        current_user.id,
        current_user.full_name,
        None,
        {"rx_ref": rx.rx_ref, "medication": rx.medication_name, "quantity": qty_dispensed, "cost": total_med_cost},
        f"صرف روشتة طبية رقم {rx.rx_ref} للمريض {rx.patient_name} — دواء: {rx.medication_name} (كمية: {qty_dispensed})",
    )
    await db.commit()
    await db.refresh(rx)
    return rx


# ─── Laboratory & Diagnostics ───────────────────────────────────────────────
@router.get("/lab-orders")
async def list_lab_orders(
    patient_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    filters = [ClinicLabOrder.status == status_filter] if status_filter else []
    return await _clinical_list(db, current_user, ClinicLabOrder, "lab_orders", patient_id,
                                "clinic:lab", filters, limit, offset)


@router.post("/lab-orders")
async def create_lab_order(
    payload: LabOrderCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_doctor),
):
    patient = (await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == payload.patient_id, ClinicPatient.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="المريض غير مسجل في النظام")
    await access.require_clinical_access(db, current_user, patient.id)

    ref = f"LAB-{uuid.uuid4().hex[:6].upper()}"
    order = ClinicLabOrder(
        tenant_id=tenant_id,
        order_ref=ref,
        patient_id=patient.id,
        patient_name=patient.full_name,
        doctor_name=payload.doctor_name,
        doctor_user_id=current_user.id,
        test_name=payload.test_name,
        category=payload.category,
        specimen_barcode=payload.specimen_barcode or f"SPEC-{uuid.uuid4().hex[:4].upper()}",
        reference_range=payload.reference_range,
        result_value="قيد الفحص والتحليل",
        status="ordered",
        test_fee=payload.test_fee,
        created_by=current_user.full_name,
    )
    db.add(order)
    await audit_log(
        db,
        "clinic_lab_order",
        "create_lab_order",
        current_user.id,
        current_user.full_name,
        None,
        {"order_ref": ref, "test_name": payload.test_name, "patient": patient.full_name},
        f"طلب تحليل مخبري جديد {ref} ({payload.test_name}) للمريض {patient.full_name}",
    )
    await db.commit()
    await db.refresh(order)
    return order


@router.post("/lab-orders/{order_id}/result")
async def record_lab_result(
    order_id: str,
    payload: LabResultUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_lab),
):
    q = await db.execute(
        select(ClinicLabOrder).where(ClinicLabOrder.id == order_id, ClinicLabOrder.tenant_id == tenant_id)
    )
    order = q.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="طلب الفحص المخبري غير موجود")

    order.result_value = payload.result_value
    order.numeric_value = payload.numeric_value
    order.unit = payload.unit
    order.is_critical = payload.is_critical
    order.status = "reported"
    order.updated_by = current_user.full_name

    if payload.is_signed_off:
        order.is_signed_off = True
        order.signed_off_by = current_user.full_name
        order.signed_off_at = datetime.now(UTC)

    # Billing for lab order
    if order.test_fee > 0:
        inv_existing = (await db.execute(
            select(ClinicInvoice).where(
                ClinicInvoice.patient_id == order.patient_id,
                ClinicInvoice.encounter_ref == order.order_ref,
                ClinicInvoice.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()

        if not inv_existing:
            patient = (await db.execute(
                select(ClinicPatient).where(ClinicPatient.id == order.patient_id, ClinicPatient.tenant_id == tenant_id)
            )).scalar_one_or_none()

            copay = patient.copay_percent if patient else 0.0
            total = round(order.test_fee, 2)
            ins_amt = round(total * (copay / 100.0), 2)
            pat_amt = round(total - ins_amt, 2)

            inv = ClinicInvoice(
                tenant_id=tenant_id,
                invoice_ref=f"INV-LAB-{uuid.uuid4().hex[:6].upper()}",
                patient_id=order.patient_id,
                patient_name=order.patient_name,
                encounter_ref=order.order_ref,
                charges=[{"description": f"رسوم فحص مخبري — طلب {order.order_ref}", "amount": order.test_fee}],
                total=total,
                copay_percent=copay,
                insurance_amount=ins_amt,
                patient_amount=pat_amt,
                paid_amount=0.0,
                status="pending",
                created_by=current_user.full_name,
            )
            db.add(inv)
            await db.flush()

            if patient and ins_amt > 0:
                await _ensure_insurance_claim(db, tenant_id, patient, inv, current_user)

    await audit_log(
        db,
        "clinic_lab_order",
        "record_lab_result",
        current_user.id,
        current_user.full_name,
        None,
        {"order_ref": order.order_ref, "result": payload.result_value, "is_critical": payload.is_critical},
        f"تسجيل واعتماد نتيجة الفحص المخبري {order.order_ref} — النتيجة: {payload.result_value}",
    )
    await db.commit()
    await db.refresh(order)
    return order


# ─── Inpatient Beds Management ──────────────────────────────────────────────
@router.get("/beds")
async def list_beds(
    status_filter: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
):
    query = select(ClinicInpatientBed).where(ClinicInpatientBed.tenant_id == tenant_id)
    if status_filter:
        query = query.where(ClinicInpatientBed.status == status_filter)
    query = query.order_by(ClinicInpatientBed.ward_name, ClinicInpatientBed.bed_code)
    q = await db.execute(query)
    return q.scalars().all()


@router.post("/beds/{bed_id}/admit")
async def admit_bed(
    bed_id: str,
    payload: BedAdmitRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_ward),
):
    q = await db.execute(
        select(ClinicInpatientBed).where(ClinicInpatientBed.id == bed_id, ClinicInpatientBed.tenant_id == tenant_id)
    )
    bed = q.scalar_one_or_none()
    if not bed:
        raise HTTPException(status_code=404, detail="السرير الطبي غير موجود")
    if bed.status == "occupied":
        raise HTTPException(status_code=400, detail="السرير مشغول حالياً بمريض آخر")

    patient = None
    if payload.patient_id:
        patient = (await db.execute(
            select(ClinicPatient).where(ClinicPatient.id == payload.patient_id, ClinicPatient.tenant_id == tenant_id)
        )).scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=404, detail="المريض المراد تنويمه غير مسجل في النظام")

    bed.status = "occupied"
    bed.current_patient_id = patient.id if patient else None
    bed.current_patient_name = patient.full_name if patient else payload.patient_name
    bed.admission_date = payload.admission_date or date.today().isoformat()
    bed.updated_by = current_user.full_name

    await audit_log(
        db,
        "clinic_bed",
        "admit_bed",
        current_user.id,
        current_user.full_name,
        None,
        {"bed_code": bed.bed_code, "ward": bed.ward_name, "patient": bed.current_patient_name},
        f"تنويم مريض في السرير {bed.bed_code} ({bed.ward_name}): {bed.current_patient_name}",
    )
    await db.commit()
    await db.refresh(bed)
    return bed


@router.post("/beds/{bed_id}/discharge")
@router.post("/beds/{bed_id}/discharge-bill")
async def discharge_bed(
    bed_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_ward),
):
    q = await db.execute(
        select(ClinicInpatientBed).where(ClinicInpatientBed.id == bed_id, ClinicInpatientBed.tenant_id == tenant_id)
    )
    bed = q.scalar_one_or_none()
    if not bed:
        raise HTTPException(status_code=404, detail="السرير الطبي غير موجود")

    patient_name = bed.current_patient_name
    patient_id = bed.current_patient_id

    # Compute stay days
    days = 1
    try:
        adm = datetime.fromisoformat(bed.admission_date).date()
        days = max(1, (date.today() - adm).days)
    except Exception:
        days = 1

    total_charge = round(bed.daily_rate * days, 2)
    inv = None

    if patient_id or patient_name:
        patient = None
        if patient_id:
            patient = (await db.execute(
                select(ClinicPatient).where(ClinicPatient.id == patient_id, ClinicPatient.tenant_id == tenant_id)
            )).scalar_one_or_none()

        copay = patient.copay_percent if patient else 0.0
        ins_amt = round(total_charge * (copay / 100.0), 2)
        pat_amt = round(total_charge - ins_amt, 2)

        inv = ClinicInvoice(
            tenant_id=tenant_id,
            invoice_ref=f"INV-BED-{uuid.uuid4().hex[:6].upper()}",
            patient_id=patient.id if patient else (patient_id or "N/A"),
            patient_name=patient.full_name if patient else patient_name,
            charges=[{
                "description": f"إقامة وتنويم سريري — {bed.ward_name} ({bed.bed_code}) لمدة {days} يوم بواقع {bed.daily_rate} ر.س/يوم",
                "amount": total_charge,
            }],
            total=total_charge,
            copay_percent=copay,
            insurance_amount=ins_amt,
            patient_amount=pat_amt,
            paid_amount=0.0,
            status="pending",
            created_by=current_user.full_name,
        )
        db.add(inv)
        await db.flush()

        if patient and ins_amt > 0:
            await _ensure_insurance_claim(db, tenant_id, patient, inv, current_user)

    bed.status = "cleaning"
    bed.current_patient_id = None
    bed.current_patient_name = ""
    bed.admission_date = ""
    bed.updated_by = current_user.full_name

    await audit_log(
        db,
        "clinic_bed",
        "discharge_bed",
        current_user.id,
        current_user.full_name,
        None,
        {"bed_code": bed.bed_code, "patient": patient_name, "days": days, "charge": total_charge},
        f"خروج المريض {patient_name} من السرير {bed.bed_code} وحساب إقامة {days} يوم بقيمة {total_charge}",
    )
    await db.commit()
    await db.refresh(bed)
    return {"bed": bed, "billed_days": days, "charge": total_charge, "invoice": inv}


@router.post("/beds/{bed_id}/clean")
async def clean_bed(
    bed_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_ward),
):
    q = await db.execute(
        select(ClinicInpatientBed).where(ClinicInpatientBed.id == bed_id, ClinicInpatientBed.tenant_id == tenant_id)
    )
    bed = q.scalar_one_or_none()
    if not bed:
        raise HTTPException(status_code=404, detail="السرير الطبي غير موجود")
    bed.status = "available"
    bed.updated_by = current_user.full_name
    await audit_log(
        db,
        "clinic_bed",
        "clean_bed",
        current_user.id,
        current_user.full_name,
        None,
        {"bed_code": bed.bed_code},
        f"اكتمال تعقيم وتجهيز السرير {bed.bed_code} وأصبح متاحاً",
    )
    await db.commit()
    await db.refresh(bed)
    return bed


# ─── Invoices & Billing ─────────────────────────────────────────────────────
@router.get("/invoices")
async def list_invoices(
    patient_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_billing),
):
    query = select(ClinicInvoice).where(ClinicInvoice.tenant_id == tenant_id)
    if patient_id:
        query = query.where(ClinicInvoice.patient_id == patient_id)
    query = query.order_by(ClinicInvoice.created_at.desc()).offset(offset).limit(limit)
    q = await db.execute(query)
    return q.scalars().all()


@router.post("/invoices")
async def create_invoice(
    payload: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_billing),
):
    ref = f"INV-{uuid.uuid4().hex[:6].upper()}"
    total = round(sum(float(c.get("amount", 0)) for c in payload.charges), 2)
    copay = max(0.0, min(100.0, payload.copay_percent))
    insurance_amount = round(total * (copay / 100.0), 2)
    patient_amount = round(total - insurance_amount, 2)

    inv = ClinicInvoice(
        tenant_id=tenant_id,
        invoice_ref=ref,
        patient_id=payload.patient_id,
        patient_name=payload.patient_name,
        appointment_id=payload.appointment_id,
        encounter_ref=payload.encounter_ref,
        charges=payload.charges,
        total=total,
        copay_percent=copay,
        insurance_amount=insurance_amount,
        patient_amount=patient_amount,
        paid_amount=0.0,
        status="pending",
        created_by=current_user.full_name,
    )
    db.add(inv)
    await db.flush()

    patient = (await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == payload.patient_id, ClinicPatient.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if patient and insurance_amount > 0:
        await _ensure_insurance_claim(db, tenant_id, patient, inv, current_user)

    await audit_log(
        db,
        "clinic_invoice",
        "create_invoice",
        current_user.id,
        current_user.full_name,
        None,
        {"invoice_ref": ref, "total": total, "patient": payload.patient_name},
        f"إصدار فاتورة طبية جديدة {ref} للمريض {payload.patient_name} بإجمالي {total}",
    )
    await db.commit()
    await db.refresh(inv)
    return inv


@router.post("/appointments/{appt_id}/bill")
async def bill_appointment(
    appt_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_billing),
):
    q = await db.execute(
        select(ClinicAppointment).where(ClinicAppointment.id == appt_id, ClinicAppointment.tenant_id == tenant_id)
    )
    appt = q.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="الموعد الطبي غير موجود")

    existing = await db.execute(
        select(ClinicInvoice).where(ClinicInvoice.appointment_id == appt_id, ClinicInvoice.tenant_id == tenant_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="تم إصدار فاتورة لهذا الموعد مسبقاً")

    patient = (await db.execute(
        select(ClinicPatient).where(ClinicPatient.id == appt.patient_id, ClinicPatient.tenant_id == tenant_id)
    )).scalar_one_or_none()

    copay = patient.copay_percent if patient else 0.0
    total = round(appt.consultation_fee, 2)
    insurance_amount = round(total * (copay / 100.0), 2)
    patient_amount = round(total - insurance_amount, 2)

    inv = ClinicInvoice(
        tenant_id=tenant_id,
        invoice_ref=f"INV-{uuid.uuid4().hex[:6].upper()}",
        patient_id=appt.patient_id,
        patient_name=appt.patient_name,
        appointment_id=appt.id,
        charges=[{"description": f"رسوم كشف — {appt.doctor_name} ({appt.department})", "amount": appt.consultation_fee}],
        total=total,
        copay_percent=copay,
        insurance_amount=insurance_amount,
        patient_amount=patient_amount,
        paid_amount=0.0,
        status="pending",
        created_by=current_user.full_name,
    )
    db.add(inv)
    await db.flush()

    if patient and insurance_amount > 0:
        await _ensure_insurance_claim(db, tenant_id, patient, inv, current_user)

    await audit_log(
        db,
        "clinic_invoice",
        "bill_appointment",
        current_user.id,
        current_user.full_name,
        None,
        {"invoice_ref": inv.invoice_ref, "appt_ref": appt.appointment_ref},
        f"فوترة موعد طبي {appt.appointment_ref} — فاتورة: {inv.invoice_ref}",
    )
    await db.commit()
    await db.refresh(inv)
    return inv


@router.post("/invoices/{inv_id}/pay")
async def pay_invoice(
    inv_id: str,
    payload: InvoicePayRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_billing),
):
    q = await db.execute(
        select(ClinicInvoice).where(ClinicInvoice.id == inv_id, ClinicInvoice.tenant_id == tenant_id)
    )
    inv = q.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")

    remaining = round(inv.patient_amount - inv.paid_amount, 2)
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ المدفوع يجب أن يكون أكبر من صفر")
    if payload.amount > remaining + 0.001:
        raise HTTPException(status_code=400, detail=f"المبلغ أكبر من المتبقي على الفاتورة ({remaining})")

    inv.paid_amount = round(inv.paid_amount + payload.amount, 2)
    inv.payment_method = payload.payment_method
    inv.paid_by = current_user.full_name

    if inv.paid_amount >= inv.patient_amount - 0.001:
        inv.status = "paid"
        inv.paid_at = datetime.now(UTC)
    elif inv.paid_amount > 0:
        inv.status = "partial"

    await _record_invoice_payment(db, tenant_id, inv, Decimal(str(round(payload.amount, 2))),
                                  payload.payment_method or "cash", current_user)

    await audit_log(
        db,
        "clinic_invoice",
        "pay_invoice",
        current_user.id,
        current_user.full_name,
        None,
        {"invoice_ref": inv.invoice_ref, "amount": payload.amount, "status": inv.status},
        f"تحصيل وسداد مبلغ {payload.amount} لفاتورة {inv.invoice_ref} ({inv.status})",
    )
    await db.commit()
    await db.refresh(inv)
    return inv


# ─── Insurance Claims ────────────────────────────────────────────────────────
@router.get("/claims")
async def list_claims(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_billing),
):
    query = select(ClinicInsuranceClaim).where(ClinicInsuranceClaim.tenant_id == tenant_id)
    if status_filter:
        query = query.where(ClinicInsuranceClaim.status == status_filter)
    query = query.order_by(ClinicInsuranceClaim.submitted_at.desc()).offset(offset).limit(limit)
    q = await db.execute(query)
    return q.scalars().all()


@router.post("/claims")
async def create_claim(
    payload: ClaimCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_billing),
):
    ref = f"CLM-{uuid.uuid4().hex[:6].upper()}"
    claim = ClinicInsuranceClaim(
        tenant_id=tenant_id,
        claim_ref=ref,
        patient_id=payload.patient_id,
        patient_name=payload.patient_name,
        invoice_id=payload.invoice_id,
        insurance_provider=payload.insurance_provider,
        policy_no=payload.policy_no,
        copay_percent=payload.copay_percent,
        claimed_amount=payload.claimed_amount,
        approved_amount=0.0,
        status="submitted",
        created_by=current_user.full_name,
        notes=payload.notes,
    )
    db.add(claim)
    await audit_log(
        db,
        "clinic_insurance_claim",
        "create_claim",
        current_user.id,
        current_user.full_name,
        None,
        {"claim_ref": ref, "claimed_amount": payload.claimed_amount, "provider": payload.insurance_provider},
        f"تقديم مطالبة تأمينية رقم {ref} لشركة {payload.insurance_provider} بقيمة {payload.claimed_amount}",
    )
    await db.commit()
    await db.refresh(claim)
    return claim


@router.post("/claims/{claim_id}/status")
async def update_claim_status(
    claim_id: str,
    payload: ClaimStatusUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_billing),
):
    q = await db.execute(
        select(ClinicInsuranceClaim).where(ClinicInsuranceClaim.id == claim_id, ClinicInsuranceClaim.tenant_id == tenant_id)
    )
    claim = q.scalar_one_or_none()
    if not claim:
        raise HTTPException(status_code=404, detail="المطالبة غير موجودة")

    old_status = claim.status
    claim.status = payload.status
    if payload.approved_amount is not None:
        claim.approved_amount = payload.approved_amount
    if payload.notes:
        claim.notes = payload.notes
    if payload.status in ("approved", "rejected", "paid"):
        claim.resolved_at = datetime.now(UTC)

    await audit_log(
        db,
        "clinic_insurance_claim",
        "update_claim_status",
        current_user.id,
        current_user.full_name,
        None,
        {"claim_ref": claim.claim_ref, "from": old_status, "to": payload.status, "approved": claim.approved_amount},
        f"تحديث حالة المطالبة التأمينية {claim.claim_ref} من {old_status} إلى {payload.status}",
    )
    await db.commit()
    await db.refresh(claim)
    return claim


@router.post("/seed")
async def seed_clinic_data(
    db: AsyncSession = Depends(get_db),
    tenant_id: str = Depends(get_current_tenant_id),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_clinic_manage),
):
    """Seed initial sample clinical, appointment, EMR, and inpatient bed data."""
    from app.activities.healthcare.modules.healthcare_clinic.seed import seed_clinic_records

    seeded = await seed_clinic_records(db, tenant_id)
    if not seeded:
        return {"message": "بيانات المركز الطبي والعناية السريرية مسجلة مسبقاً"}
    return {"message": "تم تهيئة وتوليد بيانات العيادات والملفات الطبية والأسرة بنجاح"}
