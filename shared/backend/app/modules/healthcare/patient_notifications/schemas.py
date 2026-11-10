from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class AlertCreate(BaseModel):
    alert_type: str
    patient_id: Optional[int] = None
    title: str
    message: str
    priority: str = "normal"

class AlertResponse(AlertCreate):
    id: int
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
