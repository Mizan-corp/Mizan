from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class TeleconsultationCreate(BaseModel):
    session_id: str
    patient_id: int
    doctor_id: int
    scheduled_at: datetime
    meeting_link: Optional[str] = None

class TeleconsultationResponse(TeleconsultationCreate):
    id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
