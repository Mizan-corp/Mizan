import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.tenancy.context import TenantScoped
from app.db.base import Base


class ExpenseVendor(TenantScoped, Base):
    __tablename__ = "expense_vendors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Expense(TenantScoped, Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("expense_vendors.id"))
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("financial_categories.id"))
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Input VAT included in `amount` (ADR-014 D6), entered from the supplier's invoice; only in a
    # VAT-registered workspace. The category's account gets amount - tax_amount.
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0, server_default=text("0"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft/approved/rejected/cancelled
    payment_method: Mapped[str | None] = mapped_column(String(32))
    wallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_wallets.id"))
    safe_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("safes.id"))
    attachment_path: Mapped[str | None] = mapped_column(Text)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring_interval: Mapped[str | None] = mapped_column(String(16))
    recurring_end_date: Mapped[date | None] = mapped_column(Date)
    # A recurring expense's occurrence is used once (services/recurring.py): when its successor was
    # made, and the occurrence a generated draft follows.
    recurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recurred_from: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("expenses.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
