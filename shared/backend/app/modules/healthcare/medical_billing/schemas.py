from pydantic import BaseModel, ConfigDict
from datetime import datetime

class InvoiceCreate(BaseModel):
    invoice_number: str
    patient_id: int
    total_amount: float
    insurance_share: float = 0.0
    patient_share: float

class InvoiceResponse(InvoiceCreate):
    id: int
    paid_amount: float
    payment_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
