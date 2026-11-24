"""Strict internal input, no inferred currency or final-price semantics."""
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class OfferingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=5000)
    starting_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @field_validator("currency")
    @classmethod
    def currency_supported(cls, value):
        # Explicit supported ISO subset, extend deliberately with UI/formatting coverage.
        if value not in {"EGP", "USD", "EUR", "GBP", "SAR", "AED", "QAR"}:
            raise ValueError("unsupported currency")
        return value

class OfferingArchive(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    is_active: bool

from uuid import UUID
from typing import Literal

class FsmCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_id: str
    expected_status: Literal['dispatched','on_site','parts_needed']
    completion_notes: str = Field(min_length=1,max_length=5000)

    @field_validator('operation_id')
    @classmethod
    def valid_operation(cls,value):
        return str(UUID(value))

    @field_validator('completion_notes')
    @classmethod
    def meaningful_notes(cls,value):
        if not value.strip():raise ValueError('completion notes required')
        return value

class PropertyRequestCreate(BaseModel):
    model_config = ConfigDict(extra='forbid',strict=True,str_strip_whitespace=True)
    operation_id: str
    unit_id: str = Field(min_length=1,max_length=36)
    category: str = Field(min_length=1,max_length=64)
    description: str = Field(min_length=1,max_length=5000)
    reported_by: str = Field(min_length=1,max_length=128)

    @field_validator('operation_id','unit_id')
    @classmethod
    def valid_uuid(cls,value):return str(UUID(value))
