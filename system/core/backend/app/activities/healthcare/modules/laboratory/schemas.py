from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class LabTestCreate(BaseModel):
    code: str
    name: str
    category: str = "biochemistry"
    sample_type: str = "blood"
    unit: Optional[str] = None
    normal_range: Optional[str] = None
    price: float = 0.0

class LabTestResponse(LabTestCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)

class SpecimenCreate(BaseModel):
    barcode: str
    patient_id: int
    test_id: int

class SpecimenResponse(SpecimenCreate):
    id: int
    result_value: Optional[str] = None
    is_abnormal: bool
    is_critical: bool
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
