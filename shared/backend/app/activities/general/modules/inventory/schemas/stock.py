import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.activities.general.modules.inventory.models.stock import MovementType


class StockMovementCreate(BaseModel):
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    movement_type: MovementType
    qty: Decimal = Field(..., gt=0, le=Decimal("999999999"))
    unit_cost: Decimal = Field(Decimal("0"), ge=0, le=Decimal("9999999999"))
    unit_price: Decimal = Field(Decimal("0"), ge=0, le=Decimal("9999999999"))
    note: str | None = Field(None, max_length=1000)
    # Batch tracking (pharmacies, ADR-006 phase 4): which batch the stock comes in as.
    batch_number: str | None = Field(None, max_length=64)
    expiry_date: date | None = None

    @field_validator('note')
    def note_required_for_damage(cls, v, info):
        movement_type = info.data.get('movement_type') if hasattr(info, 'data') else None
        if movement_type in ('damage', 'adjustment_out') and not v:
            raise ValueError('اكتب سبب التالف أو التسوية بالنقص في الملاحظات')
        return v


class StockMovementOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    movement_type: MovementType
    qty: Decimal
    unit_cost: Decimal
    unit_price: Decimal
    ref_id: uuid.UUID | None
    ref_type: str | None
    sale_id: uuid.UUID | None = None
    purchase_id: uuid.UUID | None = None
    operation_id: uuid.UUID | None = None
    note: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


class StockBalance(BaseModel):
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    current_qty: Decimal


class TransferRequest(BaseModel):
    product_id: uuid.UUID
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    qty: Decimal = Field(..., gt=0, le=Decimal("999999999"))
    note: str | None = Field(None, max_length=1000)
