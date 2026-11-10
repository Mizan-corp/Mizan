from pydantic import BaseModel, ConfigDict
from datetime import date, datetime

class MetricResponse(BaseModel):
    metric_date: date
    total_visits: int
    admissions_count: int
    discharges_count: int
    bed_occupancy_rate: float
    average_wait_minutes: int
    model_config = ConfigDict(from_attributes=True)
