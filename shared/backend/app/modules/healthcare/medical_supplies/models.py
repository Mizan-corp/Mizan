from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class MedicalSupplyItem(TenantScoped, Base):
    __tablename__ = "hlt_medical_items"
    id = Column(Integer, primary_key=True, index=True)
    item_code = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    category = Column(String(50), default="consumable")
    unit = Column(String(30), default="piece")
    stock_qty = Column(Integer, default=0)
    min_alert_qty = Column(Integer, default=10)
    cost_price = Column(Numeric(10, 2), default=0.0)
