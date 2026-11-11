"""The screen builder's API (ADR-006 D4, phase 5): each role's home, menu and dashboard, and each
record's form, per workspace. Used by the owner and staff with the `designer` permission. A
layout arranges what a role may already open; it never grants anything (permissions decide).
Custom fields are edited through /settings/fields (same permission)."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user, require_perm
from app.platform.auth.models.user import User

# Included by the settings router (prefix /settings).
router = APIRouter()


class LayoutIn(BaseModel):
    home: str | None = None
    menu: list[dict[str, Any]] = []
    dashboard: list[Any] = []


class FormIn(BaseModel):
    sections: list[dict[str, Any]] = []
    hidden: list[str] = []


async def _role(db: AsyncSession, role_id: uuid.UUID) -> dict:
    from app.platform.permissions.access import available_roles

    role = next((r for r in await available_roles(db) if r["id"] == role_id), None)
    if role is None:
        raise HTTPException(404, "الدور غير موجود")
    return role


async def _audit(db: AsyncSession, user: User, action: str, what: str, note: str, changes: dict | None = None):
    from app.platform.audit.service import log

    await log(db, "layout", action, user.id, user.full_name, None, {"target": what, **(changes or {})}, note)


@router.get("/screens")
async def my_screens(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """The acting role's home, menu and dashboard, and every screen it may open."""
    from app.framework import layouts
    from app.framework.activation import get_active_modules
    from app.framework.hooks import workspace_activity
    from app.framework.screens import resolve

    acting = getattr(user, "acting_role", None)
    layout = await layouts.get(db, "role", str(acting["id"])) if acting else {}
    return resolve(layout, await workspace_activity(db), acting["code"] if acting else None,
                   getattr(user, "effective_permissions", frozenset()), await get_active_modules(db))


@router.get("/forms/{record}")
async def form(record: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """A record's form for this workspace: its sections and fields (built-in and custom)."""
    from app.framework import layouts
    from app.framework.hooks import workspace_activity

    return await layouts.form_for(db, record, await workspace_activity(db))


@router.get("/designer")
async def overview(db: AsyncSession = Depends(get_db), _: User = Depends(require_perm("designer"))):
    """What the builder can change: the workspace's roles and the records' forms and fields."""
    from sqlalchemy import select

    from app.framework import fields as F
    from app.framework import layouts
    from app.platform.permissions.access import available_roles

    saved = {(k, t) for k, t in (await db.execute(select(layouts.WorkspaceLayout.kind, layouts.WorkspaceLayout.target))).all()}
    return {
        "roles": [{"id": r["id"], "code": r["code"], "name": r["name"], "standard": r["standard"],
                   "custom": ("role", str(r["id"])) in saved} for r in await available_roles(db)],
        "forms": [{"record": rec, "label": f["label"], "custom": ("form", rec) in saved}
                  for rec, f in layouts.forms().items()],
        "field_records": list(F.RECORDS),
    }


@router.get("/designer/roles/{role_id}")
async def role_layout(role_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_perm("designer"))):
    """A role's layout to edit (its own, else the activity's default), and what it can contain:
    every screen and widget of the installed modules, marked by whether the role may open it."""
    from app.framework import layouts, screens
    from app.framework.activation import get_active_modules
    from app.framework.hooks import workspace_activity

    role = await _role(db, role_id)
    activity_id = await workspace_activity(db)
    active = set(await get_active_modules(db))
    granted = set(role["grants"] or [])
    saved = await layouts.get(db, "role", str(role_id))
    base = screens.defaults(activity_id, role["code"])
    all_screens, all_widgets = screens.catalogue()
    return {
        "role": {"id": role["id"], "code": role["code"], "name": role["name"], "standard": role["standard"]},
        "custom": bool(saved),
        "layout": {"home": saved.get("home") or base["home"], "menu": saved.get("menu") or base["menu"],
                   "dashboard": saved.get("dashboard") or base["dashboard"]},
        "screens": [{"id": sid, "label": s.get("label"), "path": s["path"], "icon": s.get("icon"), "module": s["module"],
                     "allowed": screens.allowed(s.get("permission"), granted)}
                    for sid in all_screens if (s := screens.screen(sid, activity_id)) and screens.installed(s["module"], active)],
        "widgets": [{"id": wid, "label": w.get("label"), "size": w.get("size"), "module": w["module"],
                     "allowed": screens.allowed(w.get("permission"), granted)}
                    for wid, w in all_widgets.items() if screens.installed(w["module"], active)],
    }


@router.put("/designer/roles/{role_id}")
async def save_role_layout(role_id: uuid.UUID, data: LayoutIn, db: AsyncSession = Depends(get_db),
                           user: User = Depends(require_perm("designer"))):
    from app.framework import layouts, screens

    role = await _role(db, role_id)
    layout = screens.check_layout(data.model_dump())
    await layouts.save(db, "role", str(role_id), layout, user.id)
    await _audit(db, user, "save", f"role:{role['code']}", f"تعديل شاشات الدور {role['name']}")
    await db.commit()
    return await role_layout(role_id, db, user)


@router.delete("/designer/roles/{role_id}", status_code=204)
async def reset_role_layout(role_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_perm("designer"))):
    """Back to the activity's default layout for this role."""
    from app.framework import layouts

    role = await _role(db, role_id)
    await layouts.reset(db, "role", str(role_id))
    await _audit(db, user, "reset", f"role:{role['code']}", f"إعادة شاشات الدور {role['name']} للافتراضي")
    await db.commit()


@router.get("/designer/forms/{record}")
async def form_layout(record: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_perm("designer"))):
    """A record's form to edit: its sections and the fields it leaves out."""
    return await form(record, db, _)


@router.put("/designer/forms/{record}")
async def save_form_layout(record: str, data: FormIn, db: AsyncSession = Depends(get_db),
                           user: User = Depends(require_perm("designer"))):
    from app.framework import layouts
    from app.framework.hooks import workspace_activity

    activity_id = await workspace_activity(db)
    layout = await layouts.check_form(db, record, activity_id, data.model_dump())
    await layouts.save(db, "form", record, layout, user.id)
    await _audit(db, user, "save", f"form:{record}", f"تعديل نموذج {layouts.forms()[record]['label']}")
    await db.commit()
    return await layouts.form_for(db, record, activity_id)


@router.delete("/designer/forms/{record}", status_code=204)
async def reset_form_layout(record: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("designer"))):
    from app.framework import layouts

    if record not in layouts.forms():
        raise HTTPException(404, "نموذج غير معروف")
    await layouts.reset(db, "form", record)
    await _audit(db, user, "reset", f"form:{record}", f"إعادة نموذج {layouts.forms()[record]['label']} للافتراضي")
    await db.commit()
