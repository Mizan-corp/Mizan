from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date, datetime

class StaffCreate(BaseModel):
    staff_type: str = "physician"
    first_name: str
    last_name: str
    specialty: str
    license_number: Optional[str] = None
    license_expiry: Optional[date] = None
    consultation_fee: float = 0.0
    commission_rate: float = 0.0
    phone: Optional[str] = None
    email: Optional[str] = None

class StaffResponse(StaffCreate):
    id: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
