"""Stock operations: request schemas (dispatch, stock request)."""
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class OperationItem(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0, le=Decimal("999999999"))
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    note: str | None = Field(None, max_length=500)
    # Batch tracking (pharmacies, ADR-006 phase 4): which batch the stock comes in as.
    batch_number: str | None = Field(None, max_length=64)
    expiry_date: date | None = None


class DispatchRequest(BaseModel):
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    items: list[OperationItem] = Field(..., min_length=1, max_length=500)
    notes: str | None = Field(None, max_length=1000)

    @model_validator(mode='after')
    def check_warehouses(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError('لا يمكن أن يكون مخزن المصدر والوجهة نفس المخزن')
        return self


class StockRequestRequest(BaseModel):
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    items: list[OperationItem] = Field(..., min_length=1, max_length=500)
    notes: str | None = Field(None, max_length=1000)

    @model_validator(mode='after')
    def check_warehouses(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError('لا يمكن أن يكون مخزن المصدر والوجهة نفس المخزن')
        return self
