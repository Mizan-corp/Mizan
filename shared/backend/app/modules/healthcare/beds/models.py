from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class HospitalWard(TenantScoped, Base):
    __tablename__ = "hlt_hospital_wards"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=False)
    ward_type = Column(String(50), default="general")  # general, icu, surgical, pediatric, maternity
    floor = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)

class HospitalBed(TenantScoped, Base):
    __tablename__ = "hlt_hospital_beds"
    id = Column(Integer, primary_key=True, index=True)
    ward_id = Column(Integer, nullable=False, index=True)
    bed_number = Column(String(50), nullable=False)
    bed_type = Column(String(50), default="standard")
    daily_rate = Column(Numeric(10, 2), default=0.0)
    status = Column(String(30), default="available")  # available, occupied, cleaning, maintenance
    current_patient_id = Column(Integer, nullable=True)
