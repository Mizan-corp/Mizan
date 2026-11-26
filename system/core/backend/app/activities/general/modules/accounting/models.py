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
- `acc_settings`: one row per workspace: the first month of the fiscal year and the date the ledger
  starts (set by the opening entry, D10).
- `acc_drafts` / `acc_draft_lines`: manual journal entries being written (D9). Kept apart from
  `acc_entries`, which are immutable and must balance at commit: a draft is edited freely and may be
  unbalanced until it is posted. Posting writes a normal entry (source `manual`, the draft's id,
  event `post`) and keeps the draft, read-only, with `status = 'posted'` and its `entry_id`.

The tables keep the short `acc_` prefix the ADR names them with.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, text
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


class Settings(TenantScoped, Base):
    """The workspace's accounting settings (one row, created on first use): the first month of the
    fiscal year (1-12, default January, D7) and the date the ledger starts (D10)."""
    __tablename__ = "acc_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_acc_settings_tenant"),
        CheckConstraint("fiscal_year_start BETWEEN 1 AND 12", name="ck_acc_settings_fy_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fiscal_year_start: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Draft(TenantScoped, Base):
    """A manual journal entry not posted yet (D9), or one posted from here (`status` posted, kept
    read-only with the entry it became)."""
    __tablename__ = "acc_drafts"
    __table_args__ = (CheckConstraint("status IN ('draft', 'posted')", name="ck_acc_drafts_status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default=text("'draft'"))
    entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("acc_entries.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DraftLine(TenantScoped, Base):
    __tablename__ = "acc_draft_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_acc_draft_lines_amounts"),
        CheckConstraint("party_type IS NULL OR party_type IN ('customer', 'supplier', 'employee')",
                        name="ck_acc_draft_lines_party"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("acc_drafts.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("acc_accounts.id"), nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default=text("0"))
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default=text("0"))
    party_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    party_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
