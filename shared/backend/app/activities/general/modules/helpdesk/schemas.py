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
