from sqlalchemy import Column, Integer, String, Numeric, DateTime, func
from app.db.base import Base
from app.core.tenancy import TenantScoped

class PatientInvoice(TenantScoped, Base):
    __tablename__ = "hlt_patient_invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), nullable=False, index=True)
    patient_id = Column(Integer, nullable=False, index=True)
    total_amount = Column(Numeric(10, 2), default=0.0)
    insurance_share = Column(Numeric(10, 2), default=0.0)
    patient_share = Column(Numeric(10, 2), default=0.0)
    paid_amount = Column(Numeric(10, 2), default=0.0)
    payment_status = Column(String(30), default="unpaid")  # unpaid, partially_paid, paid
    created_at = Column(DateTime, default=func.now(), nullable=False)
