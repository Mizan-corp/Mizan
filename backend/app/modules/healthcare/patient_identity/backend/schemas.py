from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime

class PatientCreate(BaseModel):
    mrn: str
    national_id: Optional[str] = None
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    gender: str = "male"
    phone: str
    email: Optional[str] = None
    blood_group: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    guardian_name: Optional[str] = None

class PatientResponse(PatientCreate):
    id: int
    is_merged: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
