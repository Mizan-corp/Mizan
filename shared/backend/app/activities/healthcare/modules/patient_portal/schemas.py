from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class PortalRequestCreate(BaseModel):
    patient_id: int
    request_type: str
    details: Optional[str] = None

class PortalRequestResponse(PortalRequestCreate):
    id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
