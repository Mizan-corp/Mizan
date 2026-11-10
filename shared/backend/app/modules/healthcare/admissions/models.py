from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base
from app.core.tenancy import TenantScoped

class InpatientAdmission(TenantScoped, Base):
    __tablename__ = "hlt_inpatient_admissions"
    id = Column(Integer, primary_key=True, index=True)
    admission_number = Column(String(50), nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    doctor_id = Column(Integer, nullable=False)
    ward_id = Column(Integer, nullable=True)
    bed_id = Column(Integer, nullable=True)
    admission_date = Column(DateTime, default=func.now(), nullable=False)
    discharge_date = Column(DateTime, nullable=True)
    admission_reason = Column(Text, nullable=False)
    discharge_summary = Column(Text, nullable=True)
    status = Column(String(30), default="admitted")  # admitted, discharged, transferred
