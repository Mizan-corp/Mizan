"""Storage quota (ADR-006 D3): what a workspace stores, analysed by module.

What counts: its database rows (each table's rows times that table's average row size), the
data of removed modules kept for 30 days, exports taken before deleting a module's data, and
the files its records point to. Limits come from the plan: a warning at 80%; at 100% new
uploads are refused, while sales and daily work never stop.

Measuring touches every workspace table, so the result is kept in storage_usage and refreshed
by the nightly job, or on demand when it's older than a few minutes.
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import BigInteger, DateTime, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

WARN_AT = 0.8
FRESH = timedelta(minutes=10)
DEFAULT_ROW_BYTES = 200


class StorageUsage(Base):
    """The last measurement of a workspace's storage (one row per workspace)."""
    __tablename__ = "storage_usage"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    by_module: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


def _table_modules() -> dict[str, str]:
    """table -> the module whose models define it ('core' for the platform's own)."""
    from app.framework.composition import module_tables
    from app.framework.loader import module_dirs

    out: dict[str, str] = {}
    for module_id in module_dirs():
        for table in module_tables(module_id):
            out.setdefault(table.name, module_id)
    return out


def _file_bytes(paths: list[str]) -> int:
    from app.core.config import settings

    total = 0
    root = getattr(settings, "UPLOAD_DIR", "uploads")
    for url in paths:
        if not url or not url.startswith("/uploads/"):
            continue
        path = os.path.join(root, url.removeprefix("/uploads/"))
        if os.path.isfile(path):
            total += os.path.getsize(path)
    return total


async def measure(db: AsyncSession, tenant_id) -> dict:
    """Measure now (the workspace must be bound: RLS limits every count to its rows)."""
    tables = (await db.execute(text("""
        SELECT c.relname, pg_total_relation_size(c.oid) AS bytes, GREATEST(c.reltuples, 0) AS tuples
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
          AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped)
    """))).all()
    owners = _table_modules()
    kept = set((await db.execute(text("SELECT module_id FROM module_retention WHERE mode = 'kept'"))).scalars())
    by_module: dict[str, dict] = {}
    for name, size, tuples in tables:
        rows = await db.scalar(text(f'SELECT count(*) FROM "{name}"'))
        if not rows:
            continue
        per_row = (size / tuples) if tuples and tuples > 0 else DEFAULT_ROW_BYTES
        module = owners.get(name, "core")
        entry = by_module.setdefault(module, {"bytes": 0, "rows": 0, "kept": module in kept})
        entry["bytes"] += int(rows * per_row)
        entry["rows"] += rows
    exports = await db.scalar(text("SELECT COALESCE(sum(length(export)), 0) FROM module_retention WHERE export IS NOT NULL"))
    if exports:
        by_module["module_exports"] = {"bytes": int(exports), "rows": 0, "kept": False}
    files = _file_bytes(list((await db.execute(text("""
        SELECT image_url FROM products WHERE image_url IS NOT NULL
        UNION ALL SELECT value FROM store_settings WHERE key = 'logo_url'
    """))).scalars()))
    if files:
        by_module["files"] = {"bytes": files, "rows": 0, "kept": False}
    total = sum(e["bytes"] for e in by_module.values())
    await db.execute(text("""
        INSERT INTO storage_usage (tenant_id, measured_at, total_bytes, by_module) VALUES (:t, now(), :b, CAST(:m AS jsonb))
        ON CONFLICT (tenant_id) DO UPDATE SET measured_at = now(), total_bytes = EXCLUDED.total_bytes, by_module = EXCLUDED.by_module
    """), {"t": tenant_id, "b": total, "m": __import__("json").dumps(by_module)})
    return {"total_bytes": total, "by_module": by_module, "measured_at": datetime.now(UTC)}


SPECIAL = {"core": "النظام والمستخدمون والسجلات", "module_exports": "نسخ بيانات الوحدات المحذوفة", "files": "الملفات والصور"}


def _name(module_id: str) -> str:
    from app.framework.loader import manifest_index

    return SPECIAL.get(module_id) or manifest_index().get(module_id, {}).get("name", module_id)


async def limit_bytes(db: AsyncSession, tenant_id) -> int:
    from app.platform.billing.plans import get_plan_limits

    plan = await db.scalar(text("SELECT plan FROM tenants WHERE id = :t"), {"t": tenant_id})
    return int(get_plan_limits(plan or "trial")["max_storage_mb"]) * 1024 * 1024


async def usage(db: AsyncSession, tenant_id, refresh: bool = False) -> dict:
    """The workspace's storage: used, limit, state (ok, warn, full) and the analysis by module."""
    row = (await db.execute(text("SELECT measured_at, total_bytes, by_module FROM storage_usage WHERE tenant_id = :t"),
                            {"t": tenant_id})).first()
    if row is None or refresh and datetime.now(UTC) - row.measured_at > FRESH:
        measured = await measure(db, tenant_id)
        used, by_module, at = measured["total_bytes"], measured["by_module"], measured["measured_at"]
    else:
        used, by_module, at = row.total_bytes, row.by_module, row.measured_at
    limit = await limit_bytes(db, tenant_id)
    share = used / limit if limit else 0
    return {
        "used_bytes": used, "limit_bytes": limit, "percent": round(share * 100, 1),
        "state": "full" if share >= 1 else "warn" if share >= WARN_AT else "ok",
        "measured_at": at.isoformat() if hasattr(at, "isoformat") else at,
        "by_module": sorted(({"module": k, "name": _name(k), **v} for k, v in (by_module or {}).items()),
                            key=lambda e: -e["bytes"]),
    }


async def ensure_room(db: AsyncSession, incoming: int) -> None:
    """Refuse an upload when the bound workspace is out of storage (daily work is never blocked)."""
    from app.platform.tenancy.context import current_tenant_id

    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        return
    u = await usage(db, tenant_id)
    if u["used_bytes"] + incoming > u["limit_bytes"]:
        raise HTTPException(413, "مساحة التخزين ممتلئة: لا يمكن رفع ملفات جديدة. حرّر مساحة أو رقِّ الباقة من لوحة المالك؛ البيع والعمل اليومي مستمران.")


async def measure_all(db: AsyncSession) -> int:
    """Nightly: measure every active workspace, and warn those past 80%."""
    from app.platform.tenancy.context import bind_tenant, current_tenant_id

    tenants = (await db.execute(text("SELECT id FROM tenants WHERE status <> 'deleted'"))).scalars().all()
    for tid in tenants:
        await bind_tenant(db, tid)
        u = await usage(db, tid, refresh=True)
        if u["state"] != "ok":
            recent = await db.scalar(text("""
                SELECT 1 FROM notifications WHERE type = 'storage_alert' AND created_at > now() - interval '1 day' LIMIT 1
            """))
            if not recent:
                await db.execute(text("""
                    INSERT INTO notifications (id, tenant_id, type, severity, title, body, link, is_read)
                    VALUES (gen_random_uuid(), :t, 'storage_alert', :sev, :title, :body, '/settings', false)
                """), {"t": tid, "sev": "error" if u["state"] == "full" else "warning",
                       "title": "مساحة التخزين ممتلئة" if u["state"] == "full" else "مساحة التخزين تقترب من الحد",
                       "body": f"تستخدم منشأتك {u['percent']}% من مساحة التخزين. حرّر مساحة أو رقِّ الباقة من لوحة المالك."
                               + (" رفع الملفات متوقف حتى ذلك؛ البيع والعمل اليومي مستمران." if u["state"] == "full" else "")})
        await db.commit()
    current_tenant_id.set(None)
    return len(tenants)
