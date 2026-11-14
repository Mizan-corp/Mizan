"""Database models for Healthcare & Clinic/Hospital ERP module (HLT-01..12)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.tenancy.context import TenantScoped
from app.db.base import Base


class ClinicPatient(TenantScoped, Base):
    """Electronic Medical Record (EMR) Master Patient Index (HLT-01)."""
    __tablename__ = "clinic_patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_mrn: Mapped[str] = mapped_column(String(32), index=True)  # Medical Record Number (MRN)
    full_name: Mapped[str] = mapped_column(String(128), index=True)
    national_id: Mapped[str] = mapped_column(String(32), index=True)
    phone: Mapped[str] = mapped_column(String(32))
    gender: Mapped[str] = mapped_column(String(16))  # ذكر / أنثى
    date_of_birth: Mapped[str] = mapped_column(String(32))
    blood_group: Mapped[str] = mapped_column(String(8), default="A+")
    allergies: Mapped[str] = mapped_column(String(256), default="لا توجد حساسيات مسجلة")
    chronic_conditions: Mapped[str] = mapped_column(String(256), default="لا توجد أمراض مزمنة")
    insurance_provider: Mapped[str] = mapped_column(String(128), default="نقدي / غير مؤمن")
    insurance_policy_no: Mapped[str] = mapped_column(String(64), default="N/A")
    copay_percent: Mapped[float] = mapped_column(Float, default=0.0)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClinicDepartment(TenantScoped, Base):
    """Department master (#36): the clinic's departments and their specialty codes."""
    __tablename__ = "clinic_departments"
    __table_args__ = (Index("ux_clinic_departments_code", "tenant_id", "code", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(64))
    specialty_code: Mapped[str] = mapped_column(String(32), default="", server_default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicRoom(TenantScoped, Base):
    """Examination / consultation rooms (#36)."""
    __tablename__ = "clinic_rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(64))
    department_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clinic_departments.id", ondelete="SET NULL"), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicDoctorSchedule(TenantScoped, Base):
    """A doctor's weekly roster (#36): on `weekday` (0 = Monday … 6 = Sunday, Python's weekday()),
    from start_time to end_time ("HH:MM"), in a department and room, in slots of slot_minutes."""
    __tablename__ = "clinic_doctor_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_departments.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clinic_rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[str] = mapped_column(String(5))
    end_time: Mapped[str] = mapped_column(String(5))
    slot_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicAppointment(TenantScoped, Base):
    """Physician Appointment Scheduling & Queuing (HLT-02)."""
    __tablename__ = "clinic_appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    appointment_ref: Mapped[str] = mapped_column(String(32), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    patient_name: Mapped[str] = mapped_column(String(128))
    doctor_name: Mapped[str] = mapped_column(String(128), index=True)
    doctor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    department: Mapped[str] = mapped_column(String(64))  # the department's name (kept for older records and lists)
    department_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clinic_departments.id", ondelete="SET NULL"), nullable=True, index=True)
    room_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clinic_rooms.id", ondelete="SET NULL"), nullable=True, index=True)
    appointment_date: Mapped[str] = mapped_column(String(32))
    time_slot: Mapped[str] = mapped_column(String(32))  # "HH:MM" (24h) since #36; older rows may hold "10:30 AM"
    queue_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")  # scheduled, waiting, in_consultation, completed, cancelled, no_show
    consultation_fee: Mapped[float] = mapped_column(Float, default=250.0)
    chief_complaint: Mapped[str] = mapped_column(String(256), default="")
    cancellation_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    rescheduled_from: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reschedule_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClinicEncounter(TenantScoped, Base):
    """Clinical Encounters, Vitals & ICD-10 Diagnoses (HLT-03, HLT-10)."""
    __tablename__ = "clinic_encounters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    encounter_ref: Mapped[str] = mapped_column(String(32), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    patient_name: Mapped[str] = mapped_column(String(128))
    doctor_name: Mapped[str] = mapped_column(String(128))
    doctor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    department: Mapped[str] = mapped_column(String(64))
    encounter_date: Mapped[str] = mapped_column(String(32))
    bp_systolic: Mapped[int] = mapped_column(Integer, default=120)
    bp_diastolic: Mapped[int] = mapped_column(Integer, default=80)
    heart_rate: Mapped[int] = mapped_column(Integer, default=72)
    temperature: Mapped[float] = mapped_column(Float, default=37.0)
    spo2: Mapped[int] = mapped_column(Integer, default=98)
    blood_glucose: Mapped[float | None] = mapped_column(Float, nullable=True)  # mg/dL (#42)
    chief_complaint: Mapped[str] = mapped_column(Text)
    icd10_code: Mapped[str] = mapped_column(String(32), index=True)  # e.g. E11.9, I10, J06.9
    icd10_description: Mapped[str] = mapped_column(String(256))
    clinical_notes: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClinicPrescription(TenantScoped, Base):
    """Electronic Prescriptions (e-Rx) (HLT-04)."""
    __tablename__ = "clinic_prescriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rx_ref: Mapped[str] = mapped_column(String(32), index=True)
    encounter_ref: Mapped[str] = mapped_column(String(32), default="", index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    patient_name: Mapped[str] = mapped_column(String(128))
    doctor_name: Mapped[str] = mapped_column(String(128))
    doctor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    issue_date: Mapped[str] = mapped_column(String(32))
    medication_name: Mapped[str] = mapped_column(String(128))
    dosage: Mapped[str] = mapped_column(String(64))  # e.g. 500mg
    frequency: Mapped[str] = mapped_column(String(64))  # 3 مرات يومياً بعد الأكل
    duration_days: Mapped[int] = mapped_column(Integer, default=7)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    instructions: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, dispensed
    dispensed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispensed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClinicLabOrder(TenantScoped, Base):
    """Laboratory & Diagnostic Radiology Orders (HLT-05)."""
    __tablename__ = "clinic_lab_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_ref: Mapped[str] = mapped_column(String(32), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    patient_name: Mapped[str] = mapped_column(String(128))
    doctor_name: Mapped[str] = mapped_column(String(128))
    doctor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    test_name: Mapped[str] = mapped_column(String(128))  # CBC, صورة دم كاملة, أشعة سينية الصدر
    category: Mapped[str] = mapped_column(String(64))  # مختبر / أشعة
    specimen_barcode: Mapped[str] = mapped_column(String(64), index=True)
    reference_range: Mapped[str] = mapped_column(String(128), default="Normal")
    result_value: Mapped[str] = mapped_column(String(128), default="قيد التحليل")
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="")
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    test_fee: Mapped[float] = mapped_column(Float, default=150.0)
    status: Mapped[str] = mapped_column(String(32), default="ordered")  # ordered, collected, reported
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_signed_off: Mapped[bool] = mapped_column(Boolean, default=False)
    signed_off_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    signed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClinicInpatientBed(TenantScoped, Base):
    """Ward & Inpatient Bed Occupancy Management (HLT-07, HLT-08)."""
    __tablename__ = "clinic_inpatient_beds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bed_code: Mapped[str] = mapped_column(String(32), index=True)  # e.g. BED-ICU-01, BED-W-204
    ward_name: Mapped[str] = mapped_column(String(64), index=True)  # العناية المركزة (ICU)، جناح الجراحة، قسم الباطنة
    room_number: Mapped[str] = mapped_column(String(32))
    bed_type: Mapped[str] = mapped_column(String(32))  # عادي، عناية حثيثة، عزل طبي
    daily_rate: Mapped[float] = mapped_column(Float, default=1200.0)
    status: Mapped[str] = mapped_column(String(32), default="available")  # available, occupied, cleaning, maintenance
    current_patient_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="SET NULL"), nullable=True, index=True)
    current_patient_name: Mapped[str] = mapped_column(String(128), default="")
    admission_date: Mapped[str] = mapped_column(String(32), default="")
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClinicInvoice(TenantScoped, Base):
    """Clinic/Hospital billing invoice (consultation, bed, lab, pharmacy charges)."""
    __tablename__ = "clinic_invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_ref: Mapped[str] = mapped_column(String(32), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    patient_name: Mapped[str] = mapped_column(String(128))
    appointment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    encounter_ref: Mapped[str | None] = mapped_column(String(32), nullable=True)
    charges: Mapped[list] = mapped_column(JSONB, default=list)  # [{description, amount}]
    total: Mapped[float] = mapped_column(Float, default=0.0)
    copay_percent: Mapped[float] = mapped_column(Float, default=0.0)
    insurance_amount: Mapped[float] = mapped_column(Float, default=0.0)
    patient_amount: Mapped[float] = mapped_column(Float, default=0.0)
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, partial, paid
    payment_method: Mapped[str] = mapped_column(String(32), default="cash")
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    paid_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClinicInsuranceClaim(TenantScoped, Base):
    """Insurance claim submission & tracking for clinic services."""
    __tablename__ = "clinic_insurance_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_ref: Mapped[str] = mapped_column(String(32), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    patient_name: Mapped[str] = mapped_column(String(128))
    invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    insurance_provider: Mapped[str] = mapped_column(String(128))
    policy_no: Mapped[str] = mapped_column(String(64), default="N/A")
    copay_percent: Mapped[float] = mapped_column(Float, default=0.0)
    claimed_amount: Mapped[float] = mapped_column(Float, default=0.0)
    approved_amount: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="submitted")  # submitted, approved, rejected, paid
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class ClinicCareTeam(TenantScoped, Base):
    """The clinicians caring for a patient: they read and write the patient's clinical record (#113)."""
    __tablename__ = "clinic_care_team"
    __table_args__ = (
        Index("ux_clinic_care_team_active", "tenant_id", "patient_id", "user_id", unique=True, postgresql_where=text("ended_at IS NULL")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="attending", server_default="attending")  # attending, consultant, nurse, other
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ClinicAccessGrant(TenantScoped, Base):
    """Break-glass: a clinician outside the care team opens one patient's record for a short window,
    with a reason; the privacy officer reviews it (#113)."""
    __tablename__ = "clinic_access_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClinicAccessLog(TenantScoped, Base):
    """One row per read of clinical data: who, which patient (none for a list), how access was granted (#113)."""
    __tablename__ = "clinic_access_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    user_name: Mapped[str] = mapped_column(String(128), default="", server_default="")
    patient_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    resource: Mapped[str] = mapped_column(String(16))  # patient, encounters, prescriptions, lab_orders
    how: Mapped[str] = mapped_column(String(16))  # all, team, break_glass, queue, setting
    rows: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class ClinicReferral(TenantScoped, Base):
    """A referral of a patient to another department or doctor (#45). Accepting it puts the
    receiving doctor on the patient's care team: the patient's record follows the referral."""
    __tablename__ = "clinic_referrals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    referral_ref: Mapped[str] = mapped_column(String(32), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    from_doctor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    from_doctor_name: Mapped[str] = mapped_column(String(128), default="", server_default="")
    to_department_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_departments.id", ondelete="RESTRICT"), index=True)
    to_doctor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(String(16), default="routine", server_default="routine")  # routine, urgent, emergency
    reason: Mapped[str] = mapped_column(Text)
    triage_notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending", index=True)  # pending, accepted, declined, completed
    encounter_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clinic_encounters.id", ondelete="SET NULL"), nullable=True)
    responded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_note: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClinicConsentForm(TenantScoped, Base):
    """A signed consent (#43): procedure, surgery, data sharing… with the signer's drawn signature
    (a PNG in the private file store; signature_path is its key, never served by URL)."""
    __tablename__ = "clinic_consent_forms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    consent_ref: Mapped[str] = mapped_column(String(32), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    encounter_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clinic_encounters.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default="procedure")  # procedure, surgery, data_sharing, other
    title: Mapped[str] = mapped_column(String(200))  # the procedure or what is consented to
    body: Mapped[str] = mapped_column(Text)
    signer_name: Mapped[str] = mapped_column(String(128))
    signer_relation: Mapped[str] = mapped_column(String(16), default="self")  # self, guardian, parent, spouse, other
    signature_path: Mapped[str] = mapped_column(String(1024))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    witness_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    witness_name: Mapped[str] = mapped_column(String(128), default="", server_default="")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    revoke_reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicImage(TenantScoped, Base):
    """A medical image (#44): X-ray, ultrasound, CT, MRI… (JPEG, PNG, WebP or DICOM) in the private
    file store; served only through a short-lived signed link after the access check."""
    __tablename__ = "clinic_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinic_patients.id", ondelete="CASCADE"), index=True)
    encounter_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clinic_encounters.id", ondelete="SET NULL"), nullable=True, index=True)
    modality: Mapped[str] = mapped_column(String(8), default="other")  # XR, US, CT, MRI, other
    file_path: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    original_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_by_name: Mapped[str] = mapped_column(String(128), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
