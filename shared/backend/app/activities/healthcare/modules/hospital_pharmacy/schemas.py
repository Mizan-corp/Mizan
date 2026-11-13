from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class MedicationCreate(BaseModel):
    code: str
    trade_name: str
    generic_name: str
    dosage_form: str = "tablet"
    strength: Optional[str] = None
    unit_price: float = 0.0
    stock_qty: int = 0
    is_controlled: bool = False

class MedicationResponse(MedicationCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class DispenseCreate(BaseModel):
    patient_id: int
    medication_id: int
    quantity: int = 1
    dispensed_by: Optional[str] = None

class DispenseResponse(DispenseCreate):
    id: int
    dispensed_at: datetime
    model_config = ConfigDict(from_attributes=True)
