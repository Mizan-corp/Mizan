"""Batches and expiry (FEFO): database models.

A lot is stock of one product in one branch under one batch number, with its expiry date. The
lots of a product in a branch always add up to its stock balance: every stock movement goes
through inventory.apply_movement, whose hook puts stock into a lot or takes it out (first expiry
first out) and records that in batches_lot_movements (traceability: which sale took which batch).
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

NO_BATCH = "—"  # stock that arrived without a batch (before tracking, or a return without one)


class Lot(TenantScoped, Base):
    __tablename__ = "batches_lots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "product_id", "warehouse_id", "batch_number", name="uq_batches_lots_batch"),
        Index("ix_batches_lots_fefo", "product_id", "warehouse_id", "expiry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0, server_default=text("0"))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default=text("'active'"))  # active, quarantined
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LotMovement(TenantScoped, Base):
    """How much of a stock movement went into or out of a lot (signed)."""
    __tablename__ = "batches_lot_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("batches_lots.id", ondelete="CASCADE"), nullable=False, index=True)
    movement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_movements.id", ondelete="CASCADE"), nullable=False, index=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
