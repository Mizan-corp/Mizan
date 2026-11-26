import uuid
from datetime import datetime
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, Field

# VAT codes (ADR-014 D6); the rates are in app/platform/settings/vat.py.
TaxCode = Literal["standard", "zero", "exempt"]

# The columns' limits (models/product.py): longer input is a 422, never a database error.
PRICE_MAX = Decimal("9999999999")  # Numeric(12, 2)
QTY_MAX = Decimal("999999999")  # Numeric(12, 3)
_TRIM = {"str_strip_whitespace": True}


class CategoryCreate(BaseModel):
    model_config = _TRIM
    name: str = Field(..., min_length=1, max_length=128)
    code: str | None = Field(None, max_length=32)
    image_url: str | None = Field(None, max_length=512)


class CategoryOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str | None = None
    image_url: str | None = None
    model_config = {"from_attributes": True}


class SubcategoryCreate(BaseModel):
    model_config = _TRIM
    category_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=128)
    code: str | None = Field(None, max_length=32)


class SubcategoryOut(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    code: str | None = None
    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    model_config = _TRIM
    # Optional (INV-9): a workspace that hasn't made categories yet can still add products.
    subcategory_id: uuid.UUID | None = None
    name: str = Field(..., min_length=1, max_length=256)
    code: str | None = Field(None, max_length=32)
    barcode: str | None = Field(None, max_length=64)
    unit: str = Field("عدد", min_length=1, max_length=32)
    retail_price: Decimal = Field(default=Decimal("0"), ge=0, le=PRICE_MAX)
    wholesale_price: Decimal = Field(default=Decimal("0"), ge=0, le=PRICE_MAX)
    cost_price: Decimal = Field(default=Decimal("0"), ge=0, le=PRICE_MAX)
    company: str | None = Field(None, max_length=128)
    size: str | None = Field(None, max_length=64)
    product_type: str | None = Field(None, max_length=64)
    material: str | None = Field(None, max_length=64)
    image_url: str | None = Field(None, max_length=512)
    description: str | None = Field(None, max_length=5000)
    shelf_number: str | None = Field(None, max_length=32)
    reorder_point: Decimal = Field(default=Decimal("0"), ge=0, le=QTY_MAX)
    reorder_qty: Decimal = Field(default=Decimal("0"), ge=0, le=QTY_MAX)
    reorder_level: int = Field(default=5, ge=0, le=1_000_000_000)
    tax_code: TaxCode = "standard"
    # Values of the fields the activity's variants and the workspace add (framework/fields.py).
    extra: dict = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    model_config = _TRIM
    name: str | None = Field(None, min_length=1, max_length=256)
    code: str | None = Field(None, max_length=32)
    barcode: str | None = Field(None, max_length=64)
    unit: str | None = Field(None, min_length=1, max_length=32)
    retail_price: Decimal | None = Field(None, ge=0, le=PRICE_MAX)
    wholesale_price: Decimal | None = Field(None, ge=0, le=PRICE_MAX)
    cost_price: Decimal | None = Field(None, ge=0, le=PRICE_MAX)
    subcategory_id: uuid.UUID | None = None
    # subcategory_id null keeps it; this takes the product out of its category.
    clear_subcategory: bool = False
    company: str | None = Field(None, max_length=128)
    size: str | None = Field(None, max_length=64)
    product_type: str | None = Field(None, max_length=64)
    material: str | None = Field(None, max_length=64)
    shelf_number: str | None = Field(None, max_length=32)
    is_active: bool | None = None
    reorder_point: Decimal | None = Field(None, ge=0, le=QTY_MAX)
    reorder_qty: Decimal | None = Field(None, ge=0, le=QTY_MAX)
    reorder_level: int | None = Field(default=None, ge=0, le=1_000_000_000)
    # "untracked": stock isn't followed for this product (a service); sales don't check its balance.
    stock_status: str | None = Field(default=None, pattern="^(tracked|untracked)$")
    description: str | None = Field(None, max_length=5000)
    tax_code: TaxCode | None = None
    # Values of the fields the activity's variants and the workspace add (framework/fields.py).
    extra: dict | None = None


class ProductOut(BaseModel):
    id: uuid.UUID
    subcategory_id: uuid.UUID | None = None
    name: str
    code: str | None = None
    barcode: str | None
    unit: str
    retail_price: Decimal
    wholesale_price: Decimal
    # Costs: null for a user who sells or moves stock but may not see costs (INV-8, see
    # services/products.COST_PERMISSIONS).
    cost_price: Decimal | None = None
    # The workspace's weighted average cost (ADR-014 D5); 0 until the first costed receipt.
    avg_cost: Decimal | None = Decimal("0")
    company: str | None
    size: str | None
    product_type: str | None
    material: str | None
    shelf_number: str | None
    is_active: bool
    image_url: str | None = None
    description: str | None = None
    reorder_point: Decimal
    reorder_qty: Decimal
    reorder_level: int = 5
    stock_status: str = "untracked"
    tax_code: str = "standard"
    created_at: datetime
    updated_at: datetime
    extra: dict = Field(default_factory=dict)
    model_config = {"from_attributes": True}


class ProductWithStock(ProductOut):
    current_qty: Decimal = Decimal("0")


class ProductOutWithBalance(ProductOut):
    model_config = {"from_attributes": True, "extra": "allow"}


class ProductBarcodeCreate(BaseModel):
    model_config = _TRIM
    barcode: str = Field(..., min_length=1, max_length=64)
    is_primary: bool = False


class ProductBarcodeOut(BaseModel):
    id: uuid.UUID
    barcode: str
    is_primary: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ProductWithBarcodes(ProductOut):
    barcodes: list[ProductBarcodeOut] = []


class MoveProduct(BaseModel):
    subcategory_id: uuid.UUID


class BulkReorderLevelIn(BaseModel):
    product_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)
    reorder_level: int = Field(5, ge=0, le=1_000_000_000)
