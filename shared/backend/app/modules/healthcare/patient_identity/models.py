from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, func
from app.db.base import Base
from app.core.tenancy import TenantScoped

class PatientIdentity(TenantScoped, Base):
    __tablename__ = "hlt_patients"
    id = Column(Integer, primary_key=True, index=True)
    mrn = Column(String(50), nullable=False, index=True)
    national_id = Column(String(50), nullable=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), default="unknown")  # male, female, other
    phone = Column(String(50), nullable=False, index=True)
    email = Column(String(100), nullable=True)
    blood_group = Column(String(10), nullable=True)
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    guardian_name = Column(String(100), nullable=True)
    is_merged = Column(Boolean, default=False)
    merged_into_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
