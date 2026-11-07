from pydantic import BaseModel, ConfigDict
from typing import Optional

class WardCreate(BaseModel):
    name: str
    code: str
    ward_type: str = "general"
    floor: Optional[str] = None

class WardResponse(WardCreate):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class BedCreate(BaseModel):
    ward_id: int
    bed_number: str
    bed_type: str = "standard"
    daily_rate: float = 0.0

class BedResponse(BedCreate):
    id: int
    status: str
    current_patient_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
