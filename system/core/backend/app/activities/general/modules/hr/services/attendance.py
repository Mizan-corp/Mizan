"""HR Attendance domain services.

Encapsulates attendance CSV parsing, time normalization, and device sync processing.
"""
from __future__ import annotations

import csv
import io
from datetime import date as _date
from datetime import UTC as _UTC
from datetime import datetime as _dt
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.hr.services.payroll import LOCKED_STATUSES, month_of
from app.activities.general.modules.hr.services.audit import audit

STATUSES = {"present", "absent", "leave", "mission", "excuse"}
MAX_CSV_BYTES = 5 * 1024 * 1024


def _parse_time(raw: str, work_date: _date) -> _dt | None:
    """Jibble/CSV times come in many shapes: ISO, %H:%M, %H:%M:%S, 12h AM/PM. Returns tz-naive datetime or None."""
    s = str(raw).strip()
    if not s:
        return None
    # Strip UTC designators / timezone offsets for ISO parsing
    c = s.replace("Z", "+00:00").replace("UTC", "+00:00")
    c = c.replace(" (UTC)", "").replace("(UTC)", "")
    if "T" not in c:
        parts = c.split(" ")
        if any((":" in p and any(ch.isdigit() for ch in p[:2])) for p in parts[1:]) or (len(parts) == 1 and ":" in c):
            if len(parts) >= 2 and ":" not in parts[0]:
                c = parts[0] + "T" + " ".join(parts[1:])
    try:
        return _dt.fromisoformat(c).replace(tzinfo=None)
    except ValueError:
        pass
    # Date-time formats
    for fmt in (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"
    ):
        try:
            return _dt.strptime(s, fmt)
        except ValueError:
            continue
    # Time-only formats → combine with work_date
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M:%S%p", "%I:%M%p"):
        try:
            parsed = _dt.strptime(s, fmt)
            return _dt.combine(work_date, parsed.time())
        except ValueError:
            continue
    return None


async def import_attendance_csv_stream(db: AsyncSession, content: bytes, user=None) -> dict[str, Any]:
    """Parses and ingests attendance CSV logs. Days saved by hand (edited) are kept, and days in
    a month whose payroll is approved or paid are refused (listed in the errors). The import is
    one row of the HR audit log (how many days were added, updated and skipped)."""
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(400, "الملف أكبر من 5 ميجابايت")
    try:
        text_content = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "الملف ليس ملف CSV بترميز UTF-8") from None
    reader = csv.DictReader(io.StringIO(text_content))

    try:
        fieldnames = reader.fieldnames
    except csv.Error:
        raise HTTPException(400, "تعذرت قراءة ملف CSV") from None
    if not fieldnames:
        raise HTTPException(400, "الملف فارغ أو لا يحتوي على ترويسة أعمدة")

    col_map = {}
    for h in reader.fieldnames:
        hl = h.lower().strip().replace("_", " ").replace("(", "").replace(")", "")
        if hl in ("employee code", "emp code", "uid", "employee id", "employee", "emp id", "code", "id", "user id"):
            col_map[h] = "emp_code"
        elif hl in ("member", "name", "employee name", "full name", "fullname", "person"):
            col_map[h] = "emp_name" if "emp_code" not in col_map.values() else "note"
        elif hl in ("date", "work date", "attendance date", "day", "clock in date", "clock out date", "start date", "end date", "workday"):
            col_map[h] = "date"
        elif hl in ("check in", "clock in", "time in", "in", "checkin", "start time", "start", "begin"):
            col_map[h] = "check_in"
        elif hl in ("check out", "clock out", "time out", "out", "checkout", "end time", "end", "finish"):
            col_map[h] = "check_out"
        elif hl in ("status", "attendance status", "state"):
            col_map[h] = "status"

    has_code = "emp_code" in col_map.values()
    has_name = "emp_name" in col_map.values()
    if "date" not in col_map.values():
        raise HTTPException(400, f"يجب أن يحتوي ملف CSV على عمود للتاريخ. الموجود: {reader.fieldnames}")
    if not has_code and not has_name:
        raise HTTPException(400, f"يجب أن يحتوي ملف CSV على كود أو اسم الموظف. الموجود: {reader.fieldnames}")

    added = updated = skipped = 0
    errors = []
    month_locked: dict[str, bool] = {}

    try:
        rows = list(reader)
    except csv.Error:
        raise HTTPException(400, "تعذرت قراءة ملف CSV") from None
    for row in rows:
        try:
            emp_code_raw = str(row.get(next(k for k, v in col_map.items() if v == "emp_code"), "")).strip() if has_code else ""
            emp_name_raw = str(row.get(next(k for k, v in col_map.items() if v == "emp_name"), "")).strip() if has_name else ""
            date_str = str(row.get(next(k for k, v in col_map.items() if v == "date"), "")).strip()
            check_in_raw = row.get(next(k for k, v in col_map.items() if v == "check_in"), "").strip() if "check_in" in col_map.values() else ""
            check_out_raw = row.get(next(k for k, v in col_map.items() if v == "check_out"), "").strip() if "check_out" in col_map.values() else ""
            status_raw = row.get(next(k for k, v in col_map.items() if v == "status"), "").strip() if "status" in col_map.values() else "present"
        except (IndexError, KeyError, AttributeError):
            skipped += 1
            continue

        if not (emp_code_raw or emp_name_raw) or not date_str:
            skipped += 1
            continue

        emp = None
        if emp_code_raw:
            emp = (await db.execute(text("SELECT id FROM hr_employees WHERE emp_code=:code"), {"code": emp_code_raw})).fetchone()
        if not emp and emp_name_raw:
            emp = (await db.execute(text(
                "SELECT id FROM hr_employees WHERE is_active=TRUE AND LOWER(REPLACE(name,' ',''))=LOWER(REPLACE(:n,' ',''))"
            ), {"n": emp_name_raw})).fetchone()

        if not emp:
            errors.append(f"الموظف غير موجود: {emp_name_raw or emp_code_raw}")
            skipped += 1
            continue

        try:
            work_date = _date.fromisoformat(date_str[:10])
        except ValueError:
            parsed_d = None
            for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%b %d %Y", "%d %b %Y", "%b %d, %Y", "%d %b, %Y", "%Y/%m/%d"):
                try:
                    parsed_d = _dt.strptime(date_str.strip(), fmt).date()
                    break
                except ValueError:
                    continue
            if not parsed_d:
                errors.append(f"تاريخ غير صالح '{date_str}'")
                skipped += 1
                continue
            work_date = parsed_d

        month = month_of(work_date)
        if month not in month_locked:
            # FOR SHARE: the month can't be approved while this import is writing into it.
            status = (await db.execute(text("SELECT status FROM hr_payroll_periods WHERE month=:m FOR SHARE"),
                                       {"m": month})).scalar_one_or_none()
            month_locked[month] = status in LOCKED_STATUSES
            if month_locked[month]:
                errors.append(f"رواتب شهر {month} معتمدة أو مصروفة — لم تُستورد أيامه")
        if month_locked[month]:
            skipped += 1
            continue

        # Wall-clock times marked UTC, as the payroll engine reads them (it drops the zone).
        check_in = _parse_time(check_in_raw, work_date) if check_in_raw else None
        check_out = _parse_time(check_out_raw, work_date) if check_out_raw else None
        check_in = check_in.replace(tzinfo=_UTC) if check_in else None
        check_out = check_out.replace(tzinfo=_UTC) if check_out else None
        if check_in_raw and check_in is None:
            errors.append(f"وقت غير صالح '{check_in_raw}'")
        if check_out_raw and check_out is None:
            errors.append(f"وقت غير صالح '{check_out_raw}'")

        status = (status_raw or "present").strip().lower()
        status = "present" if status in ("regular", "") or status not in STATUSES else status

        existing = (await db.execute(text(
            "SELECT id, edited FROM hr_attendance WHERE employee_id=:e AND work_date=:d"
        ), {"e": emp[0], "d": work_date})).fetchone()

        if existing:
            if existing[1]:
                skipped += 1
                continue
            await db.execute(text(
                "UPDATE hr_attendance SET check_in=:ci, check_out=:co, status=:st WHERE id=:id"
            ), {"ci": check_in, "co": check_out, "st": status, "id": existing[0]})
            updated += 1
        else:
            await db.execute(text(
                "INSERT INTO hr_attendance (employee_id, work_date, check_in, check_out, status) VALUES (:e,:d,:ci,:co,:st)"
            ), {"e": emp[0], "d": work_date, "ci": check_in, "co": check_out, "st": status})
            added += 1

    if added or updated:
        await audit(db, "import", "attendance", None, getattr(user, "id", None), "استيراد حضور من ملف CSV",
                    {"added": added, "updated": updated, "skipped": skipped, "months": sorted(month_locked)})
    await db.commit()
    return {
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:20],
        "total": added + updated + skipped,
    }
