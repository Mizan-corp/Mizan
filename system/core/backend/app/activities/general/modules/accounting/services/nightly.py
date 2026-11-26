"""The nightly reconciliation check (ADR-014 D8), run by the automation runner
(`accounting_reconciliation` in `app/platform/automation_worker/runner.py`, nightly group of
`deploy/server/mizan-cron.sh`).

For every workspace where accounting is on and the ledger has entries, `reports.reconciliation`
compares the ledger with the operational balances (customers, suppliers, safes, wallets, stock).
When something differs, the users who may read the accounting reports (`accounting:view`: the
owner's admin role, accountants, managers) get one notification, at most once a day, linking to the
reconciliation report. It only reads and notifies: the ledger is the truth and nothing is changed.
"""
import json
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.services import reports

logger = logging.getLogger("mizan.accounting")
NOTIFICATION_TYPE = "accounting_reconciliation"
LINK = "/accounting/reports?tab=reconciliation"


async def _recipients(db: AsyncSession, tenant_id: uuid.UUID) -> list[uuid.UUID]:
    return list((await db.execute(text("""
        SELECT DISTINCT u.id FROM users u
        JOIN user_role_assignments a ON a.user_id = u.id AND a.is_active
        JOIN sys_roles r ON r.id = a.role_id
        WHERE u.tenant_id = :t AND u.is_active AND r.grants @> CAST(:perm AS jsonb)
    """), {"t": tenant_id, "perm": json.dumps(["accounting:view"])})).scalars().all())


def _summary(rec: dict) -> str:
    parts = [f"{i['label']}: فرق {i['difference']:,.2f}" for i in rec["differences"][:4]]
    if len(rec["differences"]) > 4:
        parts.append(f"و{len(rec['differences']) - 4} بنود أخرى")
    if rec["parties"]:
        parts.append(f"{len(rec['parties'])} عميل/مورد يختلف رصيده عن الدفاتر")
    return "؛ ".join(parts)


async def check_workspace(db: AsyncSession, tenant_id: uuid.UUID) -> dict | None:
    """Reconcile one workspace (bound by the caller). Returns the reconciliation when it found
    differences, None when it agrees or the ledger is empty. Notifies at most once a day."""
    if not await db.scalar(text("SELECT 1 FROM acc_entries WHERE tenant_id = :t LIMIT 1"), {"t": tenant_id}):
        return None
    rec = await reports.reconciliation(db, tenant_id)
    if rec["ok"] and not rec["parties"]:
        return None
    recent = await db.scalar(text(
        "SELECT 1 FROM notifications WHERE tenant_id = :t AND type = :type AND created_at > now() - interval '20 hours' LIMIT 1"),
        {"t": tenant_id, "type": NOTIFICATION_TYPE})
    if not recent:
        has_opening = await db.scalar(text(
            "SELECT 1 FROM acc_entries WHERE tenant_id = :t AND source_type = 'opening' LIMIT 1"), {"t": tenant_id})
        body = "الفحص الليلي وجد فروقاً بين الدفاتر والأرصدة التشغيلية: " + _summary(rec) + "."
        if not has_opening:
            body += " لم يُسجَّل القيد الافتتاحي بعد، وهو سبب الفروق غالباً."
        data = json.dumps({"differences": [{k: i[k] for k in ("key", "ledger", "operational", "difference")}
                                           for i in rec["differences"]], "parties": len(rec["parties"])}, default=str)
        for user_id in await _recipients(db, tenant_id):
            await db.execute(text("""
                INSERT INTO notifications (id, tenant_id, user_id, type, severity, title, body, link, data_json, is_read)
                VALUES (:id, :t, :u, :type, 'warning', :title, :body, :link, CAST(:data AS jsonb), false)
            """), {"id": uuid.uuid4(), "t": tenant_id, "u": user_id, "type": NOTIFICATION_TYPE,
                   "title": "فروق بين الدفاتر والأرصدة", "body": body, "link": LINK, "data": data})
    return rec


async def reconcile_all(db: AsyncSession) -> dict:
    """Every workspace with accounting on. One workspace's failure doesn't stop the others."""
    from app.catalog import canonical_modules
    from app.platform.tenancy.context import bind_tenant, current_tenant_id

    rows = (await db.execute(text("SELECT id, active_modules FROM tenants WHERE status <> 'deleted'"))).all()
    await db.commit()
    tenants = [r.id for r in rows if "accounting" in canonical_modules(list(r.active_modules or []))]
    checked = flagged = failed = 0
    for tid in tenants:
        try:
            await bind_tenant(db, tid)
            if await check_workspace(db, tid) is not None:
                flagged += 1
            await db.commit()
            checked += 1
        except Exception as e:  # noqa: BLE001 (logged; the next workspace still runs)
            await db.rollback()
            failed += 1
            logger.warning("Nightly reconciliation of %s failed: %s", tid, e)
    current_tenant_id.set(None)
    return {"message": f"فُحصت دفاتر {checked} منشأة: {flagged} بها فروق" + (f"، وتعذر فحص {failed}" if failed else ""),
            "items_processed": checked, "flagged": flagged, "failed": failed}
