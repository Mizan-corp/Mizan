from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime

class FacilityCreate(BaseModel):
    name: str
    name_en: Optional[str] = None
    code: str
    facility_type: str = "clinic"
    phone: Optional[str] = None
    email: Optional[str] = None
    license_no: Optional[str] = None
    accreditation: Optional[str] = None
    currency: str = "SAR"
    operating_hours: Optional[Any] = None

class FacilityResponse(FacilityCreate):
    id: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DepartmentCreate(BaseModel):
    facility_id: int
    name: str
    name_en: Optional[str] = None
    code: str
    dept_type: str = "outpatient"
    floor: Optional[str] = None

class DepartmentResponse(DepartmentCreate):
    id: int
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
