from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SaleItemCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0)

    @field_validator('qty')
    def qty_positive(cls, v):
        if v <= 0:
            raise ValueError('qty must be > 0')
        return v

    unit_price: Decimal
    unit_cost: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")

    @field_validator('discount')
    def discount_max(cls, v, info):
        if v < 0:
            raise ValueError('discount cannot be negative')
        values = info.data if hasattr(info, 'data') else {}
        unit_price = values.get('unit_price')
        qty = values.get('qty')
        if unit_price and qty and v > unit_price * qty:
            raise ValueError('discount cannot exceed item total')
        return v


class SaleItemUpdate(BaseModel):
    qty: Decimal = Field(..., gt=0)
    expected_qty: Decimal | None = None


class SplitPaymentItem(BaseModel):
    method: str = Field(..., pattern=r"^(cash|wallet|credit|bank|cheque)$")
    amount: Decimal = Field(..., gt=0)
    wallet_id: uuid.UUID | None = None


class SaleCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    shift_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID
    sale_mode: str = Field(default="retail", pattern=r"^(retail|wholesale)$")
    items: list[SaleItemCreate]
    is_credit: bool = False
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    payment_method: str = Field(default="cash", pattern=r"^(cash|wallet|credit|bank|cheque)$")
    wallet_id: uuid.UUID | None = None
    paid_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    payments: list[SplitPaymentItem] | None = None
    # Values of the fields the activity's variants and the workspace add (framework/fields.py).
    extra: dict = Field(default_factory=dict)
    local_id: str | None = None  # idempotency key for offline sync dedup
    allow_negative_stock: bool = False
    is_offline_sync: bool = False


class UpdateSaleItem(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)


class UpdateSale(BaseModel):
    items: list[UpdateSaleItem] = []
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None
    customer_id: uuid.UUID | None = None


class ConfirmQuotationRequest(BaseModel):
    """وجهة فلوس عرض السعر عند التأكيد — درج (وردية مفتوحة) أو خزنة أو على حساب العميل (آجل)."""
    destination: Literal["drawer", "safe", "credit"] = "drawer"
    safe_id: uuid.UUID | None = None


class PartialReturnItem(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0)


class PartialReturnRequest(BaseModel):
    items: list[PartialReturnItem]
    shift_id: uuid.UUID | None = None


class SaleItemOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str | None = None
    qty: Decimal
    unit_price: Decimal
    unit_cost: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    # VAT stored at the time of the document (ADR-014 D6).
    tax_code: str | None = None
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    net_amount: Decimal | None = None
    extra: dict = Field(default_factory=dict)
    model_config = {"from_attributes": True}


class SaleOut(BaseModel):
    id: uuid.UUID
    invoice_number: str
    customer_id: uuid.UUID | None
    customer_name: str | None = None
    warehouse_id: uuid.UUID
    cashier_id: uuid.UUID
    shift_id: uuid.UUID | None
    total: Decimal
    discount_amount: Decimal
    net_total: Decimal
    tax_amount: Decimal = Decimal("0")
    paid_amount: Decimal | None
    is_credit: bool
    status: str
    sale_mode: str
    payment_method: str
    wallet_id: uuid.UUID | None
    notes: str | None
    extra: dict = Field(default_factory=dict)
    # A return document points to the sale it returns; a sale shows how much has been returned.
    return_of: uuid.UUID | None = None
    returns_total: Decimal | None = None
    created_at: datetime
    items: list[SaleItemOut] = []
    model_config = {"from_attributes": True}
