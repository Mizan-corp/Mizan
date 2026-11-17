from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# Bounds of the columns (Numeric(12,3) quantities, Numeric(12,2) money): larger values were a 500.
MAX_QTY = Decimal("999999999")
MAX_MONEY = Decimal("9999999999")


class SaleItemCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0, le=MAX_QTY)
    # The product's price unless the workspace allows another (checked on the server, SAL-1).
    unit_price: Decimal = Field(..., ge=0, le=MAX_MONEY)
    unit_cost: Decimal = Field(Decimal("0"), ge=0, le=MAX_MONEY)  # ignored: the cost is the average (D5)
    discount: Decimal = Field(Decimal("0"), ge=0, le=MAX_MONEY)

    @field_validator('discount')
    def discount_max(cls, v, info):
        values = info.data if hasattr(info, 'data') else {}
        unit_price = values.get('unit_price')
        qty = values.get('qty')
        if unit_price is not None and qty and v > unit_price * qty:
            raise ValueError('الخصم أكبر من إجمالي البند')
        return v


class SaleItemUpdate(BaseModel):
    qty: Decimal = Field(..., gt=0, le=MAX_QTY)
    expected_qty: Decimal | None = None


class SplitPaymentItem(BaseModel):
    method: Literal["cash", "wallet", "credit", "bank", "cheque"]
    amount: Decimal = Field(..., gt=0, le=MAX_MONEY)
    wallet_id: uuid.UUID | None = None


class SaleCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    shift_id: uuid.UUID | None = None
    warehouse_id: uuid.UUID
    sale_mode: Literal["retail", "wholesale"] = "retail"
    items: list[SaleItemCreate] = Field(..., min_length=1, max_length=500)
    is_credit: bool = False
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0, le=MAX_MONEY)
    payment_method: Literal["cash", "wallet", "credit", "bank", "cheque"] = "cash"
    wallet_id: uuid.UUID | None = None
    paid_amount: Decimal | None = Field(default=None, ge=0, le=MAX_MONEY)
    notes: str | None = Field(default=None, max_length=2000)
    payments: list[SplitPaymentItem] | None = Field(default=None, max_length=20)
    # Values of the fields the activity's variants and the workspace add (framework/fields.py).
    extra: dict = Field(default_factory=dict)
    # The POS's own id for this sale (a UUID made on the device, kept across retries and the
    # offline queue): sending it again returns the sale already recorded (SAL-2). Whether stock
    # may go below zero is decided on the server, never by the client.
    local_id: uuid.UUID | None = None


class UpdateSaleItem(SaleItemCreate):
    pass


class UpdateSale(BaseModel):
    items: list[UpdateSaleItem] = Field(default_factory=list, max_length=500)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0, le=MAX_MONEY)
    notes: str | None = Field(default=None, max_length=2000)
    customer_id: uuid.UUID | None = None


class ConfirmQuotationRequest(BaseModel):
    """وجهة فلوس عرض السعر عند التأكيد — درج (وردية مفتوحة) أو خزنة أو على حساب العميل (آجل)."""
    destination: Literal["drawer", "safe", "credit"] = "drawer"
    safe_id: uuid.UUID | None = None


class PartialReturnItem(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0, le=MAX_QTY)


class PartialReturnRequest(BaseModel):
    items: list[PartialReturnItem] = Field(..., min_length=1, max_length=500)
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
