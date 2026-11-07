from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from app.db.base import Base
from app.core.tenancy import TenantScoped

class HealthcareAlert(TenantScoped, Base):
    __tablename__ = "hlt_alerts"
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(50), nullable=False)  # critical_lab, missed_med, emergency, appointment_reminder
    patient_id = Column(Integer, nullable=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    priority = Column(String(20), default="normal")  # normal, urgent, emergency
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
