from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class RadiologyOrderCreate(BaseModel):
    order_number: str
    patient_id: int
    doctor_id: int
    modality: str
    body_part: str
    clinical_notes: Optional[str] = None

class RadiologyOrderResponse(RadiologyOrderCreate):
    id: int
    findings: Optional[str] = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
