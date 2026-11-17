"""Accounting: request and response schemas."""
import uuid
from datetime import date as Date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    parent_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=200)
    name_en: str | None = Field(None, max_length=200)
    code: str | None = Field(None, min_length=1, max_length=32, pattern=r"^[0-9A-Za-z.\-]+$")
    is_group: bool = False


class AccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    name_en: str | None = Field(None, max_length=200)
    active: bool | None = None


class CategoryAccount(BaseModel):
    account_id: uuid.UUID | None = None


class OpeningCreate(BaseModel):
    date: Date | None = None  # the start date; today when omitted


class SettingsUpdate(BaseModel):
    fiscal_year_start: int = Field(..., ge=1, le=12)


class DraftLineIn(BaseModel):
    account_id: uuid.UUID
    debit: Decimal = Field(Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    credit: Decimal = Field(Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    party_type: Literal["customer", "supplier", "employee"] | None = None
    party_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID | None = None


class DraftIn(BaseModel):
    """A manual journal entry (D9): saved as a draft, posted later."""
    date: Date
    memo: str | None = Field(None, max_length=500)
    warehouse_id: uuid.UUID | None = None
    lines: list[DraftLineIn] = Field(default_factory=list, max_length=200)


class ReverseIn(BaseModel):
    date: Date | None = None  # today for a manual entry, the entry's own date for the opening entry
    memo: str | None = Field(None, max_length=300)
