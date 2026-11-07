from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class AdmissionCreate(BaseModel):
    admission_number: str
    patient_id: int
    doctor_id: int
    ward_id: Optional[int] = None
    bed_id: Optional[int] = None
    admission_reason: str

class AdmissionResponse(AdmissionCreate):
    id: int
    admission_date: datetime
    discharge_date: Optional[datetime] = None
    status: str
    model_config = ConfigDict(from_attributes=True)
