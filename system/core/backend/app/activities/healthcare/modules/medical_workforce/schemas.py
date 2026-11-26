from pydantic import BaseModel, ConfigDict
from datetime import date

class CredentialCreate(BaseModel):
    staff_id: int
    credential_title: str
    issuing_authority: str
    expiry_date: date

class CredentialResponse(CredentialCreate):
    id: int
    status: str
    model_config = ConfigDict(from_attributes=True)
