from __future__ import annotations

import uuid as _uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    phone: str | None = Field(None, max_length=32)
    address: str | None = None
    is_cash: bool = False
    credit_limit: Decimal | None = Field(None, ge=0)
    extra: dict = Field(default_factory=dict)  # custom fields (app/framework/fields.py)


class CustomerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    phone: str | None = Field(None, max_length=32)
    address: str | None = None
    is_cash: bool | None = None
    credit_limit: Decimal | None = Field(None, ge=0)
    extra: dict | None = None


class CustomerPaymentCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)
    note: str | None = None
    sale_id: _uuid.UUID | None = None
    # Where the money went: a safe (bank accounts are safes of type bank) or a wallet. Cash with
    # neither goes into the receiving cashier's open drawer.
    method: str | None = Field(None, max_length=32)
    safe_id: _uuid.UUID | None = None
    wallet_id: _uuid.UUID | None = None


class SetBalanceRequest(BaseModel):
    """The balance the customer should have; the difference is recorded as an adjustment."""
    balance: Decimal = Field(default=Decimal("0"))
    note: str | None = None


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    phone: str | None = Field(None, max_length=32)
    address: str | None = None



