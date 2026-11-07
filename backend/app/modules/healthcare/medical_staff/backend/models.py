from sqlalchemy import Column, Integer, String, Text, Boolean, Numeric, Date, DateTime, func
from app.db.base import Base
from app.core.tenancy import TenantScoped

class MedicalStaff(TenantScoped, Base):
    __tablename__ = "hlt_medical_staff"
    id = Column(Integer, primary_key=True, index=True)
    staff_type = Column(String(50), default="physician")  # physician, surgeon, nurse, technician, pharmacist
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    specialty = Column(String(100), nullable=False)
    license_number = Column(String(100), nullable=True)
    license_expiry = Column(Date, nullable=True)
    consultation_fee = Column(Numeric(10, 2), default=0.0)
    commission_rate = Column(Numeric(5, 2), default=0.0)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
