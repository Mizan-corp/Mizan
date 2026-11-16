"""Accounting: request and response schemas."""
import uuid

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
