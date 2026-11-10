from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class EmergencyCase(TenantScoped, Base):
    __tablename__ = "hlt_emergency_admissions"
    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(50), nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    triage_level = Column(Integer, default=3)  # 1 (resuscitation) to 5 (non-urgent)
    chief_complaint = Column(Text, nullable=False)
    arrival_mode = Column(String(50), default="walk_in")  # walk_in, ambulance
    assigned_bay = Column(String(50), nullable=True)
    status = Column(String(30), default="triaged")  # triaged, under_treatment, admitted, discharged
    arrived_at = Column(DateTime, default=func.now(), nullable=False)
