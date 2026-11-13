from sqlalchemy import Column, Integer, String, Text, Date, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class MedicalAppointment(TenantScoped, Base):
    __tablename__ = "hlt_appointments"
    id = Column(Integer, primary_key=True, index=True)
    appointment_number = Column(String(50), nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    doctor_id = Column(Integer, nullable=False, index=True)
    department_id = Column(Integer, nullable=True)
    service_type = Column(String(50), default="consultation")
    appointment_date = Column(Date, nullable=False, index=True)
    start_time = Column(String(20), nullable=False)
    end_time = Column(String(20), nullable=True)
    status = Column(String(30), default="scheduled")  # scheduled, confirmed, arrived, in_progress, completed, cancelled, no_show
    cancellation_reason = Column(Text, nullable=True)
    queue_number = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
