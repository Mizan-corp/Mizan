from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime

class SurgicalCaseCreate(BaseModel):
    case_number: str
    patient_id: int
    surgeon_id: int
    theater_name: str
    procedure_name: str
    scheduled_date: date

class SurgicalCaseResponse(SurgicalCaseCreate):
    id: int
    who_checklist_completed: bool
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
