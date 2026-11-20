"""API endpoints for Mizan Modular App Engine."""
from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework.activation import (
    BUSINESS_PRESETS,
    get_active_modules,
    get_active_preset,
    set_active_modules,
    with_dependencies,
)
from app.catalog import canonical_module
from app.framework.loader import registry
from app.db.base import get_db
from app.dependencies import get_current_user, require_perm

router = APIRouter(prefix="/modules", tags=["modules"])


class ToggleModuleRequest(BaseModel):
    enabled: bool


class ApplyPresetRequest(BaseModel):
    preset_id: str


class UpdateModuleSettingsRequest(BaseModel):
    settings: dict[str, Any]


def _catalog() -> dict:
    """Every module, from its manifest (the registry is the only catalogue)."""
    return {m.id: m for m in registry.get_all_manifests()}


@router.get("")
async def list_modules(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """List all available modules, current tenant active modules, and business presets."""
    active_mods = await get_active_modules(db)
    active_preset = await get_active_preset(db)

    combined = _catalog()

    catalog_list = []
    from app.framework.composition import base_modules, installable
    from app.framework.hooks import workspace_activity

    activity = await workspace_activity(db)
    base = set(base_modules(activity))
    for m in combined.values():
        d = asdict(m)
        d["is_installed"] = m.id in active_mods
        # ADR-006 D2: what this workspace may add, and what its activity starts with.
        d["installable"], d["not_installable_reason"] = installable(m.id, activity)
        d["in_base"] = m.id in base
        catalog_list.append(d)

    presets_list = [asdict(p) for p in BUSINESS_PRESETS.values()]
    categories = registry.get_categories()

    return {
        "active_preset": active_preset,
        "active_modules": active_mods,
        "catalog": catalog_list,
        "presets": presets_list,
        "categories": categories,
    }


@router.get("/categories")
async def get_module_categories(
    _=Depends(get_current_user),
):
    """Return categorized configuration of all modular ERP suites and specialized collections."""
    return {"categories": registry.get_categories()}


@router.get("/{module_id}/settings")
async def get_module_settings_endpoint(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("settings")),
):
    """A module's settings schema and this workspace's values. Under `settings`, as saving is: the
    values hold secrets (the WhatsApp access token)."""
    try:
        return await registry.get_settings(db, module_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="الوحدة المطلوبة غير مسجلة")


@router.post("/{module_id}/settings")
async def save_module_settings_endpoint(
    module_id: str,
    data: UpdateModuleSettingsRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("settings")),
):
    """Save updated settings for a module."""
    try:
        updated = await registry.save_settings(db, module_id, data.settings)
        return {
            "detail": "تم حفظ إعدادات الوحدة بنجاح",
            "settings": updated,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="الوحدة المطلوبة غير مسجلة")


class UninstallRequest(BaseModel):
    confirm: str
    data: str = "keep"  # keep (hidden 30 days) or delete (now, after an export)


@router.post("/{module_id}/toggle")
async def toggle_module(
    module_id: str,
    data: ToggleModuleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("settings")),
):
    """Add a module (with its dependencies) if the workspace's activity allows it. Removing one
    goes through the uninstall flow (preview, typed `delete`, keep or delete its data)."""
    from app.framework.composition import installable, restore_on_install
    from app.framework.hooks import workspace_activity

    module_id = canonical_module(module_id)
    if module_id not in _catalog():
        raise HTTPException(status_code=404, detail="الوحدة المطلوبة غير موجودة في الدليل")
    if not data.enabled:
        raise HTTPException(status_code=409, detail="إزالة الوحدة تتم من «إزالة الوحدة» بعد مراجعة ما سيتأثر")
    activity = await workspace_activity(db)
    ok, reason = installable(module_id, activity)
    if not ok:
        raise HTTPException(status_code=403, detail=reason)
    active = list(await get_active_modules(db))
    # What the module needs, and what those need in turn (sales: pos, finance, contacts…).
    added = [module_id] + [mid for mid in with_dependencies([module_id])[1:] if mid not in active]
    for mid in added:
        ok, reason = installable(mid, activity)
        if not ok:
            raise HTTPException(status_code=403, detail=f"{_catalog().get(mid).name if mid in _catalog() else mid}: {reason}")
    restored = [mid for mid in added if await restore_on_install(db, mid)]
    await set_active_modules(db, list(dict.fromkeys(active + added)))
    return {
        "detail": "تم تثبيت الوحدة" + (" واستعادة بياناتها المحفوظة" if restored else ""),
        "active_modules": await get_active_modules(db),
        "restored": restored,
    }


@router.get("/{module_id}/uninstall-preview")
async def uninstall_preview(module_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_perm("settings"))):
    """What removing the module takes with it: modules that need it, its data, roles using it."""
    from app.framework.composition import uninstall_preview as preview
    from app.framework.hooks import workspace_activity

    module_id = canonical_module(module_id)
    active = await get_active_modules(db)
    if module_id not in active:
        raise HTTPException(status_code=404, detail="الوحدة غير مثبتة")
    if module_id == "core":
        raise HTTPException(status_code=400, detail="لا يمكن إزالة النواة الأساسية للنظام")
    return await preview(db, module_id, active, await workspace_activity(db))


@router.post("/{module_id}/uninstall")
async def uninstall_module(module_id: str, data: UninstallRequest, db: AsyncSession = Depends(get_db),
                           user=Depends(require_perm("settings"))):
    """Remove a module after the owner typed `delete`: its data kept 30 days or deleted now."""
    from app.framework.composition import uninstall
    from app.platform.audit.service import log as audit_log
    from app.platform.tenancy.models import Tenant

    if data.confirm.strip().lower() != "delete":
        raise HTTPException(status_code=422, detail="اكتب delete للتأكيد")
    if data.data not in ("keep", "delete"):
        raise HTTPException(status_code=422, detail="اختر الاحتفاظ بالبيانات أو حذفها")
    tenant = await db.get(Tenant, user.tenant_id)
    result = await uninstall(db, tenant, canonical_module(module_id), data.data, user.id)
    await audit_log(db, "module", "uninstall", user.id, user.full_name, None,
                    {"removed": result["removed"], "data": data.data}, f"إزالة وحدة {module_id}")
    await db.commit()
    return {**result, "active_modules": await get_active_modules(db)}


@router.get("/retention")
async def retention(db: AsyncSession = Depends(get_db), _=Depends(require_perm("settings"))):
    """Removed modules: data kept until a date (reinstalling restores it), or deleted with an export."""
    from sqlalchemy import text as sqltext

    rows = (await db.execute(sqltext("""
        SELECT id, module_id, mode, removed_at, purge_after, export IS NOT NULL AS has_export
        FROM module_retention WHERE mode IN ('kept', 'deleted') ORDER BY removed_at DESC
    """))).mappings().all()
    return [dict(r) for r in rows]


@router.get("/retention/{retention_id}/export")
async def retention_export(retention_id: uuid.UUID, db: AsyncSession = Depends(get_db), _=Depends(require_perm("settings"))):
    """The export taken before deleting a module's data (gzip JSON)."""
    from fastapi.responses import Response
    from sqlalchemy import text as sqltext

    row = (await db.execute(sqltext("SELECT module_id, export FROM module_retention WHERE id = CAST(:i AS uuid)"),
                            {"i": retention_id})).first()
    if not row or not row.export:
        raise HTTPException(status_code=404, detail="لا توجد نسخة")
    return Response(content=row.export, media_type="application/gzip",
                    headers={"Content-Disposition": f'attachment; filename="{row.module_id}-data.json.gz"'})


@router.post("/presets/apply")
async def apply_preset(_=Depends(require_perm("settings"))):
    """Retired: a workspace has one activity, and its modules follow it (ADR-006 D2). Changing
    activity is a guided conversion done with the Mizan team."""
    raise HTTPException(status_code=410, detail="تغيير نشاط المنشأة يتم عبر فريق ميزان؛ ثبّت الوحدات المناسبة من الدليل")


# ─── The store: developers' listed modules and themes (ADR-007 milestone 2, #105) ────────────


async def _store_installed(db: AsyncSession, user) -> dict[str, str]:
    """Item id -> installed version, for this workspace's community modules and theme packages."""
    from sqlalchemy import select

    from app.platform.community.models import CommunityModule
    from app.platform.themes.models import WorkspaceTheme

    out = {m: v for m, v in (await db.execute(select(CommunityModule.module_id, CommunityModule.version))).all()}
    out.update({t: v for t, v in (await db.execute(
        select(WorkspaceTheme.theme_id, WorkspaceTheme.version).where(WorkspaceTheme.tenant_id == user.tenant_id))).all()})
    return out


def _may_browse(user) -> None:
    from app.platform.permissions.access import can

    if not can(user, "community.manage", "themes.manage"):
        raise HTTPException(status_code=403, detail="ليست لديك صلاحية إدارة الإضافات")


@router.get("/store")
async def store(kind: str | None = None, q: str | None = None, db: AsyncSession = Depends(get_db),
                user=Depends(get_current_user)):
    """Listed modules and themes, with what this workspace has installed."""
    from app.platform.marketplace import listings

    _may_browse(user)
    installed = await _store_installed(db, user)
    items = await listings.store(db, kind if kind in listings.STORE_KINDS else None, q)
    return {"items": [{**i, "installed_version": installed.get(i["id"])} for i in items]}


@router.get("/store/{item_id}")
async def store_item(item_id: str, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """A listing in full: what it adds and may access (as an install from a file shows it)."""
    from app.platform.community import service as community
    from app.platform.marketplace import listings
    from app.platform.themes import service as themes

    _may_browse(user)
    item, pkg = await listings.listed_package(db, item_id)
    installed = await _store_installed(db, user)
    if item.kind == "theme":
        detail = themes.package_summary(pkg, await themes.installed_row(db, user.tenant_id, item_id))
    else:
        from sqlalchemy import select

        from app.platform.community.models import CommunityModule

        row = await db.scalar(select(CommunityModule).where(CommunityModule.module_id == item_id))
        detail = community.summary(pkg, row)
    return {"item": {**listings.item_out(item, pkg.developer), "installed_version": installed.get(item_id)}, "detail": detail}


class StoreInstall(BaseModel):
    approved_scopes: list[str] = []


@router.post("/store/{item_id}/install")
async def store_install(item_id: str, body: StoreInstall, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    """Install (or update to) the listed version: verified again, then installed as from a file."""
    from app.platform.community import service as community
    from app.platform.marketplace import listings
    from app.platform.permissions.access import can
    from app.platform.tenancy.context import unbind_tenant
    from app.platform.tenancy.models import Tenant
    from app.platform.themes import service as themes

    item, pkg = await listings.listed_package(db, item_id)
    needed = "themes.manage" if item.kind == "theme" else "community.manage"
    if not can(user, needed):
        raise HTTPException(status_code=403, detail="ليست لديك صلاحية تثبيت هذه الإضافة")
    if item.kind == "theme":
        row = await themes.install(db, await db.get(Tenant, user.tenant_id), pkg, user.id)  # commits
        out = {"id": row.theme_id, "version": row.version}
    else:
        row = await community.install(db, pkg, user.id, body.approved_scopes)  # commits
        out = community.installed_out(row)
    # The listing's install count is a platform row: written with no workspace bound (#112).
    await unbind_tenant(db)
    await listings.count_install(db, item_id)
    await db.commit()
    return out
