from sqlalchemy import Column, Integer, String, Date, DateTime, func
from app.db.base import Base
from app.core.tenancy import TenantScoped

class ClinicalCredentialRecord(TenantScoped, Base):
    __tablename__ = "hlt_clinical_credentials"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, nullable=False, index=True)
    credential_title = Column(String(150), nullable=False)
    issuing_authority = Column(String(100), nullable=False)
    expiry_date = Column(Date, nullable=False)
    status = Column(String(30), default="active")  # active, expired, pending_renewal
