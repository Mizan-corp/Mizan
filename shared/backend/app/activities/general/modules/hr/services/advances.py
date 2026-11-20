"""HR money records of an employee: advances (سلفة, cash paid now from a safe or wallet and
deducted from the month's salary), deductions (خصم) and bonuses (مكافأة), which only change the
salary. A record is never deleted: it is cancelled, and a cancelled advance's cash goes back to
where it came from and its ledger entry is reversed (ADR-014). Records of a month whose payroll
is approved or paid can't be added or cancelled."""
import uuid

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework.events import notify
from app.platform.tenancy import clock
from app.activities.general.modules.hr.services.audit import audit
from app.activities.general.modules.hr.services.payroll import ensure_month_open, month_of, record_kind


async def _audit(db: AsyncSession, action: str, employee_id, user_id, reason: str, details: dict) -> None:
    await audit(db, action, "advance", employee_id, user_id, reason, details)


async def add_record(db: AsyncSession, data, user) -> uuid.UUID:
    from app.activities.general.modules.finance.services import payments

    record_type = getattr(data.record_type, "value", data.record_type)
    day = data.date or clock.today()  # the workspace's day
    # The employee is looked up in the workspace first: another workspace's id used to pass the
    # foreign key and move this workspace's cash.
    emp = (await db.execute(text("SELECT id, name, is_active FROM hr_employees WHERE id=:id FOR SHARE"),
                            {"id": data.employee_id})).mappings().first()
    if emp is None:
        raise HTTPException(404, "الموظف غير موجود")
    if not emp["is_active"]:
        raise HTTPException(400, "الموظف موقوف")
    await ensure_month_open(db, month_of(day), "السلف والخصومات والمكافآت")

    is_advance = record_kind(record_type) == "advance"
    if is_advance:
        payments.check_source(data.safe_id, data.wallet_id, "حدد الخزنة أو المحفظة التي تُصرف منها السلفة")
    safe_id, wallet_id = (data.safe_id, data.wallet_id) if is_advance else (None, None)
    advance_id = (await db.execute(text("""
        INSERT INTO hr_advances (employee_id, amount, date, note, created_by, record_type, safe_id, wallet_id)
        VALUES (:eid, :amt, :dt, :note, :by, :rt, :sid, :wid)
        RETURNING id
    """), {"eid": data.employee_id, "amt": data.amount, "dt": day, "note": data.note or "", "by": user.id,
           "rt": record_type, "sid": safe_id, "wid": wallet_id})).scalar_one()
    if is_advance:
        await payments.money_out(db, data.amount, safe_id=safe_id, wallet_id=wallet_id, ref_type="hr_advance",
                                 ref_id=advance_id, note=f"سلفة {emp['name']}".strip(), user_id=user.id)
        # Cash handed to the employee now: the ledger posts it in this transaction (ADR-014 D3).
        await notify("hr_advance.paid", db, advance_id=advance_id, employee_id=data.employee_id, amount=data.amount,
                     safe_id=safe_id, wallet_id=wallet_id, note=data.note, user_id=user.id)
    await _audit(db, "create", data.employee_id, user.id, data.note or "", {
        "id": str(advance_id), "type": record_type, "amount": float(data.amount),
        "safe_id": str(safe_id) if safe_id else None, "wallet_id": str(wallet_id) if wallet_id else None})
    return advance_id


async def cancel_record(db: AsyncSession, advance_id, reason: str | None, user) -> dict:
    """Cancel an advance, deduction or bonus of an open month. An advance's cash comes back into
    the safe or wallet it was paid from, and its ledger entry is reversed."""
    from app.activities.general.modules.finance.services import payments

    row = (await db.execute(text("SELECT * FROM hr_advances WHERE id=:id FOR UPDATE"), {"id": advance_id})).mappings().first()
    if row is None:
        raise HTTPException(404, "السجل غير موجود")
    if row["status"] == "cancelled":
        raise HTTPException(409, "هذا السجل ملغى بالفعل")
    if row.get("carried_from_period_id"):
        raise HTTPException(409, "سلفة مرحّلة من رواتب شهر سابق: لا تُلغى إلا بإعادة فتح ذلك الشهر")
    await ensure_month_open(db, month_of(row["date"]), "السلف والخصومات والمكافآت")

    if record_kind(row["record_type"]) == "advance" and (row["safe_id"] or row["wallet_id"]):
        name = (await db.execute(text("SELECT name FROM hr_employees WHERE id=:id"), {"id": row["employee_id"]})).scalar() or ""
        await payments.money_in(db, row["amount"], safe_id=row["safe_id"], wallet_id=row["wallet_id"],
                                ref_type="hr_advance_cancel", ref_id=row["id"], note=f"إلغاء سلفة {name}".strip(),
                                user_id=user.id)
        await notify("hr_advance.cancelled", db, advance_id=row["id"], employee_id=row["employee_id"],
                     amount=row["amount"], user_id=user.id)
    updated = (await db.execute(text("""
        UPDATE hr_advances SET status='cancelled', cancelled_at=now(), cancelled_by=:by, cancel_reason=:reason,
            updated_at=now()
        WHERE id=:id RETURNING *
    """), {"id": row["id"], "by": user.id, "reason": reason or ""})).mappings().one()
    await _audit(db, "cancel", row["employee_id"], user.id, reason or "", {
        "id": str(row["id"]), "type": row["record_type"], "amount": float(row["amount"])})
    return dict(updated)
