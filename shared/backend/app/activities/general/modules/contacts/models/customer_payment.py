import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.tenancy.context import TenantScoped
from app.db.base import Base


class CustomerPayment(TenantScoped, Base):
    """Money received from a customer, and where it went: the receiving cashier's open drawer
    (shift_id), a safe (bank accounts are safes of type bank) or a payment wallet."""
    __tablename__ = "customer_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str | None] = mapped_column(Text, nullable=True)  # cash / wallet / bank / cheque
    safe_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("safes.id"), nullable=True)
    wallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_wallets.id"), nullable=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shifts.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # A reversal (negative amount) points to the receipt it undoes; a receipt is reversed once.
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customer_payments.id"), nullable=True)
    __table_args__ = (Index("uq_customer_payments_reverses_id", "tenant_id", "reverses_id", unique=True,
                            postgresql_where=text("reverses_id IS NOT NULL")),)


class CustomerAdjustment(TenantScoped, Base):
    """A change to a customer's balance that isn't a sale or a payment: the opening balance, or a
    correction. Recorded so every balance change can be traced (ADR-014 D4)."""
    __tablename__ = "customer_adjustments"
    __table_args__ = (CheckConstraint("kind IN ('opening', 'adjustment')", name="customer_adjustments_kind_check"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="adjustment", server_default="adjustment")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)  # signed change to the balance
    balance_before: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
