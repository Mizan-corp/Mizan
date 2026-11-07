from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class VitalCreate(BaseModel):
    patient_id: int
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    pulse_rate: Optional[int] = None
    temperature: Optional[float] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None

class VitalResponse(VitalCreate):
    id: int
    bmi: Optional[float] = None
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AllergyCreate(BaseModel):
    patient_id: int
    allergen: str
    allergy_type: str = "medication"
    severity: str = "moderate"
    reaction: Optional[str] = None

class AllergyResponse(AllergyCreate):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
