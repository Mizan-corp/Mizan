from sqlalchemy import Column, Integer, String, Text, Boolean, Numeric, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class LabTestItem(TenantScoped, Base):
    __tablename__ = "hlt_lab_catalog"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    category = Column(String(50), default="biochemistry")
    sample_type = Column(String(50), default="blood")
    unit = Column(String(30), nullable=True)
    normal_range = Column(String(100), nullable=True)
    price = Column(Numeric(10, 2), default=0.0)

class LabSpecimenOrder(TenantScoped, Base):
    __tablename__ = "hlt_lab_specimens"
    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String(50), nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    test_id = Column(Integer, nullable=False)
    result_value = Column(String(100), nullable=True)
    is_abnormal = Column(Boolean, default=False)
    is_critical = Column(Boolean, default=False)
    status = Column(String(30), default="collected")  # collected, processing, completed
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
