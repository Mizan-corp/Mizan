from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date

class DeviceCreate(BaseModel):
    asset_tag: str
    device_name: str
    serial_number: Optional[str] = None
    department_name: Optional[str] = None
    next_calibration_due: Optional[date] = None

class DeviceResponse(DeviceCreate):
    id: int
    status: str
    model_config = ConfigDict(from_attributes=True)
