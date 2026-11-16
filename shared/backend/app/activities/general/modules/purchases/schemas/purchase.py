from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PurchaseItemCreate(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)
    notes: str | None = None


class PurchaseCreate(BaseModel):
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    notes: str | None = None
    amount_paid: Decimal | None = Field(None, ge=0)
    # Where amount_paid comes from: a safe (or bank account) or a payment wallet.
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None
    received_by_name: str | None = None
    items: list[PurchaseItemCreate] = []


class PurchaseUpdate(BaseModel):
    supplier_id: uuid.UUID | None = None
    notes: str | None = None
    items: list[PurchaseItemCreate] | None = None


class ReceiveItemOverride(BaseModel):
    product_id: uuid.UUID
    qty_received: Decimal | None = Field(None, gt=0)
    unit_cost: Decimal | None = Field(None, ge=0)
    # Batch tracking (pharmacies, ADR-006 phase 4): which batch the stock comes in as.
    batch_number: str | None = Field(None, max_length=64)
    expiry_date: date | None = None


class PurchaseReceive(BaseModel):
    items: list[ReceiveItemOverride] = []
    # What is paid on receipt and from where; when omitted, the order's own values are used.
    amount_paid: Decimal | None = Field(None, ge=0)
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None


class QuickProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    unit: str = "عدد"
    cost_price: Decimal = 0
    retail_price: Decimal = 0
    wholesale_price: Decimal = 0
    company: str | None = None
    subcategory_id: uuid.UUID | None = None


class PurchaseReturnItemIn(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0)


class PurchaseReturnCreate(BaseModel):
    """Goods sent back to the supplier from a received order. `refund_amount` is what the supplier
    paid back now, into a safe or wallet; the rest lowers what we owe them."""
    items: list[PurchaseReturnItemIn] = Field(..., min_length=1)
    refund_amount: Decimal | None = Field(None, ge=0)
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None
    notes: str | None = None
