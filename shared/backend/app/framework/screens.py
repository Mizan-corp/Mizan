"""Screens, widgets and each role's home, menu and dashboard (ADR-006 D4, phase 5).

Modules declare what they offer in their manifest:
  "screens": [{"id": "inventory.products", "path": "/products", "label", "icon", "permission"}]
  "widgets": [{"id": "reporting.sales_today", "label", "permission", "size": "s|m|l"}]
An activity arranges them (`activity.json` "menu", "dashboard", "home", and per standard role
"roles": {"cashier": {"home", "menu", "dashboard"}}); `general`'s menu is everyone's default.
A workspace role can have its own layout (sys_roles.layout, edited in the builder).

What a user sees, for the role they act as: the role's layout, else the activity's layout for
that role, else the activity's, else general's; then only screens and widgets of installed
modules that the role's permissions allow. A variant can relabel a screen ("screens" with a
dict value in variant.json).
"""
from __future__ import annotations

from functools import lru_cache

from app.framework import variants

# Available to every workspace whatever its active modules (their routes have no module guard).
ALWAYS_ON = ("core", "reporting")


@lru_cache(maxsize=1)
def catalogue() -> tuple[dict[str, dict], dict[str, dict]]:
    """(screens by id, widgets by id), each with its module."""
    from app.framework.loader import manifest_index

    screens, widgets = {}, {}
    for module_id, m in manifest_index().items():
        if m.get("status") == "planned":
            continue
        for s in m.get("screens") or []:
            if isinstance(s, dict) and s.get("id"):
                screens[s["id"]] = {**s, "module": module_id}
        for w in m.get("widgets") or []:
            if isinstance(w, dict) and w.get("id"):
                widgets[w["id"]] = {**w, "module": module_id}
    return screens, widgets


def _allowed(permission: str | None, granted: frozenset) -> bool:
    return not permission or any(p in granted for p in permission.split("|"))


def _active(module_id: str, active: set) -> bool:
    return module_id in ALWAYS_ON or module_id in active


def _screen(screen_id: str, activity_id: str | None) -> dict | None:
    s = catalogue()[0].get(screen_id)
    if s is None:
        return None
    override = (variants.variant(s["module"], activity_id).get("screens") or {}).get(screen_id)
    return {**s, **override} if isinstance(override, dict) else s


def defaults(activity_id: str | None, role_code: str | None) -> dict:
    """The activity's layout for this standard role, else the activity's, else general's."""
    act = variants.activity(activity_id)
    general = variants.activity("general")
    per_role = (act.get("roles") or {}).get(role_code or "", {}) or {}
    return {
        "home": per_role.get("home") or act.get("home_screen") or general.get("home_screen"),
        "home_path": act.get("home"),
        "menu": per_role.get("menu") or act.get("menu") or general.get("menu") or [],
        "dashboard": per_role.get("dashboard") or act.get("dashboard") or general.get("dashboard") or [],
    }


def resolve(layout: dict | None, activity_id: str | None, role_code: str | None,
            granted: frozenset, active_modules: list[str]) -> dict:
    """The home, menu, dashboard and every available screen for a role."""
    base = defaults(activity_id, role_code)
    layout = layout or {}
    active = set(active_modules)
    hidden = set(layout.get("hidden") or [])

    def visible(screen_id: str, permission: str | None = None) -> dict | None:
        s = _screen(screen_id, activity_id)
        if not s or screen_id in hidden or not _active(s["module"], active):
            return None
        if not _allowed(permission if permission is not None else s.get("permission"), granted):
            return None
        return s

    menu = []
    for group in layout.get("menu") or base["menu"]:
        items = []
        for entry in group.get("items") or []:
            s = visible(entry["screen"], entry.get("permission"))
            if s:
                items.append({"id": s["id"], "path": entry.get("path") or s["path"],
                              "label": entry.get("label") or s.get("label"), "icon": entry.get("icon") or s.get("icon")})
        if items:
            menu.append({"id": group.get("id"), "label": group.get("label"), "items": items})

    available = [{"id": s["id"], "path": s["path"], "label": s.get("label"), "icon": s.get("icon"), "module": s["module"]}
                 for sid in catalogue()[0] if (s := visible(sid))]

    home_id = layout.get("home") or base["home"]
    home = visible(home_id) if home_id else None
    home_path = home["path"] if home else (base["home_path"] if base["home_path"] and any(
        i["path"] == base["home_path"] for g in menu for i in g["items"]) else None) or "/"

    widgets = catalogue()[1]
    dashboard = []
    for entry in layout.get("dashboard") or base["dashboard"]:
        # "widget.id", or {"id", "size"} to place it at another size than the module's default.
        wid, size = (entry, None) if isinstance(entry, str) else (entry.get("id"), entry.get("size"))
        w = widgets.get(wid)
        if w and _active(w["module"], active) and _allowed(w.get("permission"), granted) and wid not in hidden:
            dashboard.append({**{k: w.get(k) for k in ("id", "label", "size", "module")}, **({"size": size} if size else {})})

    return {"home": home_path, "menu": menu, "dashboard": dashboard, "screens": available,
            "custom": bool(layout)}
