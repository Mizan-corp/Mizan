"""Goods receipts (PUR-4): an order is received in one or more receipts, each its own document with
what arrived per line. Each receipt posts its own `purchase.received` (v104)."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.platform.tenancy.context import TenantScoped


class PurchaseReceipt(TenantScoped, Base):
    """One delivery against an order. `seq` counts the order's receipts (1, 2…); `total` is what the
    supplier is owed for it (with VAT when registered), `amount_paid` what was paid with it."""
    __tablename__ = "purchase_receipts"
    __table_args__ = (UniqueConstraint("tenant_id", "receipt_number", name="uq_purchase_receipts_number"),
                      UniqueConstraint("tenant_id", "po_id", "seq", name="uq_purchase_receipts_seq"))

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_number: Mapped[str] = mapped_column(String(32), nullable=False)
    po_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default=text("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default=text("0"))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default=text("0"))
    safe_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("safes.id"), nullable=True)
    wallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_wallets.id"), nullable=True)
    prices_include_vat: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["PurchaseReceiptItem"]] = relationship(back_populates="receipt", cascade="all, delete-orphan")


class PurchaseReceiptItem(TenantScoped, Base):
    __tablename__ = "purchase_receipt_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    receipt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_receipts.id", ondelete="CASCADE"), index=True)
    po_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_order_items.id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    batch_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0, server_default=text("0"))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default=text("0"))
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    receipt: Mapped["PurchaseReceipt"] = relationship(back_populates="items")
