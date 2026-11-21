"""
payroll_engine.py — Full payroll calculation matching the Qt موظفين system.
Logic ported directly from models.py PayrollCalculator.calculate_payroll()

The rules that used to be fixed (Friday weekend, the 5 am day rollover, 4 paid leave days a month,
26 days a month, a 9-to-21 shift for an employee without one) are the workspace's HR settings
(`SETTINGS`, today's values as defaults; HR-12). Money is Decimal end to end, rounded to the
piastre (half up) only where a figure is stored; hours and minutes stay numbers of hours.
"""
import calendar
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.platform.tenancy import clock

CENT = Decimal("0.01")
RATE = Decimal("0.0001")
ZERO = Decimal("0")

# The HR settings, with their defaults (what used to be hard-coded) and bounds. The schema
# (schemas.HRSettingsValues) refuses anything else; a bad value stored before settings were typed
# falls back to the default.
SETTINGS: dict[str, dict] = {
    "days_in_month": {"default": 26, "type": int, "min": 1, "max": 31},
    "grace_period_minutes": {"default": 10, "type": int, "min": 0, "max": 240},
    "late_penalty_multiplier": {"default": Decimal("2"), "type": Decimal, "min": 0, "max": 10},
    "missing_checkout_penalty_hours": {"default": Decimal("2"), "type": Decimal, "min": 0, "max": 24},
    "apply_missing_checkout_penalty": {"default": True, "type": bool},
    "overtime_enabled": {"default": True, "type": bool},
    "weekend_paid": {"default": True, "type": bool},
    # Python's weekday: Monday 0 … Sunday 6 (Friday 4).
    "weekend_day": {"default": 4, "type": int, "min": 0, "max": 6},
    # A punch before this hour belongs to the day before (a night shift's check-out).
    "day_start_hour": {"default": 5, "type": int, "min": 0, "max": 12},
    # Leave days a month paid as a full shift; more are unpaid.
    "paid_leave_days": {"default": 4, "type": int, "min": 0, "max": 31},
    # The shift of an employee without one (whole hours, 24-hour clock).
    "default_shift_start_hour": {"default": 9, "type": int, "min": 0, "max": 23},
    "default_shift_end_hour": {"default": 21, "type": int, "min": 0, "max": 23},
}


def _money(value) -> Decimal:
    return Decimal(str(value or 0))


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def effective_settings(stored: dict | None) -> dict:
    """Every HR setting, typed, from the stored key/value rows; a missing or bad value is the default."""
    stored = stored or {}
    out = {}
    for key, spec in SETTINGS.items():
        raw, default = stored.get(key), spec["default"]
        if spec["type"] is bool:
            out[key] = default if raw is None else str(raw).strip().lower() in ("true", "1", "yes")
            continue
        try:
            value = Decimal(str(raw)) if raw is not None else Decimal(str(default))
        except ArithmeticError:
            value = Decimal(str(default))
        if not value.is_finite() or value < spec["min"] or value > spec["max"]:
            value = Decimal(str(default))
        out[key] = int(value) if spec["type"] is int else value
    return out


def to_local(dt):
    """Return naive local datetime. DB stores Cairo time as UTC-marked — strip timezone only."""
    if dt is None:
        return None
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        # Strip timezone — times are already in local Cairo time stored with UTC marker
        return dt.replace(tzinfo=None)
    return dt


def parse_shift(shift_str: str, shifts_map: dict = None, default: tuple[int, int] = (9, 21)) -> tuple:
    """Parse shift string → (start_hour, end_hour).
    Handles: '11:00-23:00', '9-21', '11 صباحاً الى 11 مساءً', shift name/id lookup; `default` (the
    workspace's default shift) when the string says nothing usable.
    """
    if not shift_str:
        return default

    # Try direct HH:MM-HH:MM or H-H
    try:
        parts = shift_str.replace('–', '-').replace('—', '-').split('-')
        if len(parts) == 2:
            s = int(parts[0].strip().split(':')[0])
            e = int(parts[1].strip().split(':')[0])
            return s, e
    except (ValueError, IndexError, AttributeError):
        pass

    # Try Arabic format: "9 صباحا الى 9 مساءً" or "11 صباحاً الى 11 مساءً"
    nums = re.findall(r'\d+', shift_str)
    if len(nums) >= 2:
        s, e = int(nums[0]), int(nums[1])
        # Detect AM/PM from Arabic keywords
        shift_str = shift_str.lower()
        parts_ar = shift_str.split('الى') if 'الى' in shift_str else shift_str.split('إلى')
        if len(parts_ar) == 2:
            start_part, end_part = parts_ar[0], parts_ar[1]
            # Start hour
            if 'مساء' in start_part or 'pm' in start_part.lower():
                if s < 12:
                    s += 12
            elif 'صباح' in start_part or 'am' in start_part.lower():
                if s == 12:
                    s = 0
            # End hour
            if 'مساء' in end_part or 'pm' in end_part.lower():
                if e < 12:
                    e += 12
            elif 'صباح' in end_part or 'am' in end_part.lower():
                if e == 12:
                    e = 0
        return s, e

    # Try resolving by name or id from shifts_map
    if shifts_map:
        for s_obj in shifts_map.values():
            if s_obj.get('name') == shift_str or str(s_obj.get('id')) == str(shift_str):
                try:
                    return int(s_obj['start_time'].split(':')[0]), int(s_obj['end_time'].split(':')[0])
                except (ValueError, IndexError, KeyError):
                    pass

    return default


def employee_shift(employee: dict, shifts_map: dict | None) -> str:
    """The shift an employee works: the shift chosen from the shifts list (`shift_id`), else the
    schedule typed on the employee ("09:00-17:00")."""
    shift = (shifts_map or {}).get(employee.get('shift_id')) if employee.get('shift_id') else None
    if shift and shift.get('start_time') and shift.get('end_time'):
        return f"{shift['start_time']}-{shift['end_time']}"
    return employee.get('shift_schedule', '') or ''


def shift_hours(start_h: int, end_h: int) -> int:
    return (end_h - start_h) if end_h > start_h else (24 - start_h + end_h)


def setting_number(settings: dict, key: str, default: float) -> float:
    """A numeric setting; a stored value that isn't a number (saved before settings were typed)
    falls back to the default instead of breaking the run."""
    try:
        value = float(settings.get(key, default))
    except (TypeError, ValueError):
        return float(default)
    return value if value == value and value >= 0 else float(default)  # NaN or negative


def setting_flag(settings: dict, key: str, default: bool) -> bool:
    value = settings.get(key)
    if value is None:
        return default
    return str(value).strip().lower() in ('true', '1', 'yes')


def attendance_day(dt: datetime, day_start_hour: int = 5) -> date | None:
    """The working day a punch belongs to: before `day_start_hour` it is the previous day's."""
    if not dt:
        return None
    if dt.hour < day_start_hour:
        return (dt - timedelta(days=1)).date()
    return dt.date()


def calculate_payroll(employee: dict, attendances: list[dict], settings: dict,
                      shifts_map: dict, bonus=0, deduction=0, advance=0, month: str = None) -> dict:
    """
    Full payroll calculation.
    employee: dict with name, monthly_salary, shift_id / shift_schedule, ignore_lateness, max_lateness_before_overtime_cancellation
    attendances: list of dicts with check_in, check_out, status, excuse_*, shift_override, edited
    settings: dict from hr_settings table (key → stored text), read through effective_settings
    shifts_map: {id: {name, start_time, end_time}}
    month: 'YYYY-MM' string
    Money (salary, rate, deductions, pay, net) comes back as Decimal.
    """
    cfg = effective_settings(settings)
    monthly_salary = _money(employee.get('monthly_salary'))
    bonus, deduction, advance = _money(bonus), _money(deduction), _money(advance)
    days_in_month = cfg['days_in_month']
    default_shift = (cfg['default_shift_start_hour'], cfg['default_shift_end_hour'])
    emp_shift = employee_shift(employee, shifts_map)
    ignore_lateness = bool(employee.get('ignore_lateness') or False)
    max_late = employee.get('max_lateness_before_overtime_cancellation')
    max_late_for_ot = int(30 if max_late is None else max_late)

    grace_period = cfg['grace_period_minutes']
    multiplier = cfg['late_penalty_multiplier']
    missing_penalty_hours = float(cfg['missing_checkout_penalty_hours'])
    apply_missing_penalty = cfg['apply_missing_checkout_penalty']
    overtime_enabled = cfg['overtime_enabled']
    weekend_paid = cfg['weekend_paid']
    weekend_day = cfg['weekend_day']
    day_start_hour = cfg['day_start_hour']
    paid_leave_days = cfg['paid_leave_days']

    start_h, end_h = parse_shift(emp_shift, shifts_map, default_shift)
    shift_length = shift_hours(start_h, end_h)

    # Determine month range
    if month:
        year, mon = int(month.split('-')[0]), int(month.split('-')[1])
        month_start = date(year, mon, 1)
        _, last_day = calendar.monthrange(year, mon)
        month_end = date(year, mon, last_day)
    else:
        now = clock.now()  # the workspace's month and day (Africa/Cairo), not the server's
        month_start = now.date().replace(day=1)
        _, last_day = calendar.monthrange(now.year, now.month)
        month_end = now.date().replace(day=last_day)

    now = clock.now()
    end_date_for_loop = month_end if month_end < now.date() else now.date()

    # Group attendances by logical day
    grouped: dict = defaultdict(list)
    for att in attendances:
        ci = att.get('check_in')
        co = att.get('check_out')
        ref_ts = None
        if ci:
            ref_ts = to_local(ci if isinstance(ci, datetime) else datetime.fromisoformat(str(ci)))
        elif co:
            ref_ts = to_local(co if isinstance(co, datetime) else datetime.fromisoformat(str(co)))
        if ref_ts:
            day = attendance_day(ref_ts, day_start_hour)
            if day:
                grouped[day].append(att)

    scheduled_hours = days_in_month * shift_length if shift_length > 0 else 0
    hourly_rate = (monthly_salary / scheduled_hours) if scheduled_hours > 0 else ZERO

    total_hours = 0.0
    total_late_min = 0
    total_early_min = 0
    total_missing_min = 0
    s_len = shift_length  # default — overridden per-day inside loop
    working_days = 0
    actual_working_days = 0
    vacation_days = 0
    leave_days_count = 0
    daily_breakdown = []

    hire_date = None
    if employee.get('hire_date'):
        try:
            hd = employee['hire_date']
            hire_date = hd if isinstance(hd, date) else date.fromisoformat(str(hd))
        except Exception:
            pass

    current_day = month_start
    while current_day <= end_date_for_loop:
        # Pre-hire
        if hire_date and current_day < hire_date:
            daily_breakdown.append({'date': current_day.isoformat(), 'status': 'pre-hire', 'note': 'قبل تاريخ التعيين',
                                     'work_hours': 0, 'late_minutes': 0, 'overtime_hours': 0})
            current_day += timedelta(days=1)
            continue

        day_items = grouped.get(current_day, [])

        if not day_items:
            # The weekly day off (the workspace's weekend day)
            if current_day.weekday() == weekend_day and weekend_paid:
                daily_breakdown.append({'date': current_day.isoformat(), 'status': 'weekend', 'note': 'عطلة أسبوعية',
                                         'work_hours': 0, 'late_minutes': 0, 'overtime_hours': 0})
                current_day += timedelta(days=1)
                continue
            # Absent
            note = 'لم يتم تسجيل حضور اليوم' if current_day == now.date() else 'غياب'
            daily_breakdown.append({'date': current_day.isoformat(), 'status': 'absent', 'note': note,
                                     'work_hours': 0, 'late_minutes': 0, 'overtime_hours': 0})
            current_day += timedelta(days=1)
            continue

        primary = day_items[0]
        status = primary.get('status', 'present')
        if status == 'regular':
            status = 'present'
        excuse_no_late = bool(primary.get('excuse_no_late', False))
        excuse_no_early = bool(primary.get('excuse_no_early', False))
        excuse_allow_ot = bool(primary.get('excuse_allow_overtime', False))
        shift_override = primary.get('shift_override')
        is_edited = any(a.get('edited', False) for a in day_items)
        edit_reason = next((a.get('edit_reason', '') for a in day_items if a.get('edit_reason')), '')

        eff_shift = shift_override if shift_override else emp_shift
        s_h, e_h = parse_shift(eff_shift, shifts_map, default_shift)
        s_len = shift_hours(s_h, e_h)

        # Collect all timestamps
        all_ts = []
        for item in day_items:
            for k in ('check_in', 'check_out'):
                v = item.get(k)
                if v:
                    all_ts.append(to_local(v if isinstance(v, datetime) else datetime.fromisoformat(str(v))))
        all_ts = sorted(set(all_ts))
        eff_in = all_ts[0] if all_ts else None
        eff_out = all_ts[-1] if len(all_ts) > 1 else None

        work_hours = 0.0
        late_mins = 0
        early_mins = 0
        missing_mins = 0
        daily_ot = 0.0
        note_parts = []
        if edit_reason:
            note_parts.append(f'[{edit_reason}]')
        if shift_override:
            note_parts.append(f'شيفت مؤقت: {shift_override}')

        if status == 'leave':
            if leave_days_count < paid_leave_days:
                work_hours = s_len
                leave_days_count += 1
                note_parts.append('إجازة مدفوعة')
            else:
                note_parts.append(f'إجازة (تجاوز الحد {paid_leave_days} أيام)')
        elif status == 'mission':
            work_hours = s_len
            note_parts.append('مأمورية عمل')
        else:
            # Handle missing check-in
            if not eff_in and eff_out and not is_edited:
                shift_start = eff_out.replace(hour=s_h, minute=0, second=0, microsecond=0)
                if s_h > e_h and shift_start > eff_out:
                    shift_start -= timedelta(days=1)
                eff_in = shift_start
                missing_mins += int(missing_penalty_hours * 60)
                note_parts.append(f'افتراض دخول وخصم {missing_penalty_hours:.0f} ساعة')

            # Lateness
            if eff_in and status not in ('leave', 'mission'):
                shift_start_t = eff_in.replace(hour=s_h, minute=0, second=0, microsecond=0)
                if eff_in > shift_start_t:
                    raw_late = int((eff_in - shift_start_t).total_seconds() / 60)
                    if not ignore_lateness:
                        late_mins = 0 if raw_late <= grace_period else raw_late - grace_period
                    if status == 'excuse' and excuse_no_late:
                        late_mins = 0
                        note_parts.append('عذر (إلغاء التأخير)')
                    elif status == 'excuse':
                        note_parts.append('عذر')

            # Handle missing check-out
            if not eff_out and eff_in and not is_edited and status not in ('leave', 'mission'):
                shift_end_t = eff_in.replace(hour=e_h, minute=0, second=0, microsecond=0)
                if e_h <= s_h:
                    shift_end_t += timedelta(days=1)
                if current_day == now.date() and now < (shift_end_t + timedelta(hours=2)):
                    note_parts.append('قيد العمل')
                else:
                    if apply_missing_penalty:
                        eff_out = shift_end_t - timedelta(hours=missing_penalty_hours)
                        missing_mins += int(missing_penalty_hours * 60)
                        note_parts.append(f'افتراض خروج مبكر {missing_penalty_hours:.0f} ساعة')
                    else:
                        eff_out = shift_end_t  # assume full shift, no penalty
                        note_parts.append('لم يسجل خروج')

            if eff_in and eff_out:
                work_hours = (eff_out - eff_in).total_seconds() / 3600
                # Early leave
                shift_end_t = eff_in.replace(hour=e_h, minute=0, second=0, microsecond=0)
                if e_h <= s_h:
                    shift_end_t += timedelta(days=1)
                if eff_out < shift_end_t:
                    gross_early = int((shift_end_t - eff_out).total_seconds() / 60)
                    penalty_from_co = int(missing_penalty_hours * 60) if 'افتراض خروج' in ' '.join(note_parts) else 0
                    early_mins = max(0, gross_early - penalty_from_co)
                    if status == 'excuse' and excuse_no_early:
                        early_mins = 0
                        note_parts.append('عذر (إلغاء الانصراف المبكر)')
                # Overtime
                if overtime_enabled:
                    daily_ot = max(0.0, work_hours - s_len)
                    if late_mins > max_late_for_ot:
                        if not (status == 'excuse' and excuse_allow_ot):
                            daily_ot = 0.0
                            note_parts.append('إلغاء الإضافي')

        if work_hours > 0:
            working_days += 1
            if status == 'leave':
                vacation_days += 1
            else:
                actual_working_days += 1

        total_hours += work_hours
        total_late_min += late_mins
        total_early_min += early_mins
        total_missing_min += missing_mins

        daily_breakdown.append({
            'date': current_day.isoformat(),
            'check_in': eff_in.isoformat() if eff_in else None,
            'check_out': eff_out.isoformat() if eff_out else None,
            'work_hours': round(work_hours, 2),
            'late_minutes': late_mins,
            'early_minutes': early_mins,
            'overtime_hours': round(daily_ot, 2),
            'status': status,
            'note': ' / '.join(note_parts) if note_parts else '',
        })
        current_day += timedelta(days=1)

    # Final calculations, in Decimal: hours become exact decimals (the days' rounded hours), the
    # money is rounded to the piastre once, where it is stored.
    overtime_hours = sum((Decimal(str(d.get('overtime_hours', 0))) for d in daily_breakdown), ZERO)
    late_hours = Decimal(total_late_min) / 60 * multiplier
    other_hours = Decimal(total_early_min + total_missing_min) / 60
    lateness_deduction = _cents((late_hours + other_hours) * hourly_rate)
    overtime_payment = _cents(overtime_hours * hourly_rate)
    # Use the employee's standard shift length (not the last day's, which may be overridden)
    std_shift_length = shift_hours(start_h, end_h)
    bonus_days = max(0, working_days - days_in_month)
    bonus_payment = _cents(bonus_days * std_shift_length * hourly_rate)
    normal_hours = max(ZERO, Decimal(str(round(total_hours, 6))) - overtime_hours)
    if normal_hours >= scheduled_hours:
        base_pay = monthly_salary
    else:
        base_pay = _cents(monthly_salary * normal_hours / scheduled_hours) if scheduled_hours > 0 else ZERO
    final_salary = base_pay - lateness_deduction - deduction - advance + overtime_payment + bonus_payment + bonus

    return {
        'base_salary': monthly_salary,
        'hourly_rate': hourly_rate.quantize(RATE, rounding=ROUND_HALF_UP),
        'working_days': working_days,
        'actual_working_days': actual_working_days,
        'vacation_days': vacation_days,
        'absent_days': max(0, days_in_month - working_days),
        'total_hours': round(total_hours, 2),
        'lateness_minutes': total_late_min,
        'early_leave_minutes': total_early_min,
        'missing_scan_minutes': total_missing_min,
        'lateness_deduction': lateness_deduction,
        'overtime_hours': float(overtime_hours),
        'overtime_pay': overtime_payment,
        'bonus_days': bonus_days,
        'bonus_payment': bonus_payment,
        'bonus': bonus,
        'deductions': deduction,
        'advances': advance,
        'base_pay': _cents(base_pay),
        'net_salary': _cents(max(ZERO, final_salary)),
        'shift_length': std_shift_length,
        'days_in_month': days_in_month,
        'daily_breakdown': daily_breakdown,
    }
