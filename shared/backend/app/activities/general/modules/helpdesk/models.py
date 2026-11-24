"""Private tenant-scoped offerings. No product, booking or payable quote identity."""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.platform.tenancy.context import TenantScoped

class HelpdeskOffering(TenantScoped, Base):
    __tablename__ = "helpdesk_offerings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    starting_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (CheckConstraint("starting_amount >= 0", name="helpdesk_amount_nonnegative"),)

# Append-only worksheet snapshots. Source tables and native lifecycle stay intact.
from sqlalchemy import Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

class HelpdeskExecutionRevision(TenantScoped, Base):
    __tablename__ = 'helpdesk_execution_revisions'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),primary_key=True)
    source_module: Mapped[str] = mapped_column(String(32),nullable=False)
    source_id: Mapped[str] = mapped_column(String(36),nullable=False)
    revision: Mapped[int] = mapped_column(Integer,nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64),nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB,nullable=False)
    resource_labels: Mapped[dict] = mapped_column(JSONB,nullable=False,default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    __table_args__ = (UniqueConstraint('tenant_id','source_module','source_id','revision',name='uq_helpdesk_execution_source_revision'),
                     CheckConstraint('revision > 0',name='helpdesk_execution_positive_revision'))
