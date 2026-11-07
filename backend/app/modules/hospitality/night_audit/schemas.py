"""Pydantic schemas for Night Audit module."""
from typing import Optional
from pydantic import BaseModel


class NightAuditRunRequest(BaseModel):
    audit_date: Optional[str] = None
    conducted_by: Optional[str] = "المدقق الليلي الآلي"
