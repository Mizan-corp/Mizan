"""Stock operations: request schemas (dispatch, stock request)."""
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

MAX_QTY = Decimal("999999999")
# archived_documents.amount (Numeric(12, 2)) holds a dispatch's total quantity.
MAX_TOTAL_QTY = Decimal("9999999999")


class OperationItem(BaseModel):
    # stock_movements.qty is Numeric(12, 3).
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0, le=MAX_QTY, max_digits=12, decimal_places=3)
    unit_cost: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("9999999999"), max_digits=12, decimal_places=2)
    note: str | None = Field(None, max_length=500)
    # Batch tracking (pharmacies, ADR-006 phase 4): which batch the stock comes in as.
    batch_number: str | None = Field(None, max_length=64)
    expiry_date: date | None = None


class _Operation(BaseModel):
    from_warehouse_id: uuid.UUID
    to_warehouse_id: uuid.UUID
    items: list[OperationItem] = Field(..., min_length=1, max_length=500)
    notes: str | None = Field(None, max_length=1000)
    # The client's id for this attempt (or the Idempotency-Key header): sending it again returns
    # the document already made instead of making another (OPS-5).
    client_id: uuid.UUID | None = None

    @model_validator(mode='after')
    def check_warehouses(self):
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError('لا يمكن أن يكون مخزن المصدر والوجهة نفس المخزن')
        if sum((i.qty for i in self.items), Decimal("0")) > MAX_TOTAL_QTY:
            raise ValueError('إجمالي الكميات في المستند أكبر من المسموح')
        return self


class DispatchRequest(_Operation):
    pass


class StockRequestRequest(_Operation):
    pass


class FulfilLine(BaseModel):
    product_id: uuid.UUID
    qty: Decimal = Field(gt=0, le=MAX_QTY, max_digits=12, decimal_places=3)
    note: str | None = Field(None, max_length=500)


class FulfilRequest(BaseModel):
    """What is sent for an approved stock request: the lines (each at most what was asked for), or
    everything asked for when omitted."""
    items: list[FulfilLine] | None = Field(None, min_length=1, max_length=500)
    notes: str | None = Field(None, max_length=1000)
    client_id: uuid.UUID | None = None
