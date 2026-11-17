from datetime import date as date_type
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.activities.general.modules.finance.schemas.safe import Amount

# How an expense is paid. "safe" is the older spelling of cash from a safe.
PaymentMethod = Literal["cash", "safe", "bank", "cheque", "card", "wallet"]
ExpenseStatus = Literal["draft", "approved", "rejected", "cancelled"]
RecurringInterval = Literal["weekly", "monthly", "yearly"]


class ExpenseVendorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    phone: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=500)
    tax_id: str | None = Field(None, max_length=64)
    notes: str | None = Field(None, max_length=2000)


class ExpenseVendorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    phone: str | None = Field(None, max_length=32)
    address: str | None = Field(None, max_length=500)
    tax_id: str | None = Field(None, max_length=64)
    notes: str | None = Field(None, max_length=2000)
    is_active: bool | None = None


class ExpenseCreate(BaseModel):
    vendor_id: UUID | None = None
    category_id: UUID | None = None
    warehouse_id: UUID | None = None
    amount: Amount
    description: str = Field(..., min_length=1, max_length=1000)
    date: date_type | None = None
    payment_method: PaymentMethod | None = None
    wallet_id: UUID | None = None
    safe_id: UUID | None = None
    is_recurring: bool = False
    recurring_interval: RecurringInterval | None = None
    recurring_end_date: date_type | None = None
    notes: str | None = Field(None, max_length=2000)


class ExpenseUpdate(BaseModel):
    vendor_id: UUID | None = None
    category_id: UUID | None = None
    warehouse_id: UUID | None = None
    amount: Amount | None = None
    description: str | None = Field(None, min_length=1, max_length=1000)
    date: date_type | None = None
    payment_method: PaymentMethod | None = None
    wallet_id: UUID | None = None
    safe_id: UUID | None = None
    # Not changed here: approve, reject and cancel have their own routes.
    status: ExpenseStatus | None = None
    notes: str | None = Field(None, max_length=2000)


class ExpenseApprove(BaseModel):
    approved: bool = True
    notes: str | None = Field(None, max_length=2000)
    # The money's source, if the draft doesn't name it yet.
    safe_id: UUID | None = None
    wallet_id: UUID | None = None


class ExpenseCancel(BaseModel):
    reason: str | None = Field(None, max_length=500)
