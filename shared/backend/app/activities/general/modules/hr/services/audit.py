"""The HR audit log (HR-14): who did what to which record, and when (`hr_audit_log`, written in the
change's own transaction, so a change and its row are saved together or not at all).

What is logged (`action_type` / `entity_type`):
- employees: create, update (the fields that changed, before → after), stop, start;
- attendance: a day saved by hand (create / update, before → after), a CSV import (import);
- advances, deductions and bonuses: create, cancel, carry (advances.py, payroll.py);
- payroll entries: update (an entry's adjustments);
- payroll months (`payroll_period`, entity_id = the month): calculate, submit, approve, pay, reopen.
"""
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def audit(db: AsyncSession, action: str, entity_type: str, entity_id, user_id, reason: str | None = None,
                details: dict | None = None) -> None:
    await db.execute(text("""
        INSERT INTO hr_audit_log (action_type, entity_type, entity_id, performed_by, reason, details)
        VALUES (:action, :entity, :eid, :by, :reason, CAST(:det AS jsonb))
    """), {"action": action, "entity": entity_type, "eid": str(entity_id) if entity_id is not None else None,
           "by": str(user_id) if user_id else None, "reason": reason or "",
           "det": json.dumps(jsonable_encoder(details or {}), ensure_ascii=False)})


def changes(before: dict, after: dict) -> dict:
    """{field: {"from", "to"}} for the fields of `after` whose value differs from `before`."""
    out = {}
    for key, value in after.items():
        old = before.get(key)
        if not _same(old, value):
            out[key] = {"from": jsonable_encoder(old), "to": jsonable_encoder(value)}
    return out


def _same(a, b) -> bool:
    if isinstance(a, datetime) and isinstance(b, datetime):
        return a == b
    if isinstance(a, (int, float, Decimal)) and not isinstance(a, bool) and isinstance(b, (int, float, Decimal, str)) \
            and not isinstance(b, bool):
        try:
            return Decimal(str(a)) == Decimal(str(b))
        except InvalidOperation:
            return False
    return str(a if a is not None else "") == str(b if b is not None else "")
