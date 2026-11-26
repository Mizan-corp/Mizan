from pydantic import BaseModel, ConfigDict
from datetime import datetime

class ClaimCreate(BaseModel):
    claim_number: str
    provider_name: str
    patient_id: int
    claimed_amount: float

class ClaimResponse(ClaimCreate):
    id: int
    approved_amount: float
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
