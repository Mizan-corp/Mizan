"""What every screen reads at runtime (ADR-006 D4): the acting role's home, menu and dashboard
(/settings/screens) and a record's form for this workspace (/settings/forms/<record>). The editing
endpoints (/settings/designer/*) were removed in step 8d: layouts are authored by developers and
in Studio, not by the owner. Stored layouts keep applying. The custom-field editing API
(/settings/fields) and the `designer` permission were removed in step 8f; fields declared by
activities and modules still apply, and workspace_fields rows already stored still show."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import get_current_user
from app.platform.auth.models.user import User

# Included by the settings router (prefix /settings).
router = APIRouter()


@router.get("/screens")
async def my_screens(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """The acting role's home, menu and dashboard, and every screen it may open."""
    from app.framework import layouts
    from app.framework.activation import get_active_modules
    from app.framework.hooks import workspace_activity
    from app.framework.screens import resolve

    from app.platform.community.service import menu_items

    acting = getattr(user, "acting_role", None)
    layout = await layouts.get(db, "role", str(acting["id"])) if acting else {}
    community = await menu_items(db, user)
    # A developer's activity places its own modules' screens in its menus (ADR-012).
    own = {f"{c['module']}/{c['path'].rsplit('/', 1)[1]}": {**{k: c[k] for k in ("id", "path", "label", "icon")}, "module": c["module"]}
           for c in community}
    activity = await workspace_activity(db)
    out = resolve(layout, activity, acting["code"] if acting else None,
                  getattr(user, "effective_permissions", frozenset()), await get_active_modules(db), own)
    # Community modules' screens (ADR-007) the menu doesn't place, in a group of their own.
    placed = {i["path"] for g in out["menu"] for i in g["items"]}
    rest = [c for c in community if c["path"] not in placed]
    if rest:
        out["menu"].append({"id": "community", "label": "وحدات إضافية", "items": [{k: c[k] for k in ("id", "path", "label", "icon")} for c in rest]})
    out["screens"] += [{**{k: c[k] for k in ("id", "path", "label", "icon")}, "module": c["module"]} for c in community]
    return out


@router.get("/forms/{record}")
async def form(record: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """A record's form for this workspace: its sections and fields (built-in and custom)."""
    from app.framework import layouts
    from app.framework.hooks import workspace_activity

    return await layouts.form_for(db, record, await workspace_activity(db))
