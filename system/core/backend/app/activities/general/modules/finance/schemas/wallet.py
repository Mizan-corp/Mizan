from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class WalletCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    type: str = Field(..., min_length=1, max_length=32)
    phone: str | None = Field(None, max_length=32)


class WalletUpdate(BaseModel):
    """Only the fields sent change."""
    name: str | None = Field(None, min_length=1, max_length=128)
    type: str | None = Field(None, min_length=1, max_length=32)
    phone: str | None = Field(None, max_length=32)


class WalletReset(BaseModel):
    # The attempt's id: sending the same one again returns the first result (or Idempotency-Key).
    client_id: uuid.UUID | None = None
