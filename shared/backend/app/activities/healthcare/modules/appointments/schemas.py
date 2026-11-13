from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime

class AppointmentCreate(BaseModel):
    appointment_number: str
    patient_id: int
    doctor_id: int
    department_id: Optional[int] = None
    service_type: str = "consultation"
    appointment_date: date
    start_time: str
    notes: Optional[str] = None

class AppointmentResponse(AppointmentCreate):
    id: int
    status: str
    queue_number: Optional[int] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class StatusUpdate(BaseModel):
    status: str
    cancellation_reason: Optional[str] = None
