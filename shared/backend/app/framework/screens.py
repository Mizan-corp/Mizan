"""Screens, widgets and each role's home, menu and dashboard (ADR-006 D4, phase 5).

Modules declare what they offer in their manifest:
  "screens": [{"id": "inventory.products", "path": "/products", "label", "icon", "permission"}]
  "widgets": [{"id": "reporting.sales_today", "label", "permission", "size": "s|m|l"}]
An activity arranges them in activity.json: "menu" (groups of {"screen", "label"?, "icon"?}),
"dashboard" (widget ids, or {"id", "size"}) and "home" (a path), and per standard role in
"roles": {"cashier": {"home": <screen id>, "menu", "dashboard"}}. `general`'s are the defaults.
A workspace can give any role its own layout in the builder (workspace_layouts, kind 'role').

What a user sees, for the role they act as: the workspace's layout for the role, else the
activity's for that role, else the activity's, else general's; then only screens and widgets of
installed modules that the role's permissions allow. A screen's permission is its own: a menu
arranges and renames screens, it never changes who may see them. A variant can relabel a screen
("screens" with a dict value in variant.json).
"""
from __future__ import annotations

import re
from functools import lru_cache

from fastapi import HTTPException

from app.framework import variants

# Available to every workspace whatever its active modules (their routes have no module guard).
ALWAYS_ON = ("core", "reporting")
SIZES = ("s", "m", "l")
GROUP_ID = re.compile(r"^[a-z0-9_]{1,40}$")
ICON = re.compile(r"^[A-Z][A-Za-z0-9]{1,40}$")  # a lucide icon name; unknown ones render a circle


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


def allowed(permission: str | None, granted: frozenset | set) -> bool:
    return not permission or any(p in granted for p in permission.split("|"))


def installed(module_id: str, active) -> bool:
    return module_id in ALWAYS_ON or module_id in active


def screen(screen_id: str, activity_id: str | None) -> dict | None:
    s = catalogue()[0].get(screen_id)
    if s is None:
        return None
    override = (variants.variant(s["module"], activity_id).get("screens") or {}).get(screen_id)
    return {**s, **override} if isinstance(override, dict) else s


def _screen_at(path: str | None) -> str | None:
    return next((sid for sid, s in catalogue()[0].items() if s["path"] == path), None) if path else None


def _dashboard_entry(entry) -> dict:
    return {"id": entry, "size": None} if isinstance(entry, str) else {"id": entry.get("id"), "size": entry.get("size")}


def defaults(activity_id: str | None, role_code: str | None) -> dict:
    """The activity's layout for this standard role, else the activity's, else general's, in
    the builder's form: {"home": screen id, "menu": [...], "dashboard": [{"id", "size"}]}."""
    act = variants.activity(activity_id)
    general = variants.activity("general")
    per_role = (act.get("roles") or {}).get(role_code or "", {}) or {}
    return {
        "home": per_role.get("home") or _screen_at(act.get("home")) or "core.home",
        "menu": per_role.get("menu") or act.get("menu") or general.get("menu") or [],
        "dashboard": [_dashboard_entry(e) for e in
                      (per_role.get("dashboard") or act.get("dashboard") or general.get("dashboard") or [])],
    }


def resolve(layout: dict | None, activity_id: str | None, role_code: str | None,
            granted: frozenset, active_modules: list[str], extra: dict[str, dict] | None = None) -> dict:
    """The home, menu, dashboard and every available screen for a role. `extra`: community modules'
    screens this user may open, by the id an activity's menu uses ("acme.orders/order", ADR-012)."""
    base = defaults(activity_id, role_code)
    layout = layout or {}
    active = set(active_modules)
    extra = extra or {}

    def visible(screen_id: str) -> dict | None:
        if screen_id in extra:
            return extra[screen_id]
        s = screen(screen_id, activity_id)
        if not s or not installed(s["module"], active) or not allowed(s.get("permission"), granted):
            return None
        return s

    menu = []
    for group in layout.get("menu") or base["menu"]:
        items = []
        for entry in group.get("items") or []:
            s = visible(entry["screen"])
            if s:
                items.append({"id": s["id"], "path": s["path"], "label": entry.get("label") or s.get("label"),
                              "icon": entry.get("icon") or s.get("icon")})
        if items:
            menu.append({"id": group.get("id"), "label": group.get("label"), "items": items})

    available = [{"id": s["id"], "path": s["path"], "label": s.get("label"), "icon": s.get("icon"), "module": s["module"]}
                 for sid in catalogue()[0] if (s := visible(sid))]

    home = visible(layout.get("home") or base["home"])

    widgets = catalogue()[1]
    dashboard = []
    for entry in layout.get("dashboard") or base["dashboard"]:
        e = _dashboard_entry(entry)
        w = widgets.get(e["id"])
        if w and installed(w["module"], active) and allowed(w.get("permission"), granted):
            dashboard.append({"id": w["id"], "label": w.get("label"), "module": w["module"], "size": e["size"] or w.get("size")})

    return {"home": home["path"] if home else "/", "menu": menu, "dashboard": dashboard, "screens": available,
            "custom": bool(layout)}


def check_layout(layout: dict) -> dict:
    """A role layout from the builder, cleaned: known screens and widgets, sane sizes."""
    screens, widgets = catalogue()
    out: dict = {}
    home = layout.get("home")
    if home:
        if home not in screens:
            raise HTTPException(422, f"شاشة غير معروفة: {home}")
        out["home"] = home

    menu, seen_groups, seen_screens = [], set(), set()
    for group in (layout.get("menu") or [])[:12]:
        gid = str(group.get("id") or "").strip()
        label = str(group.get("label") or "").strip()[:64]
        if not GROUP_ID.match(gid) or gid in seen_groups:
            raise HTTPException(422, f"معرّف مجموعة غير صالح: {gid or '—'}")
        if not label:
            raise HTTPException(422, "اسم المجموعة مطلوب")
        seen_groups.add(gid)
        items = []
        for entry in (group.get("items") or [])[:60]:
            sid = entry.get("screen")
            if sid not in screens:
                raise HTTPException(422, f"شاشة غير معروفة: {sid}")
            if sid in seen_screens:
                raise HTTPException(422, f"الشاشة مكررة في القائمة: {screens[sid].get('label')}")
            seen_screens.add(sid)
            item = {"screen": sid}
            if (entry.get("label") or "").strip() and entry["label"].strip() != screens[sid].get("label"):
                item["label"] = entry["label"].strip()[:64]
            if ICON.match(str(entry.get("icon") or "")) and entry["icon"] != screens[sid].get("icon"):
                item["icon"] = entry["icon"]
            items.append(item)
        menu.append({"id": gid, "label": label, "items": items})
    if not any(g["items"] for g in menu):
        raise HTTPException(422, "القائمة تحتاج شاشة واحدة على الأقل")
    out["menu"] = menu

    dashboard, seen_widgets = [], set()
    for entry in (layout.get("dashboard") or [])[:24]:
        e = _dashboard_entry(entry)
        if e["id"] not in widgets:
            raise HTTPException(422, f"عنصر لوحة غير معروف: {e['id']}")
        if e["id"] in seen_widgets:
            continue
        seen_widgets.add(e["id"])
        if e["size"] not in (None, *SIZES):
            raise HTTPException(422, f"مقاس غير صالح: {e['size']}")
        dashboard.append({"id": e["id"], **({"size": e["size"]} if e["size"] and e["size"] != widgets[e["id"]].get("size") else {})})
    out["dashboard"] = dashboard
    return out
