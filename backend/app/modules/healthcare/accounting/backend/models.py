from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, func
from app.db.base import Base
from app.core.tenancy import TenantScoped

class HealthcareCostCenter(TenantScoped, Base):
    __tablename__ = "hlt_cost_centers"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    center_type = Column(String(50), default="cost_center")  # cost_center, revenue_center
    budget = Column(Numeric(12, 2), default=0.0)
    actual_spent = Column(Numeric(12, 2), default=0.0)
