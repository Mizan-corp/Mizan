"""Healthcare & Clinic/Hospital ERP: request and response schemas (Pydantic). Routes accept and return these, never
models. Most of the module's older schemas are still in router.py."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BreakGlassRequest(BaseModel):
    reason: str = Field(..., max_length=1000, description="سبب الوصول الطارئ (10 أحرف على الأقل)")


class BreakGlassReview(BaseModel):
    note: str = Field("", max_length=1000)


class CareTeamAdd(BaseModel):
    user_id: str
    role: Literal["attending", "consultant", "nurse", "other"] = "attending"
