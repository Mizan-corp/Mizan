from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class ClinicalEncounter(TenantScoped, Base):
    __tablename__ = "hlt_clinical_encounters"
    id = Column(Integer, primary_key=True, index=True)
    encounter_number = Column(String(50), nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    doctor_id = Column(Integer, nullable=False, index=True)
    chief_complaint = Column(Text, nullable=False)
    examination = Column(Text, nullable=True)
    diagnosis = Column(String(255), nullable=True)
    icd10_code = Column(String(50), nullable=True)
    treatment_plan = Column(Text, nullable=True)
    status = Column(String(30), default="draft")  # draft, finalized
    signed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
