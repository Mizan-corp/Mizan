from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class MedicationAdminRecord(TenantScoped, Base):
    __tablename__ = "hlt_mar_records"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    medication_name = Column(String(150), nullable=False)
    dosage = Column(String(50), nullable=False)
    route = Column(String(30), default="oral")  # oral, iv, im, sc
    scheduled_time = Column(String(30), nullable=False)
    status = Column(String(30), default="given")  # given, missed, refused
    nurse_notes = Column(Text, nullable=True)
    administered_at = Column(DateTime, default=func.now(), nullable=False)
