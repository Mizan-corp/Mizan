"""Pydantic schemas for Housekeeping module."""
from typing import Optional
from pydantic import BaseModel


class HousekeepingTaskCreate(BaseModel):
    room_number: str
    task_type: str = "تنظيف مغادرة (Checkout Clean)"
    priority: str = "normal"  # urgent, high, normal
    assigned_to: str
    notes: Optional[str] = ""


class TaskCompleteRequest(BaseModel):
    notes: Optional[str] = ""
