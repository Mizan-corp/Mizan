"""How a workspace is composed (ADR-006 D2).

- At creation: `general`'s default modules plus the activity's (`base_modules`).
- Adding a module (`installable`): from `general`, the workspace's activity or its family, or a
  module of another activity that has a variant for this one; platform modules and connectors
  always; planned modules never.
- Removing a module: a preview of the consequences (`uninstall_preview`), then `uninstall`: the
  modules that depend on it go too, and the owner chooses to keep the data hidden for 30 days
  (reinstalling restores it) or delete it now, after an export. `purge_due` deletes kept data
  after 30 days. Data of the core ERP modules (`general`) is never deleted: everything else
  relies on it.
"""
from __future__ import annotations

import gzip
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import DateTime, LargeBinary, String, Table, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.catalog import activities, canonical_modules, family_of
from app.db.base import Base
from app.framework import variants
from app.platform.tenancy.context import TenantScoped

KEEP_DAYS = 30
ALWAYS = ("core",)


def system_modules() -> tuple[str, ...]:
    """Modules that are part of the ERP itself (manifest `system: true`, e.g. the site builder):
    always on in every workspace, never offered in the module centre or marketplace."""
    return tuple(sorted(i for i, m in _manifests().items() if m.get("system")))


def always_on() -> tuple[str, ...]:
    return (*ALWAYS, *system_modules())


class ModuleRetention(TenantScoped, Base):
    """A removed module's data: kept hidden until purge_after, or deleted (with an export)."""
    __tablename__ = "module_retention"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # kept, deleted, purged, restored
    removed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Delete now: a gzip JSON copy of the rows, kept with the record (works where files don't persist).
    export: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    removed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


def _manifests() -> dict[str, dict]:
    from app.framework.loader import manifest_index

    return manifest_index()


def base_modules(activity_id: str | None) -> list[str]:
    """What a new workspace of this activity starts with."""
    acts = activities()
    act = variants.activity(activity_id)
    return canonical_modules(["core", *system_modules(), *acts.get("general", {}).get("modules", []), *(act.get("modules") or [])])


def installable(module_id: str, activity_id: str | None) -> tuple[bool, str]:
    """Whether this workspace may add the module, and why not."""
    m = _manifests().get(module_id)
    if not m:
        return False, "الوحدة غير موجودة"
    if m.get("status") == "planned":
        return False, "الوحدة قيد التطوير ولم تُتح بعد"
    if m.get("kind") in ("platform", "integration") or module_id in ALWAYS:
        return True, ""
    home = m.get("activity", "general")
    act = variants.activity(activity_id).get("id") or activity_id
    if home in ("general", act) or module_id in base_modules(activity_id):
        return True, ""
    if act and family_of(home) and family_of(home) == family_of(act):
        return True, ""
    if act and act in variants.all_variants().get(module_id, {}):
        return True, ""
    return False, "هذه الوحدة لنشاط آخر وليس لها نسخة تناسب نشاط منشأتك"


def dependents(module_id: str, active: list[str]) -> list[str]:
    """Active modules that need this one, directly or through others."""
    manifests = _manifests()
    out: list[str] = []
    frontier = [module_id]
    while frontier:
        current = frontier.pop()
        for mid in active:
            if mid not in out and mid != module_id and current in manifests.get(mid, {}).get("dependencies", []):
                out.append(mid)
                frontier.append(mid)
    return out


def used_by_variants(module_id: str, activity_id: str | None) -> list[str]:
    """The workspace's variants that use this module ("inventory · pharmacy" uses batches): it
    can't be removed while the activity runs them."""
    out = []
    manifests = _manifests()
    act_name = variants.activity(activity_id).get("name_en") or activity_id
    for mid, vid in variants.variants_for(activity_id).items():
        if module_id in (variants.variant(mid, activity_id).get("uses") or []):
            out.append(f"{manifests.get(mid, {}).get('name', mid)} ({act_name})")
    return out


def module_tables(module_id: str) -> list[Table]:
    """The tables a module's models define, children before parents (safe delete order)."""
    from app.framework.loader import module_dirs

    path = module_dirs().get(module_id)
    if path is None:
        return []
    app_root = Path(__file__).resolve().parents[1]
    package = ".".join(("app", *path.relative_to(app_root).parts)) + "."
    names = {m.local_table.name for m in Base.registry.mappers if m.class_.__module__.startswith(package)}
    return [t for t in reversed(Base.metadata.sorted_tables) if t.name in names]


def keeps_data(module_id: str) -> bool:
    """Core ERP data (general) is never deleted when its module is removed."""
    return _manifests().get(module_id, {}).get("activity", "general") == "general"


async def uninstall_preview(db: AsyncSession, module_id: str, active: list[str], activity_id: str | None = None) -> dict:
    manifests = _manifests()
    going = [module_id, *dependents(module_id, active)]
    data = []
    for mid in going:
        for table in module_tables(mid):
            if "tenant_id" in table.c:
                rows = await db.scalar(text(f"SELECT count(*) FROM {table.name}"))
                if rows:
                    data.append({"module": mid, "table": table.name, "rows": rows})
    granted = {p.get("id") if isinstance(p, dict) else p for mid in going for p in manifests.get(mid, {}).get("permissions", [])}
    roles = []
    if granted:
        rows = (await db.execute(text("SELECT name, grants FROM sys_roles WHERE tenant_id IS NOT NULL OR is_system"))).all()
        roles = sorted({name for name, grants in rows if granted & set(grants or [])})
    return {
        "module": module_id,
        "removed": [{"id": mid, "name": manifests.get(mid, {}).get("name", mid)} for mid in going],
        "data": data,
        "roles": roles,
        "data_kept_always": [mid for mid in going if keeps_data(mid)],
        "keep_days": KEEP_DAYS,
        "blocked_by": [u for mid in going for u in used_by_variants(mid, activity_id)],
    }


def _json(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    return value


async def _export(db: AsyncSession, tenant_id, module_ids: list[str]) -> bytes:
    """A gzip JSON copy of the modules' rows for this workspace (the backup before deleting)."""
    dump: dict = {"tenant_id": str(tenant_id), "exported_at": datetime.now(UTC).isoformat(), "tables": {}}
    for mid in module_ids:
        for table in module_tables(mid):
            rows = (await db.execute(text(f"SELECT * FROM {table.name}"))).mappings().all()
            dump["tables"][table.name] = [{k: _json(v) for k, v in r.items()} for r in rows]
    return gzip.compress(json.dumps(dump, ensure_ascii=False).encode())


async def _delete_data(db: AsyncSession, module_ids: list[str]) -> None:
    for mid in module_ids:
        if keeps_data(mid):
            continue
        for table in module_tables(mid):
            if "tenant_id" in table.c:
                await db.execute(text(f"DELETE FROM {table.name}"))  # RLS: this workspace's rows only


async def uninstall(db: AsyncSession, tenant, module_id: str, mode: str, user_id) -> dict:
    """Remove the module (and those needing it); keep its data 30 days or delete it now."""
    if module_id in always_on():
        raise HTTPException(400, "لا يمكن إزالة النواة الأساسية للنظام")
    active = list(tenant.active_modules or [])
    if module_id not in active:
        raise HTTPException(404, "الوحدة غير مثبتة")
    going = [module_id, *dependents(module_id, active)]
    blocked = [u for mid in going for u in used_by_variants(mid, variants.activity(tenant.sector).get("id") or tenant.sector)]
    if blocked:
        raise HTTPException(409, f"لا يمكن إزالتها: نشاط المنشأة يعتمد عليها ({'، '.join(blocked)})")
    tenant.active_modules = [m for m in active if m not in going]
    now = datetime.now(UTC)
    export = None
    if mode == "delete":
        export = await _export(db, tenant.id, going)
        await _delete_data(db, going)
    for mid in going:
        await db.execute(text("DELETE FROM module_retention WHERE module_id = :m AND mode = 'kept'"), {"m": mid})
        db.add(ModuleRetention(
            module_id=mid, mode="deleted" if mode == "delete" else "kept", removed_by=user_id,
            purge_after=None if mode == "delete" else now + timedelta(days=KEEP_DAYS), export=export if mid == module_id else None,
        ))
    return {"removed": going, "mode": mode, "purge_after": None if mode == "delete" else (now + timedelta(days=KEEP_DAYS)).isoformat()}


async def restore_on_install(db: AsyncSession, module_id: str) -> bool:
    """Reinstalling within 30 days brings the kept data back (it was only hidden)."""
    res = await db.execute(text(
        "UPDATE module_retention SET mode = 'restored' WHERE module_id = :m AND mode = 'kept' RETURNING id"
    ), {"m": module_id})
    return res.first() is not None


async def purge_due(db: AsyncSession) -> int:
    """Delete kept data whose 30 days are over (all workspaces; run by the nightly job)."""
    from app.platform.tenancy.context import bind_tenant

    due = (await db.execute(text(
        "SELECT id, tenant_id, module_id FROM module_retention WHERE mode = 'kept' AND purge_after < now()"
    ))).all()
    for rid, tid, mid in due:
        await bind_tenant(db, tid)
        active = await db.scalar(text("SELECT active_modules FROM tenants WHERE id = :t"), {"t": tid}) or []
        if mid not in active:  # reinstalled meanwhile: nothing to purge
            await _delete_data(db, [mid])
        await db.execute(text("UPDATE module_retention SET mode = 'purged' WHERE id = :r"), {"r": rid})
    await db.commit()
    return len(due)
