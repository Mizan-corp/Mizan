from sqlalchemy import Column, Integer, String, Date
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class BiomedicalDevice(TenantScoped, Base):
    __tablename__ = "hlt_biomedical_devices"
    id = Column(Integer, primary_key=True, index=True)
    asset_tag = Column(String(50), nullable=False, index=True)
    device_name = Column(String(150), nullable=False)
    serial_number = Column(String(100), nullable=True)
    department_name = Column(String(100), nullable=True)
    last_calibration_date = Column(Date, nullable=True)
    next_calibration_due = Column(Date, nullable=True)
    status = Column(String(30), default="operational")  # operational, calibration_due, under_maintenance
