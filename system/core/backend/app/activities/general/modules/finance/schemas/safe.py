from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# A positive amount of money that fits the Numeric(14, 2) columns.
Amount = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
Note = Annotated[str, Field(max_length=500)]


class SafeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    location: str | None = Field(None, max_length=256)
    # A bank account is a safe of type bank: bank transfers and cheques are paid into or out of it.
    safe_type: Literal["permanent", "temporary", "bank"] = "permanent"


class SafeUpdate(BaseModel):
    """Only the fields sent change."""
    name: str | None = Field(None, min_length=1, max_length=128)
    location: str | None = Field(None, max_length=256)
    safe_type: Literal["permanent", "temporary", "bank"] | None = None


class SafeTransferCreate(BaseModel):
    from_wallet_id: uuid.UUID
    to_safe_id: uuid.UUID
    amount: Amount
    note: Note | None = None
    # The attempt's id: sending the same one again returns the first result (or Idempotency-Key).
    client_id: uuid.UUID | None = None


class SafeDepositCreate(BaseModel):
    """A deposit made by hand. A shift's cash reaches a safe through the shift (revenue delivery,
    closing with a manager), never by naming a shift here."""
    amount: Amount
    warehouse_id: uuid.UUID | None = None
    received_by_id: uuid.UUID | None = None
    notes: Note | None = None
    client_id: uuid.UUID | None = None


class SafeWithdrawCreate(BaseModel):
    amount: Amount
    note: Note | None = None
    client_id: uuid.UUID | None = None
