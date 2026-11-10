from sqlalchemy import Column, Integer, String, Text, Boolean, Numeric, Date, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class MedicationProduct(TenantScoped, Base):
    __tablename__ = "hlt_pharmacy_formulary"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False)
    trade_name = Column(String(150), nullable=False)
    generic_name = Column(String(150), nullable=False)
    dosage_form = Column(String(50), default="tablet")
    strength = Column(String(50), nullable=True)
    unit_price = Column(Numeric(10, 2), default=0.0)
    stock_qty = Column(Integer, default=0)
    is_controlled = Column(Boolean, default=False)

class MedicationDispenseRecord(TenantScoped, Base):
    __tablename__ = "hlt_prescription_dispense"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    medication_id = Column(Integer, nullable=False)
    quantity = Column(Integer, default=1)
    dispensed_by = Column(String(100), nullable=True)
    dispensed_at = Column(DateTime, default=func.now(), nullable=False)
