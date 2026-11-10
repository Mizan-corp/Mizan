"""API endpoints for Mizan Modular App Engine."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.modules import (
    BUSINESS_PRESETS,
    MODULE_CATALOG,
    get_active_modules,
    get_active_preset,
    set_active_modules,
)
from app.modules.loader import registry
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
    """Built-in catalogue plus the modules discovered from their manifests."""
    return {**MODULE_CATALOG, **{m.id: m for m in registry.get_all_manifests()}}


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
    for m in combined.values():
        d = asdict(m)
        d["is_installed"] = m.id in active_mods
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
    _=Depends(get_current_user),
):
    """Retrieve settings schema and current tenant values for a module."""
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


@router.post("/{module_id}/toggle")
async def toggle_module(
    module_id: str,
    data: ToggleModuleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("settings")),
):
    """Enable or disable a specific module."""
    # The same catalogue the module centre lists: discovered modules can be enabled too.
    catalog = _catalog()
    if module_id not in catalog:
        raise HTTPException(status_code=404, detail="الوحدة المطلوبة غير موجودة في الدليل")

    if module_id == "core" and not data.enabled:
        raise HTTPException(status_code=400, detail="لا يمكن تعطيل النواة الأساسية للنظام")

    active = set(await get_active_modules(db))

    if data.enabled:
        active.add(module_id)
        # Add dependencies
        manifest = catalog[module_id]
        for dep in manifest.dependencies:
            active.add(dep)
    else:
        # Check if other active modules depend on this one
        dependent = [
            m.name
            for m in catalog.values()
            if m.id in active and module_id in m.dependencies and m.id != module_id
        ]
        if dependent:
            raise HTTPException(
                status_code=400,
                detail=f"لا يمكن تعطيل هذه الوحدة لأن الوحدات التالية تعتمد عليها: {', '.join(dependent)}",
            )
        active.discard(module_id)

    await set_active_modules(db, list(active))
    return {
        "detail": "تم تحديث حالة الوحدة بنجاح",
        "active_modules": list(active),
    }


@router.post("/presets/apply")
async def apply_preset(
    data: ApplyPresetRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_perm("settings")),
):
    """Apply a business collection preset (Retail, Restaurant, School, Services)."""
    preset = BUSINESS_PRESETS.get(data.preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="حزمة النشاط المطلوبة غير مسجلة")

    await set_active_modules(db, preset.modules, preset_id=data.preset_id)
    return {
        "detail": f"تم تطبيق حزمة «{preset.name}» بنجاح",
        "active_preset": data.preset_id,
        "active_modules": preset.modules,
    }

