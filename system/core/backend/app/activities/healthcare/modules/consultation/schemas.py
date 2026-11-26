from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class EncounterCreate(BaseModel):
    encounter_number: str
    patient_id: int
    doctor_id: int
    chief_complaint: str
    examination: Optional[str] = None
    diagnosis: Optional[str] = None
    icd10_code: Optional[str] = None
    treatment_plan: Optional[str] = None

class EncounterResponse(EncounterCreate):
    id: int
    status: str
    signed_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
