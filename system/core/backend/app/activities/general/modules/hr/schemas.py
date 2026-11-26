from __future__ import annotations

import uuid
from datetime import date as date_type
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# A payroll month, "YYYY-MM" (query parameters use the same pattern).
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
Month = Annotated[str, StringConstraints(pattern=MONTH_PATTERN)]
# "HH:MM" or "HH:MM:SS", 24-hour.
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$"
ClockTime = Annotated[str, StringConstraints(pattern=TIME_PATTERN)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class EmployeeCreate(BaseModel):
    """Schema for creating an HR employee (hr_employees table)."""
    emp_code: str | None = Field(None, max_length=32)
    user_id: uuid.UUID | None = None
    name: str = Field(..., min_length=1, max_length=128)
    position: str | None = Field(None, max_length=64)
    monthly_salary: Money = Decimal("0")
    shift_schedule: str | None = Field(None, max_length=64)
    shift_id: str | None = Field(None, max_length=32)
    hire_date: date_type | None = None
    ignore_lateness: bool = False
    max_lateness_before_overtime_cancellation: int = Field(30, ge=0, le=1440)


class EmployeeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    user_id: uuid.UUID | None = None
    position: str | None = Field(None, max_length=64)
    monthly_salary: Money | None = None
    shift_schedule: str | None = Field(None, max_length=64)
    shift_id: str | None = Field(None, max_length=32)
    hire_date: date_type | None = None
    is_active: bool | None = None
    ignore_lateness: bool | None = None
    max_lateness_before_overtime_cancellation: int | None = Field(None, ge=0, le=1440)


class AttendanceCreate(BaseModel):
    """A day of attendance saved by hand: it is marked edited (by whom, why), and a later CSV
    import doesn't overwrite it."""
    employee_id: uuid.UUID
    work_date: date_type
    check_in: ClockTime | None = None
    check_out: ClockTime | None = None
    status: Literal["present", "absent", "leave", "mission", "excuse"] = "present"
    notes: str | None = Field(None, max_length=1000)
    edit_reason: str | None = Field(None, max_length=500)
    excuse_no_late: bool = False
    excuse_no_early: bool = False
    excuse_allow_overtime: bool = False
    shift_override: str | None = Field(None, max_length=32)


class PayrollCalculate(BaseModel):
    month: Month
    employee_id: uuid.UUID | None = None


class PayrollUpdate(BaseModel):
    """A payroll entry's manual adjustments (while its month is draft or in review). The status is
    the month's, never set by hand."""
    model_config = ConfigDict(extra="forbid")

    bonus: Money = Decimal("0")
    deductions: Money = Decimal("0")
    drawer_variance: Annotated[Decimal, Field(ge=-10**9, le=10**9, max_digits=12, decimal_places=2)] = Decimal("0")
    notes: str | None = Field(None, max_length=1000)


class HrRecordType(str, Enum):
    """An HR money record: an advance is cash paid now and deducted from the salary; a deduction
    lowers the salary, a bonus raises it (no cash moves for either)."""
    advance = "سلفة"
    deduction = "خصم"
    bonus = "مكافأة"


class AdvanceCreate(BaseModel):
    employee_id: uuid.UUID
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    date: date_type | None = None
    note: str | None = Field(None, max_length=1000)
    record_type: HrRecordType = HrRecordType.advance
    # An advance is paid out now: from a safe (or bank account) or a wallet.
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None


class AdvanceCancel(BaseModel):
    reason: str | None = Field(None, max_length=500)


class PayrollPay(BaseModel):
    """Where the month's salaries are paid from."""
    safe_id: uuid.UUID | None = None
    wallet_id: uuid.UUID | None = None


class ShiftCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    start_time: ClockTime
    end_time: ClockTime
    description: str = Field("", max_length=1000)


class ShiftUpdate(BaseModel):
    """Only the fields sent change; a stopped shift is not offered for new employees."""
    name: str | None = Field(None, min_length=1, max_length=128)
    start_time: ClockTime | None = None
    end_time: ClockTime | None = None
    description: str | None = Field(None, max_length=1000)
    is_active: bool | None = None


class HRSettingsValues(BaseModel):
    """The payroll engine's settings. Anything else is refused (a bad value used to break every
    payroll run)."""
    model_config = ConfigDict(extra="forbid")

    days_in_month: int | None = Field(None, ge=1, le=31)
    grace_period_minutes: int | None = Field(None, ge=0, le=240)
    late_penalty_multiplier: Decimal | None = Field(None, ge=0, le=10)
    missing_checkout_penalty_hours: Decimal | None = Field(None, ge=0, le=24)
    apply_missing_checkout_penalty: bool | None = None
    overtime_enabled: bool | None = None
    weekend_paid: bool | None = None
    # What used to be fixed (HR-12); the defaults are those values (services/payroll_engine.SETTINGS).
    weekend_day: int | None = Field(None, ge=0, le=6)  # Monday 0 … Sunday 6; Friday 4
    day_start_hour: int | None = Field(None, ge=0, le=12)
    paid_leave_days: int | None = Field(None, ge=0, le=31)
    default_shift_start_hour: int | None = Field(None, ge=0, le=23)
    default_shift_end_hour: int | None = Field(None, ge=0, le=23)


class HRSettingsUpdate(BaseModel):
    settings: HRSettingsValues = Field(default_factory=HRSettingsValues)
