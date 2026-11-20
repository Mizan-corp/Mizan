from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class PurchaseItemCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0, le=Decimal("999999999"))
    unit_cost: Decimal = Field(..., ge=0, le=Decimal("9999999999"))
    notes: str | None = Field(None, max_length=1000)


class PurchaseCreate(BaseModel):
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=2000)
    amount_paid: Decimal | None = Field(None, ge=0, le=Decimal("9999999999"))
    # Where amount_paid comes from: a safe (or bank account) or a payment wallet.
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None
    received_by_name: str | None = Field(None, max_length=128)
    # Whether the unit costs include VAT (ADR-014 D6); omitted: the workspace's setting at receipt.
    prices_include_vat: bool | None = None
    items: list[PurchaseItemCreate] = Field(default_factory=list, max_length=500)


class PurchaseUpdate(BaseModel):
    """A draft's changes; omitted fields stay as they are. `supplier_id` null keeps the supplier
    (`clear_supplier` makes it a cash purchase)."""
    supplier_id: uuid.UUID | None = None
    clear_supplier: bool = False
    warehouse_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=2000)
    items: list[PurchaseItemCreate] | None = Field(None, min_length=1, max_length=500)


class ReceiveItemOverride(BaseModel):
    """What arrived of one line of the order: the line by its id (`item_id`) or by its product.
    `qty_received` 0 means nothing of it this time; a line not listed arrives in full (what is left
    of it)."""
    item_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    qty_received: Decimal | None = Field(None, ge=0, le=Decimal("999999999"))
    unit_cost: Decimal | None = Field(None, ge=0, le=Decimal("9999999999"))
    # Batch tracking (pharmacies, ADR-006 phase 4): which batch the stock comes in as.
    batch_number: str | None = Field(None, max_length=64)
    expiry_date: date | None = None

    @model_validator(mode="after")
    def names_a_line(self):
        if self.item_id is None and self.product_id is None:
            raise ValueError("حدد سطر أمر الشراء (item_id) أو الصنف (product_id)")
        return self


class PurchaseReceive(BaseModel):
    items: list[ReceiveItemOverride] = Field(default_factory=list, max_length=500)
    # What is paid on receipt and from where; when omitted, the order's own values are used (on its
    # first receipt only).
    amount_paid: Decimal | None = Field(None, ge=0, le=Decimal("9999999999"))
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None
    # Whether the unit costs include VAT (ADR-014 D6); omitted: what the order says, else the setting.
    prices_include_vat: bool | None = None
    notes: str | None = Field(None, max_length=1000)


class PurchaseCancel(BaseModel):
    reason: str | None = Field(None, max_length=500)


class QuickProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    unit: str = Field("عدد", max_length=32)
    cost_price: Decimal = Field(Decimal("0"), ge=0, le=Decimal("9999999999"))
    retail_price: Decimal = Field(Decimal("0"), ge=0, le=Decimal("9999999999"))
    wholesale_price: Decimal = Field(Decimal("0"), ge=0, le=Decimal("9999999999"))
    company: str | None = Field(None, max_length=128)
    subcategory_id: uuid.UUID | None = None


class PurchaseReturnItemIn(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0, le=Decimal("999999999"))


class PurchaseReturnCreate(BaseModel):
    """Goods sent back to the supplier from a received order. `refund_amount` is what the supplier
    paid back now, into a safe or wallet; the rest lowers what we owe them."""
    items: list[PurchaseReturnItemIn] = Field(..., min_length=1, max_length=500)
    refund_amount: Decimal | None = Field(None, ge=0, le=Decimal("9999999999"))
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=2000)
