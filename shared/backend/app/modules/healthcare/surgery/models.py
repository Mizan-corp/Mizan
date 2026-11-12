from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class SurgicalCase(TenantScoped, Base):
    __tablename__ = "hlt_surgical_cases"
    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(50), nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    surgeon_id = Column(Integer, nullable=False)
    theater_name = Column(String(50), nullable=False)
    procedure_name = Column(String(200), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    who_checklist_completed = Column(Boolean, default=False)
    status = Column(String(30), default="scheduled")  # scheduled, in_surgery, recovery, completed
    created_at = Column(DateTime, default=func.now(), nullable=False)
