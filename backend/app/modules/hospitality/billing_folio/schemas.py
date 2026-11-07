"""Pydantic schemas for Hotel Guest Folio module."""
from typing import Optional
from pydantic import BaseModel


class FolioChargeCreate(BaseModel):
    reservation_id: str
    guest_name: str
    room_number: str
    charge_type: str = "مطعم وكافيه (F&B Room Service)"
    description: str
    net_amount: float
    tax_amount: float = 0.0
    total_amount: float
    charge_date: str


class FolioSettleRequest(BaseModel):
    payment_method: str = "cash"  # cash, card, bank_transfer
