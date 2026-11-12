from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func, JSON
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class HealthcareFacility(TenantScoped, Base):
    __tablename__ = "hlt_facilities"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    name_en = Column(String(150), nullable=True)
    code = Column(String(50), nullable=False, index=True)
    facility_type = Column(String(50), default="clinic")  # clinic, hospital, medical_center, lab
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    license_no = Column(String(100), nullable=True)
    accreditation = Column(String(100), nullable=True)
    currency = Column(String(10), default="SAR")
    operating_hours = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class FacilityDepartment(TenantScoped, Base):
    __tablename__ = "hlt_departments"
    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("hlt_facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=True)
    code = Column(String(50), nullable=False)
    dept_type = Column(String(50), default="outpatient")  # outpatient, inpatient, emergency, icu, laboratory, radiology, pharmacy, surgery
    floor = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
