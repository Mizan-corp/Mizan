from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base
from app.core.tenancy import TenantScoped

class RadiologyStudyOrder(TenantScoped, Base):
    __tablename__ = "hlt_radiology_orders"
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    doctor_id = Column(Integer, nullable=False)
    modality = Column(String(20), nullable=False)  # XR, CT, MRI, US
    body_part = Column(String(100), nullable=False)
    clinical_notes = Column(Text, nullable=True)
    findings = Column(Text, nullable=True)
    status = Column(String(30), default="scheduled")  # scheduled, completed, reported
    created_at = Column(DateTime, default=func.now(), nullable=False)
