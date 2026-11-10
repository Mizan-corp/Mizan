from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, func
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class HealthcareDailyMetric(TenantScoped, Base):
    __tablename__ = "hlt_daily_metrics"
    id = Column(Integer, primary_key=True, index=True)
    metric_date = Column(Date, nullable=False, index=True)
    total_visits = Column(Integer, default=0)
    admissions_count = Column(Integer, default=0)
    discharges_count = Column(Integer, default=0)
    bed_occupancy_rate = Column(Numeric(5, 2), default=0.0)
    average_wait_minutes = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now(), nullable=False)
