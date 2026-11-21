"""Recurring expenses (FIN-9): every night (`recurring_expenses` in
`app/platform/automation_worker/runner.py`, nightly group of `deploy/server/mizan-cron.sh`) each
recurring expense whose next date has come gets its next occurrence: a new draft, dated that day,
with the same vendor, category, branch, amount, VAT, description, payment method and source. The
draft is approved (paid) or rejected like any other; no money moves here.

- The next date is the expense's date plus a week, a month or a year (PostgreSQL's interval
  arithmetic: the 31st of a month is followed by the last day of a shorter month).
- An occurrence is used once: `recurred_at` is set when its successor is made, in the same
  transaction and under a row lock, so two runs never make the same occurrence twice. The new
  draft is recurring too and carries the series on, and `recurred_from` points to the one before.
- The series goes on whatever an occurrence's status (a rejected or cancelled one is a decision
  about that month only). It stops at its end date, when recurrence is switched off on the latest
  occurrence, or when the latest draft is deleted.
- A run catches up: an expense whose job didn't run for a while gets every missed occurrence.
"""
import logging
import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mizan.finance")

NEXT_DATE = """(e.date + CASE e.recurring_interval WHEN 'weekly' THEN interval '7 days'
                                           WHEN 'yearly' THEN interval '1 year'
                                           ELSE interval '1 month' END)::date"""
BATCH = 500
MAX_ROUNDS = 400  # a weekly expense ten years behind; a guard against a loop, never reached in use

COPIED = ("vendor_id", "category_id", "warehouse_id", "amount", "tax_amount", "description", "payment_method",
          "wallet_id", "safe_id", "recurring_interval", "recurring_end_date", "notes", "created_by")


async def create_due(db: AsyncSession, today: date) -> int:
    """The next occurrences due by `today` in the bound workspace. Returns how many were made.
    The caller commits."""
    made = 0
    for _ in range(MAX_ROUNDS):
        due = (await db.execute(text(f"""
            SELECT e.id, {NEXT_DATE} AS next_date
            FROM expenses e
            WHERE e.is_recurring AND e.recurred_at IS NULL
              AND {NEXT_DATE} <= :today
              AND (e.recurring_end_date IS NULL OR {NEXT_DATE} <= e.recurring_end_date)
            ORDER BY e.date, e.id
            LIMIT :batch
            FOR UPDATE OF e SKIP LOCKED
        """), {"today": today, "batch": BATCH})).all()
        if not due:
            break
        for row in due:
            cols = ", ".join(COPIED)
            await db.execute(text(f"""
                INSERT INTO expenses (id, {cols}, date, status, is_recurring, recurred_from)
                SELECT :new_id, {cols}, :next_date, 'draft', true, e.id FROM expenses e WHERE e.id = :id
            """), {"new_id": uuid.uuid4(), "next_date": row.next_date, "id": row.id})
            await db.execute(text("UPDATE expenses SET recurred_at = now() WHERE id = :id"), {"id": row.id})
            made += 1
    return made


async def run_all(db: AsyncSession) -> dict:
    """Every active workspace, each in its own transaction: one workspace's failure doesn't stop
    the others. Dates are each workspace's day (Africa/Cairo)."""
    from app.platform.tenancy import clock
    from app.platform.tenancy.context import bind_tenant, current_tenant_id

    tenants = (await db.execute(text("SELECT id FROM tenants WHERE status IN ('active', 'trial') ORDER BY id"))).scalars().all()
    await db.commit()
    made = failed = 0
    for tid in tenants:
        try:
            await bind_tenant(db, tid)
            made += await create_due(db, clock.today())
            await db.commit()
        except Exception as e:  # noqa: BLE001 (logged; the next workspace still runs)
            await db.rollback()
            failed += 1
            logger.warning("Recurring expenses of %s failed: %s", tid, e)
    current_tenant_id.set(None)
    return {"message": f"أُنشئ {made} مصروفًا دوريًا كمسودة بانتظار الاعتماد" + (f"، وتعذر ذلك في {failed} منشأة" if failed else ""),
            "items_processed": made, "failed": failed}
