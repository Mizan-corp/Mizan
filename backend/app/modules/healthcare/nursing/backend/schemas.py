from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class MARCreate(BaseModel):
    patient_id: int
    medication_name: str
    dosage: str
    route: str = "oral"
    scheduled_time: str
    status: str = "given"
    nurse_notes: Optional[str] = None

class MARResponse(MARCreate):
    id: int
    administered_at: datetime
    model_config = ConfigDict(from_attributes=True)
