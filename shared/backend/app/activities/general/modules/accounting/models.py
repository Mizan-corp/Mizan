"""Accounting: the ledger (ADR-014 D1, D2).

- `acc_accounts`: the workspace's chart of accounts, copied from `charts/eg_standard.json`.
  Posting rules find accounts by `role`, never by code. Group accounts take no postings.
- `acc_entries`: one journal entry per (source_type, source_id, event); never updated or
  deleted. A mistake is corrected by a reversing entry (`reverses_id`, event "reverse").
- `acc_lines`: the entry's debits and credits. Each entry balances (sum of debits = sum of
  credits > 0), checked by the posting service and by a deferred constraint trigger.
- Branch and user ids are kept without foreign keys: an entry is never updated, so deleting a
  branch or a user must not try to null them.
- `acc_money_accounts`: which sub-account holds the money of each safe, wallet and branch drawer.

The tables keep the short `acc_` prefix the ADR names them with.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

ACCOUNT_TYPES = ("asset", "liability", "equity", "income", "expense")


class Account(TenantScoped, Base):
    __tablename__ = "acc_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_acc_accounts_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("acc_accounts.id"), nullable=True)
    is_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    role: Mapped[str | None] = mapped_column(String(48), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Entry(TenantScoped, Base):
    __tablename__ = "acc_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_type", "source_id", "event", name="uq_acc_entries_source"),
        UniqueConstraint("tenant_id", "number", name="uq_acc_entries_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(32), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event: Mapped[str] = mapped_column(String(48), nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("acc_entries.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Line(TenantScoped, Base):
    __tablename__ = "acc_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("acc_entries.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("acc_accounts.id"), index=True)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    party_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # customer / supplier / employee
    party_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MoneyAccount(TenantScoped, Base):
    """The ledger account of a safe, a payment wallet or a branch's cashier drawer (kind: safe,
    wallet, drawer, default_bank), created the first time money moves through it."""
    __tablename__ = "acc_money_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "kind", "ref_id", name="uq_acc_money_accounts_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("acc_accounts.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
