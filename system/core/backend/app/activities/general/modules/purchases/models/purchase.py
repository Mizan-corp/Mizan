import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.tenancy.context import TenantScoped
from app.db.base import Base


class POStatus(enum.StrEnum):
    draft = "draft"
    received = "received"
    partial = "partial"
    cancelled = "cancelled"


class PurchaseOrder(TenantScoped, Base):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_number: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    status: Mapped[POStatus] = mapped_column(SAEnum(POStatus, name="po_status_enum"), default=POStatus.draft)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    # Where amount_paid comes from (ADR-014 D4): a safe (or bank account) or a payment wallet.
    safe_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("safes.id"), nullable=True)
    wallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_wallets.id"), nullable=True)
    received_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # VAT (ADR-014 D6): the tax in what the order cost when received, and whether its unit costs
    # included VAT (NULL until received: the workspace's setting then, unless the order says).
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    prices_include_vat: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("tenant_id", "po_number", name="uq_purchase_orders_po_number"),
                      Index("idx_purchase_orders_supplier_id", "supplier_id"))

class PurchaseOrderItem(TenantScoped, Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Values of the fields variants and the workspace add (app/framework/fields.py).
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    po_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"))
    qty_ordered: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # VAT at receipt (ADR-014 D6), as on sale lines: net_amount is the received value without VAT.
    tax_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default=text("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
    __table_args__ = (Index("idx_purchase_order_items_po_id", "po_id"),
                      Index("idx_purchase_order_items_product_id", "product_id"),
                      # PLAT-9: an order's line of a product (receipts, returns).
                      Index("ix_purchase_order_items_po_product", "po_id", "product_id"))
