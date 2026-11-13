from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class EmergencyCaseCreate(BaseModel):
    case_number: str
    patient_id: int
    triage_level: int = 3
    chief_complaint: str
    arrival_mode: str = "walk_in"
    assigned_bay: Optional[str] = None

class EmergencyCaseResponse(EmergencyCaseCreate):
    id: int
    status: str
    arrived_at: datetime
    model_config = ConfigDict(from_attributes=True)
