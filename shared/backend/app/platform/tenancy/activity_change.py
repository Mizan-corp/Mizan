"""Changing a workspace's activity (ADR-006 phase 9, #107).

An owner asks (owner panel), after seeing what the change does; the Mizan team approves or
rejects it (admin panel); approving applies it at once. What a workspace's activity decides is
mostly read from the activity at run time (variants, menus and home screens, terms, positions),
so the conversion itself is small:

- the workspace's activity (`tenants.sector`, `business_type`) becomes the new one;
- modules the new activity can't run leave, with the modules that need them: their data is kept
  hidden for 30 days (coming back restores it) or deleted after an export, as the owner chose,
  through the same rules as removing a module (`framework.composition`); core ERP data is never
  deleted;
- the new activity's own modules are added (data kept from an earlier stint comes back);
- the settings preset follows, and a theme that belonged to the old activity gives way to the new
  activity's (or Mizan's).

Cloud workspaces only: on-site installs carry their activity in the licence (through support).
Plans don't depend on the activity, so the price doesn't change.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import DateTime, ForeignKey, String, Text, select, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

DATA_MODES = ("keep", "delete")


class ActivityChange(Base):
    """A request to change a workspace's activity, and what became of it. Platform table."""
    __tablename__ = "activity_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
                                          server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    from_activity: Mapped[str] = mapped_column(String(32), nullable=False)
    to_activity: Mapped[str] = mapped_column(String(64), nullable=False)
    data_mode: Mapped[str] = mapped_column(String(8), nullable=False, default="keep", server_default=text("'keep'"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="requested", server_default=text("'requested'"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("owner_accounts.id", ondelete="SET NULL"), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _activity(activity_id: str) -> dict:
    from app.framework.variants import activity

    return activity(activity_id)


def _name(activity_id: str) -> str:
    a = _activity(activity_id)
    return a.get("name") or activity_id


def check_target(tenant, to: str) -> str:
    """The activity id to change to, or a 4xx explaining why not."""
    from app.catalog import canonical_activity
    from app.catalog.sectors import SECTORS
    from app.platform.licensing.services.licences import is_on_premise

    to = canonical_activity(to)
    if to not in SECTORS:
        raise HTTPException(status_code=422, detail="نشاط غير معروف")
    if to == canonical_activity(tenant.sector):
        raise HTTPException(status_code=409, detail="هذا هو نشاط مساحة العمل الحالي")
    if is_on_premise(tenant):
        raise HTTPException(status_code=409, detail="تغيير نشاط النسخ المثبتة على أجهزتك يتم عن طريق الدعم.")
    return to


def plan(tenant, to: str) -> dict:
    """Which modules leave, join and stay, and which ones work differently (no database)."""
    from app.framework import variants
    from app.framework.composition import ALWAYS, base_modules, dependents, installable
    from app.framework.loader import manifest_index

    manifests = manifest_index()
    old = tenant.sector
    active = list(tenant.active_modules or [])
    leaving = [m for m in active if m not in ALWAYS and not installable(m, to)[0]]
    for m in list(leaving):
        for d in dependents(m, active):
            if d not in leaving:
                leaving.append(d)
    staying = [m for m in active if m not in leaving]
    # The new activity's own modules join; general's defaults the workspace removed stay removed.
    general = set(base_modules("general"))
    joining = [m for m in base_modules(to) if m not in staying and m not in general]

    def info(mid: str) -> dict:
        m = manifests.get(mid, {})
        return {"id": mid, "name": m.get("name", mid), "name_en": m.get("name_en", "")}

    changed = []
    for mid in staying:
        before, after = variants.variant_of(mid, old), variants.variant_of(mid, to)
        if before != after:
            changed.append({**info(mid), "from": before, "to": after})
    return {
        "leaving": [info(m) for m in leaving],
        "joining": [info(m) for m in joining],
        "staying": [info(m) for m in staying],
        "variants_changed": changed,
    }


def theme_after(tenant, to: str) -> str | None:
    """The theme the workspace switches to, if its current one belongs to the old activity."""
    from app.platform.themes.service import current_id, file_themes

    themes = file_themes()
    current = themes.get(current_id(tenant))
    if not current or current.get("activity") in (None, "general", to):
        return None
    default = _activity(to).get("theme")
    return default if default in themes else "mizan"


async def preview(db: AsyncSession, tenant, to: str) -> dict:
    """What changing to `to` does, for the owner before asking and the team before approving.
    Binds the workspace to count records; the caller rolls back before writing platform rows."""
    from app.framework.composition import KEEP_DAYS, keeps_data, module_tables
    from app.platform.tenancy.context import bind_tenant

    to = check_target(tenant, to)
    p = plan(tenant, to)
    await bind_tenant(db, tenant.id)
    data = []
    for m in p["leaving"]:
        rows = 0
        for table in module_tables(m["id"]):
            if "tenant_id" in table.c:
                rows += await db.scalar(text(f"SELECT count(*) FROM {table.name}")) or 0
        if rows:
            data.append({**m, "rows": rows, "kept_always": keeps_data(m["id"])})
    new_theme = theme_after(tenant, to)
    return {
        "from": {"id": tenant.sector, "name": _name(tenant.sector)},
        "to": {"id": to, "name": _name(to), "name_en": _activity(to).get("name_en", "")},
        **p,
        "data": data,
        "keep_days": KEEP_DAYS,
        "theme": {"from": (tenant.palette or {}).get("name"), "to": new_theme} if new_theme else None,
        "price_changes": False,
    }


async def open_request(db: AsyncSession, tenant_id) -> ActivityChange | None:
    return await db.scalar(select(ActivityChange).where(
        ActivityChange.tenant_id == tenant_id, ActivityChange.status == "requested"))


async def request(db: AsyncSession, tenant, owner_id, to: str, data_mode: str, note: str | None) -> ActivityChange:
    """Record the owner's request (no workspace bound). The caller commits."""
    to = check_target(tenant, to)
    if data_mode not in DATA_MODES:
        raise HTTPException(status_code=422, detail="اختر ما يحدث لبيانات الوحدات التي ستُزال")
    if await open_request(db, tenant.id):
        raise HTTPException(status_code=409, detail="لديك طلب تغيير نشاط قيد المراجعة بالفعل")
    change = ActivityChange(tenant_id=tenant.id, from_activity=tenant.sector, to_activity=to, data_mode=data_mode,
                            note=(note or "").strip()[:1000] or None, requested_by=owner_id)
    db.add(change)
    await db.flush()
    return change


async def apply(db: AsyncSession, change: ActivityChange, tenant, admin_user_id) -> dict:
    """Carry out an approved change. Binds the workspace and commits its changes; the caller then
    records the decision on `change` (unbound)."""
    from app.framework.activation import SECTOR_TO_PRESET, set_active_modules
    from app.framework.composition import KEEP_DAYS, ModuleRetention, _delete_data, _export, restore_on_install
    from app.catalog.sectors import PALETTE_HUES
    from app.platform.tenancy.context import bind_tenant

    if change.status != "requested":
        raise HTTPException(status_code=409, detail="This request was already decided")
    to = check_target(tenant, change.to_activity)
    p = plan(tenant, to)
    leaving = [m["id"] for m in p["leaving"]]
    new_theme = theme_after(tenant, to)
    old = tenant.sector

    await bind_tenant(db, tenant.id)
    now = datetime.now(UTC)
    if leaving:
        export = None
        if change.data_mode == "delete":
            export = await _export(db, tenant.id, leaving)
            await _delete_data(db, leaving)
        for mid in leaving:
            await db.execute(text("DELETE FROM module_retention WHERE module_id = :m AND mode = 'kept'"), {"m": mid})
            db.add(ModuleRetention(
                module_id=mid, mode="deleted" if change.data_mode == "delete" else "kept", removed_by=None,
                purge_after=None if change.data_mode == "delete" else now + timedelta(days=KEEP_DAYS),
                export=export if mid == leaving[0] else None,
            ))
    restored = [m["id"] for m in p["joining"] if await restore_on_install(db, m["id"])]

    tenant.sector = to
    tenant.business_type = to
    if new_theme:
        tenant.palette = {**(tenant.palette or {}), "name": new_theme, "hue": PALETTE_HUES.get(new_theme, PALETTE_HUES["mizan"])}
    modules = [m["id"] for m in p["staying"]] + [m["id"] for m in p["joining"]]
    await set_active_modules(db, modules, preset_id=SECTOR_TO_PRESET.get(to))  # commits

    return {
        "from": old,
        "to": to,
        "removed": leaving,
        "added": [m["id"] for m in p["joining"]],
        "restored": restored,
        "variants_changed": [m["id"] for m in p["variants_changed"]],
        "data_mode": change.data_mode,
        "theme": new_theme,
        "applied_by": str(admin_user_id) if admin_user_id else None,
    }


def out(change: ActivityChange, tenant_name: str | None = None) -> dict:
    return {
        "id": str(change.id),
        "tenant_id": str(change.tenant_id),
        "tenant_name": tenant_name,
        "from": {"id": change.from_activity, "name": _name(change.from_activity)},
        "to": {"id": change.to_activity, "name": _name(change.to_activity)},
        "data_mode": change.data_mode,
        "status": change.status,
        "note": change.note,
        "decision_note": change.decision_note,
        "result": change.result,
        "created_at": change.created_at.isoformat() if change.created_at else None,
        "decided_at": change.decided_at.isoformat() if change.decided_at else None,
    }
