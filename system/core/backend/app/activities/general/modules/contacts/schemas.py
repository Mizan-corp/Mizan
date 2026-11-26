from __future__ import annotations

import uuid as _uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

# Money that fits the Numeric(14, 2) columns.
Amount = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Balance = Annotated[Decimal, Field(max_digits=14, decimal_places=2)]
Limit = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
# How a receipt was paid; where the money went is the safe or wallet (or the cashier's drawer).
PaymentMethod = Literal["cash", "bank", "cheque", "card", "wallet"]


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    phone: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=500)
    is_cash: bool = False
    credit_limit: Limit | None = None
    extra: dict = Field(default_factory=dict)  # custom fields (app/framework/fields.py)


class CustomerUpdate(BaseModel):
    """Only the fields sent change; the name and the cash flag can't be emptied."""
    name: str | None = Field(None, min_length=1, max_length=128)
    phone: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=500)
    is_cash: bool | None = None
    credit_limit: Limit | None = None
    extra: dict | None = None

    @field_validator("name", "is_cash")
    @classmethod
    def not_null(cls, v):
        if v is None:
            raise ValueError("لا يمكن أن تكون القيمة فارغة")
        return v


class CustomerPaymentCreate(BaseModel):
    # customer_payments.amount is Numeric(12, 2).
    amount: Amount
    note: str | None = Field(None, max_length=500)
    sale_id: _uuid.UUID | None = None
    # Where the money went: a safe (bank accounts are safes of type bank) or a wallet. Cash with
    # neither goes into the receiving cashier's open drawer.
    method: PaymentMethod | None = None
    safe_id: _uuid.UUID | None = None
    wallet_id: _uuid.UUID | None = None
    # The attempt's id: sending the same one again returns the first receipt (or Idempotency-Key).
    client_id: _uuid.UUID | None = None


class PaymentReverse(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class SetBalanceRequest(BaseModel):
    """The balance the customer should have; the difference is recorded as an adjustment."""
    balance: Balance = Field(default=Decimal("0"))
    note: str | None = Field(None, max_length=500)
