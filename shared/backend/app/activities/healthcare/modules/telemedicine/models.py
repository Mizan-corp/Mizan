from sqlalchemy import Column, Integer, String, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class TeleconsultationSession(TenantScoped, Base):
    __tablename__ = "hlt_teleconsultations"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    doctor_id = Column(Integer, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    meeting_link = Column(String(255), nullable=True)
    status = Column(String(30), default="waiting")  # waiting, active, completed
    created_at = Column(DateTime, default=func.now(), nullable=False)
