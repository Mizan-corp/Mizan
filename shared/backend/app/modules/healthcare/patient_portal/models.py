from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class PatientPortalRequest(TenantScoped, Base):
    __tablename__ = "hlt_portal_requests"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    request_type = Column(String(50), nullable=False)  # appointment_booking, refill, report_copy
    details = Column(Text, nullable=True)
    status = Column(String(30), default="submitted")  # submitted, approved, rejected, completed
    created_at = Column(DateTime, default=func.now(), nullable=False)
