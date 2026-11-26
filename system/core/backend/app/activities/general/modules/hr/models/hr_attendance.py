"""HR Attendance model."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.tenancy.context import TenantScoped
from app.db.base import Base


class HrAttendance(TenantScoped, Base):
    """Maps to hr_attendance table: one row per employee and day."""
    __tablename__ = "hr_attendance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    work_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), default="present", server_default="present")  # present/absent/leave/mission/excuse
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A day saved by hand: edited, by whom (the user's id as text) and why. A CSV import never
    # overwrites an edited day.
    edited: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default=text("false"))
    edited_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    edit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    excuse_no_late: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default=text("false"))
    excuse_no_early: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default=text("false"))
    excuse_allow_overtime: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default=text("false"))
    # A shift for this day only: an hr_shifts id or "HH:MM-HH:MM" (the payroll engine reads both).
    shift_override: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="hr_attendance_employee_id_work_date_key"),)
