import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.tenancy.context import TenantScoped
from app.db.base import Base


class HrEmployee(TenantScoped, Base):
    """Maps to hr_employees table — the actual HR employee records used by raw SQL in hr.py."""
    __tablename__ = "hr_employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    emp_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    monthly_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    shift_schedule: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # An hr_shifts id (varchar, like the table's); payroll reads it with shift_schedule.
    shift_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hire_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    ignore_lateness: Mapped[bool | None] = mapped_column(Boolean, default=False, server_default=text("false"))
    max_lateness_before_overtime_cancellation: Mapped[int | None] = mapped_column(Integer, default=30, server_default="30")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("tenant_id", "emp_code", name="uq_hr_employees_emp_code"),)

class HrPayrollPeriod(TenantScoped, Base):
    """Maps to hr_payroll_periods table — payroll month tracking."""
    __tablename__ = "hr_payroll_periods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    month: Mapped[str] = mapped_column(String(7), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Paying the month moves its total out of this safe or wallet, once (ADR-014 D4).
    safe_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("safes.id"), nullable=True)
    wallet_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_wallets.id"), nullable=True)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # The total approved (the salaries expense); paying pays exactly this.
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    expense_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("expenses.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("tenant_id", "month", name="uq_hr_payroll_periods_month"),)

class HrPayrollEntry(TenantScoped, Base):
    """Maps to hr_payroll_entries table — per-employee payroll entries (replaces old hr_payroll table)."""
    __tablename__ = "hr_payroll_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hr_payroll_periods.id", ondelete="CASCADE"))
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hr_employees.id", ondelete="CASCADE"))
    base_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # The base salary for the days worked (the engine's proration of base_salary): what the net
    # starts from, also when a manager edits the entry's adjustments.
    base_pay: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    working_days: Mapped[int | None] = mapped_column(nullable=True)
    actual_working_days: Mapped[int | None] = mapped_column(nullable=True)
    absent_days: Mapped[int | None] = mapped_column(nullable=True)
    vacation_days: Mapped[int | None] = mapped_column(nullable=True)
    total_hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    lateness_minutes: Mapped[int | None] = mapped_column(nullable=True)
    early_leave_minutes: Mapped[int | None] = mapped_column(nullable=True)
    missing_scan_minutes: Mapped[int | None] = mapped_column(nullable=True)
    lateness_deduction: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    overtime_hours: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    overtime_pay: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bonus_days: Mapped[int | None] = mapped_column(nullable=True)
    bonus_payment: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    bonuses: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    # The bonuses added to the net (the hr bonus records, or what a manager typed): what payroll reads.
    bonus: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)
    deductions: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    advances: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # The part of `advances` the month's pay couldn't cover, carried to the next month (HR-9).
    advances_carried: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    drawer_variance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    net_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    daily_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("period_id", "employee_id", name="hr_payroll_entries_period_id_employee_id_key"),)
