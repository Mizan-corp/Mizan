"""Stock operations: request schemas (dispatch, goods receipt, stock request)."""
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class OperationItem(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0)
    note: str = ""
    # Batch tracking (pharmacies, ADR-006 phase 4): which batch the stock comes in as.
    batch_number: str | None = Field(None, max_length=64)
    expiry_date: date | None = None


class DispatchRequest(BaseModel):
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    items: list[OperationItem]
    notes: str = ""

    @model_validator(mode='after')
    def check_warehouses(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError('لا يمكن أن يكون مخزن المصدر والوجهة نفس المخزن')
        return self


class GoodsReceiptRequest(BaseModel):
    warehouse_id: uuid.UUID
    supplier_name: str = ""
    items: list[OperationItem]   # unit_cost = سعر التكلفة من التاجر
    notes: str = ""


class StockRequestRequest(BaseModel):
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    items: list[OperationItem]
    notes: str = ""

    @model_validator(mode='after')
    def check_warehouses(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError('لا يمكن أن يكون مخزن المصدر والوجهة نفس المخزن')
        return self
