from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class PatientVitalRecord(TenantScoped, Base):
    __tablename__ = "hlt_patient_vitals"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    systolic_bp = Column(Integer, nullable=True)
    diastolic_bp = Column(Integer, nullable=True)
    pulse_rate = Column(Integer, nullable=True)
    temperature = Column(Numeric(4, 1), nullable=True)
    respiratory_rate = Column(Integer, nullable=True)
    oxygen_saturation = Column(Integer, nullable=True)
    height_cm = Column(Numeric(5, 1), nullable=True)
    weight_kg = Column(Numeric(5, 1), nullable=True)
    bmi = Column(Numeric(4, 1), nullable=True)
    recorded_at = Column(DateTime, default=func.now(), nullable=False)

class PatientAllergyRecord(TenantScoped, Base):
    __tablename__ = "hlt_patient_allergies"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    allergen = Column(String(150), nullable=False)
    allergy_type = Column(String(50), default="medication")  # medication, food, environmental
    severity = Column(String(50), default="moderate")  # mild, moderate, severe, anaphylactic
    reaction = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
