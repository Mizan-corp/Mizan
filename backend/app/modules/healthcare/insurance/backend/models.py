from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, func
from app.db.base import Base
from app.core.tenancy import TenantScoped

class InsuranceClaimRecord(TenantScoped, Base):
    __tablename__ = "hlt_insurance_claims"
    id = Column(Integer, primary_key=True, index=True)
    claim_number = Column(String(50), nullable=False, index=True)
    provider_name = Column(String(100), nullable=False)
    patient_id = Column(Integer, nullable=False, index=True)
    claimed_amount = Column(Numeric(10, 2), default=0.0)
    approved_amount = Column(Numeric(10, 2), default=0.0)
    status = Column(String(30), default="submitted")  # submitted, approved, rejected, pending
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
