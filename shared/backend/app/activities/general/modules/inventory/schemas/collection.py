from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.activities.general.modules.inventory.schemas.product import PRICE_MAX, QTY_MAX


class CollectionItem(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(..., gt=0, le=QTY_MAX)


class CollectionCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field("", max_length=2000)
    retail_price: Decimal = Field(Decimal("0"), ge=0, le=PRICE_MAX)
    wholesale_price: Decimal = Field(Decimal("0"), ge=0, le=PRICE_MAX)
    items: list[CollectionItem] = Field(default_factory=list, max_length=200)


class CollectionUpdate(CollectionCreate):
    pass
