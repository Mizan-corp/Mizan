"""HR Audit log model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.tenancy.context import TenantScoped
from app.db.base import Base


class HrAuditLog(TenantScoped, Base):
    """Maps to hr_audit_log table — HR-specific audit trail."""
    __tablename__ = "hr_audit_log"
    __table_args__ = (Index("ix_hr_audit_log_tenant_created", "tenant_id", "created_at"),)  # the paged log, newest first

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)  # create/update/delete/calculate/approve/pay
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # employee/attendance/advance/payroll
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
