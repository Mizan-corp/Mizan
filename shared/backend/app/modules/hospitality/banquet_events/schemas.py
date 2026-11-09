"""Pydantic schemas for Banquet & Events module."""
from typing import Optional
from pydantic import BaseModel


class BanquetEventCreate(BaseModel):
    hall_name: str
    client_name: str
    client_phone: str
    event_type: str = "حفل زفاف راقي (Wedding Gala)"
    event_date: str
    start_time: str = "19:00"
    end_time: str = "01:00"
    guest_count: int = 150
    catering_package: str = "بوفيه ملكي فاخر VIP"
    total_amount: float
    deposit_amount: float = 0.0


class BanquetStatusUpdate(BaseModel):
    status: str
