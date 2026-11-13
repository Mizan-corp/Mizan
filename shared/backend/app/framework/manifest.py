"""Community module manifests and entities (ADR-007): the checks the platform and the `mizan` CLI
share. Standard library only, so mizan-sdk ships this file as is.

Official modules' manifest v2 checks stay in loader.manifest_problems().

A community manifest (`manifest.json` at the root of a .mzm package):
  {"id": "acme.visits", "name": "الزيارات", "name_en": "Visits", "version": "1.0.0",
   "kind": "community", "description": "...", "icon": "CalendarCheck",
   "entities": ["visit"],                       # entities/<id>.json
   "permissions": [{"id": "acme.visits.view", "name": "...", "name_en": "..."}],
   "menu": [{"entity": "visit", "label": "الزيارات", "icon": "CalendarCheck", "permission": "acme.visits.view"}],
   "scopes": ["customers:read", "events:sale.confirmed"],
   "webhooks": {"url": "https://example.com/mizan", "events": ["sale.confirmed"]},
   "settings_schema": [...]}

An entity (`entities/<id>.json`):
  {"id": "visit", "name": "زيارة", "name_en": "Visit", "title": "customer",
   "fields": [{"key": "customer", "type": "reference", "to": "customers", "label": "العميل", "required": true},
              {"key": "on", "type": "date", "label": "التاريخ"},
              {"key": "fee", "type": "money", "label": "الرسوم"},
              {"key": "state", "type": "select", "options": ["مجدولة", "تمت"], "label": "الحالة"}],
   "list": ["on", "customer", "state"],
   "form": {"sections": [{"id": "main", "label": "الزيارة", "fields": ["customer", "on", "fee", "state"]}]}}
"""
from __future__ import annotations

import re

MODULE_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}\.[a-z][a-z0-9_]{1,47}$")  # <developer>.<module>
KEY = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
ICON = re.compile(r"^[A-Z][A-Za-z0-9]{1,40}$")
EVENT = re.compile(r"^[a-z_]+\.[a-z_]+$")

FIELD_TYPES = ("text", "number", "money", "date", "boolean", "select", "reference")
# Built-in records an entity field may reference, and the scope that lets a module read them.
BUILT_IN_REFERENCES = {"customers": "customers:read", "suppliers": "suppliers:read", "products": "products:read",
                       "employees": "employees:read", "branches": "branches:read"}
# What a module may ask for (D3). Its own entities need no scope.
DATA_SCOPES = {
    "customers:read": ("قراءة العملاء", "Read customers"),
    "customers:write": ("إضافة العملاء وتعديلهم", "Create and edit customers"),
    "suppliers:read": ("قراءة الموردين", "Read suppliers"),
    "products:read": ("قراءة الأصناف والأسعار", "Read products and prices"),
    "stock:read": ("قراءة أرصدة المخزون", "Read stock levels"),
    "sales:read": ("قراءة فواتير المبيعات", "Read sales invoices"),
    "employees:read": ("قراءة بيانات الموظفين", "Read employees"),
    "branches:read": ("قراءة الفروع", "Read branches"),
}
EVENTS = {
    "sale.confirmed": ("عند تأكيد فاتورة بيع", "When a sale is confirmed"),
    "sale.returned": ("عند مرتجع مبيعات", "When a sale is returned"),
    "customer.created": ("عند إضافة عميل", "When a customer is added"),
    "product.updated": ("عند تعديل صنف", "When a product changes"),
    "record.created": ("عند إضافة سجل من سجلات الوحدة", "When one of the module's records is added"),
    "record.updated": ("عند تعديل سجل من سجلات الوحدة", "When one of the module's records changes"),
}
SCOPES = {**DATA_SCOPES, **{f"events:{e}": v for e, v in EVENTS.items()}}

MAX_ENTITIES = 20
MAX_FIELDS = 60


def _text(v, limit: int = 128) -> bool:
    return isinstance(v, str) and 0 < len(v.strip()) <= limit


def community_manifest_problems(m: dict, entity_ids: set[str] | None = None) -> list[str]:
    """What's wrong with a community manifest; [] when it's fine. `entity_ids`: the entity files
    the package actually has (checked against `entities` when given)."""
    p: list[str] = []
    if not isinstance(m, dict):
        return ["manifest.json must be a JSON object"]
    mid = m.get("id")
    if not isinstance(mid, str) or not MODULE_ID.match(mid):
        p.append("id must be '<developer>.<module>' in lower case (letters, digits, _), e.g. acme.visits")
    for k in ("name", "name_en"):
        if not _text(m.get(k)):
            p.append(f"{k} is required (1–128 characters)")
    if not isinstance(m.get("version"), str) or not VERSION.match(m["version"]):
        p.append("version must be MAJOR.MINOR.PATCH, e.g. 1.0.0")
    if m.get("kind") != "community":
        p.append("kind must be 'community'")
    if m.get("icon") is not None and not (isinstance(m["icon"], str) and ICON.match(m["icon"])):
        p.append("icon must be a lucide icon name, e.g. CalendarCheck")
    for forbidden in ("router", "models", "frontend", "category", "activity"):
        if forbidden in m:
            p.append(f"'{forbidden}' isn't allowed in a community module")

    entities = m.get("entities", [])
    if not isinstance(entities, list) or not all(isinstance(e, str) and KEY.match(e) for e in entities):
        p.append("entities must be a list of entity ids")
        entities = []
    if len(entities) > MAX_ENTITIES:
        p.append(f"at most {MAX_ENTITIES} entities")
    if len(set(entities)) != len(entities):
        p.append("entity ids must be unique")
    if entity_ids is not None:
        for e in set(entities) - entity_ids:
            p.append(f"entities/{e}.json is missing")
        for e in entity_ids - set(entities):
            p.append(f"entities/{e}.json isn't listed in 'entities'")

    perm_ids: set[str] = set()
    perms = m.get("permissions", [])
    if not isinstance(perms, list):
        p.append("permissions must be a list")
        perms = []
    for perm in perms:
        pid = perm.get("id") if isinstance(perm, dict) else None
        if not isinstance(pid, str) or not (isinstance(mid, str) and pid.startswith(mid + ".")):
            p.append(f"permission ids must start with the module id ({mid}.…)")
            continue
        if not (_text(perm.get("name")) and _text(perm.get("name_en"))):
            p.append(f"permission {pid} needs name and name_en")
        perm_ids.add(pid)

    menu = m.get("menu", [])
    if not isinstance(menu, list):
        p.append("menu must be a list")
        menu = []
    for item in menu:
        if not isinstance(item, dict) or item.get("entity") not in entities:
            p.append("each menu item must point at one of the module's entities")
            continue
        if not _text(item.get("label"), 64):
            p.append(f"menu item for {item['entity']} needs a label")
        if item.get("permission") is not None and item["permission"] not in perm_ids:
            p.append(f"menu item for {item['entity']}: permission {item['permission']} isn't declared")

    scopes = m.get("scopes", [])
    if not isinstance(scopes, list):
        p.append("scopes must be a list")
        scopes = []
    for s in scopes:
        if s not in SCOPES:
            p.append(f"unknown scope: {s}")

    hooks = m.get("webhooks")
    if hooks is not None:
        if not isinstance(hooks, dict) or not isinstance(hooks.get("url"), str) or not hooks["url"].startswith("https://"):
            p.append("webhooks.url must be an https:// address")
        events = hooks.get("events", []) if isinstance(hooks, dict) else []
        for e in events if isinstance(events, list) else ["?"]:
            if e not in EVENTS:
                p.append(f"unknown event: {e}")
            elif e not in ("record.created", "record.updated") and f"events:{e}" not in scopes:
                p.append(f"event {e} needs the scope events:{e}")
    return p


def entity_problems(e: dict, entity_ids: set[str], scopes: set[str]) -> list[str]:
    """What's wrong with one entity file; [] when it's fine."""
    if not isinstance(e, dict):
        return ["an entity must be a JSON object"]
    eid = e.get("id")
    p: list[str] = []
    where = f"entity {eid}"
    if not isinstance(eid, str) or not KEY.match(eid):
        p.append("entity id must be lower-case letters, digits and _")
    for k in ("name", "name_en"):
        if not _text(e.get(k)):
            p.append(f"{where}: {k} is required")
    fields = e.get("fields")
    if not isinstance(fields, list) or not fields:
        return p + [f"{where}: fields must be a non-empty list"]
    if len(fields) > MAX_FIELDS:
        p.append(f"{where}: at most {MAX_FIELDS} fields")
    keys: list[str] = []
    for f in fields:
        if not isinstance(f, dict):
            p.append(f"{where}: each field must be an object")
            continue
        key, kind = f.get("key"), f.get("type", "text")
        if not isinstance(key, str) or not KEY.match(key):
            p.append(f"{where}: field keys must be lower-case letters, digits and _")
            continue
        keys.append(key)
        if kind not in FIELD_TYPES:
            p.append(f"{where}.{key}: unknown type {kind}")
        if not _text(f.get("label")):
            p.append(f"{where}.{key}: label is required")
        if kind == "select" and not (isinstance(f.get("options"), list) and f["options"]
                                     and all(_text(o, 64) for o in f["options"])):
            p.append(f"{where}.{key}: a select needs options")
        if kind == "reference":
            to = f.get("to")
            if to in BUILT_IN_REFERENCES:
                if BUILT_IN_REFERENCES[to] not in scopes:
                    p.append(f"{where}.{key}: referencing {to} needs the scope {BUILT_IN_REFERENCES[to]}")
            elif to not in entity_ids:
                p.append(f"{where}.{key}: 'to' must be one of the module's entities or {', '.join(BUILT_IN_REFERENCES)}")
    if len(set(keys)) != len(keys):
        p.append(f"{where}: field keys must be unique")
    known = set(keys)
    if e.get("title") is not None and e["title"] not in known:
        p.append(f"{where}: title must be one of its fields")
    for k in e.get("list", []) or []:
        if k not in known:
            p.append(f"{where}: list column {k} isn't a field")
    form = e.get("form")
    if form is not None:
        sections = form.get("sections") if isinstance(form, dict) else None
        if not isinstance(sections, list):
            p.append(f"{where}: form.sections must be a list")
        else:
            for s in sections:
                for k in (s.get("fields") if isinstance(s, dict) else None) or []:
                    if k not in known:
                        p.append(f"{where}: form field {k} isn't a field")
    return p


# ── Theme packs (ADR-010 D3) ─────────────────────────────────────────────────────
# A theme sets the app's design tokens (the CSS variables of shared/frontend/src/styles.css) for
# light and dark, and picks fonts, corner radius, shadows and motion. Only these keys and strict
# value formats are accepted, so a theme can't inject CSS or break layouts.

THEME_REQUIRED = ("background", "foreground", "card", "card-foreground", "primary", "primary-foreground",
                  "secondary", "secondary-foreground", "muted", "muted-foreground", "accent", "accent-foreground",
                  "border", "input", "ring", "sidebar", "sidebar-foreground", "sidebar-primary",
                  "sidebar-primary-foreground", "sidebar-accent", "sidebar-accent-foreground", "sidebar-border",
                  "sidebar-ring")
THEME_OPTIONAL = ("popover", "popover-foreground", "destructive", "destructive-foreground", "success",
                  "success-foreground", "warning", "warning-foreground", "chart-1", "chart-2", "chart-3",
                  "chart-4", "chart-5")
THEME_TOKENS = THEME_REQUIRED + THEME_OPTIONAL
THEME_SHADOWS = ("flat", "soft", "raised")
THEME_MOTION = ("full", "reduced", "none")
THEME_DENSITY = ("comfortable", "compact")
FONT_FILE = re.compile(r"^assets/[A-Za-z0-9_.-]+\.(woff2|woff|ttf|otf)$")
FONT_WEIGHT = re.compile(r"^[1-9]00( [1-9]00)?$")
FONT_FAMILY = re.compile(r"^[A-Za-z0-9 \u0600-\u06FF-]{1,64}$")
RADIUS = re.compile(r"^(0|\d(\.\d{1,3})?rem|\d{1,2}px)$")
THEME_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}(\.[a-z][a-z0-9_]{1,47})?$")  # mizan | <developer>.<theme>
_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_NUM = r"-?\d+(\.\d+)?%?"
_RGB = re.compile(rf"^rgba?\(\s*({_NUM})[\s,]+({_NUM})[\s,]+({_NUM})(\s*[,/]\s*{_NUM})?\s*\)$")
_OKLCH = re.compile(rf"^oklch\(\s*({_NUM})\s+({_NUM})\s+({_NUM})(\s*/\s*{_NUM})?\s*\)$")
# Text must stay readable on what it sits on (WCAG ratios): body text 4.5, the rest 3.
CONTRAST = (("foreground", "background", 4.5), ("card-foreground", "card", 4.5),
            ("sidebar-foreground", "sidebar", 4.5), ("primary-foreground", "primary", 3.0),
            ("muted-foreground", "background", 3.0), ("secondary-foreground", "secondary", 3.0),
            ("accent-foreground", "accent", 3.0))


def _channel(v: str, scale: float) -> float:
    return float(v[:-1]) / 100 * scale if v.endswith("%") else float(v)


def color_rgb(value: str) -> tuple[float, float, float] | None:
    """A token's colour as sRGB 0–1, or None when it isn't a colour the app accepts."""
    import math

    v = value.strip()
    if m := _HEX.match(v):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    if m := _RGB.match(v):
        return tuple(min(1.0, max(0.0, _channel(m.group(i), 255) / 255)) for i in (1, 3, 5))  # type: ignore[return-value]
    if m := _OKLCH.match(v):
        lightness, chroma, hue = _channel(m.group(1), 1), _channel(m.group(3), 0.4), float(m.group(5).rstrip("%"))
        a, b = chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))
        lg = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
        mg = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
        sg = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
        lin = (4.0767416621 * lg - 3.3077115913 * mg + 0.2309699292 * sg,
               -1.2684380046 * lg + 2.6097574011 * mg - 0.3413193965 * sg,
               -0.0041960863 * lg - 0.7034186147 * mg + 1.7076147010 * sg)
        return tuple(min(1.0, max(0.0, c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055))
                     for c in (min(1.0, max(0.0, x)) for x in lin))  # type: ignore[return-value]
    return None


def _luminance(value: str) -> float | None:
    rgb = color_rgb(value)
    if rgb is None:
        return None
    lin = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float | None:
    la, lb = _luminance(a), _luminance(b)
    if la is None or lb is None:
        return None
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def theme_problems(t: dict, package: bool = False) -> list[str]:
    """What's wrong with a theme (theme.json, or a theme package's manifest.json); [] when fine.
    A package's id is '<developer>.<theme>'."""
    p: list[str] = []
    if not isinstance(t, dict):
        return ["a theme must be a JSON object"]
    tid = t.get("id")
    if not isinstance(tid, str) or not THEME_ID.match(tid):
        p.append("id must be lower-case letters, digits and _, e.g. acme.sunrise")
    elif package and not MODULE_ID.match(tid):
        p.append("a theme package's id is '<developer>.<theme>', e.g. acme.sunrise")
    for k in ("name", "name_en"):
        if not _text(t.get(k)):
            p.append(f"{k} is required (1–128 characters)")
    if not isinstance(t.get("version"), str) or not VERSION.match(t["version"]):
        p.append("version must be MAJOR.MINOR.PATCH, e.g. 1.0.0")
    if t.get("kind") != "theme":
        p.append("kind must be 'theme'")
    known = {"id", "name", "name_en", "version", "kind", "description", "colors", "fonts", "radius", "shadows",
             "motion", "density", "preview"}
    for k in sorted(set(t) - known):
        p.append(f"'{k}' isn't a theme field")
    colors = t.get("colors")
    if not isinstance(colors, dict) or set(colors) != {"light", "dark"}:
        p.append("colors must have 'light' and 'dark'")
        colors = {}
    for mode, tokens in colors.items():
        if not isinstance(tokens, dict):
            p.append(f"colors.{mode} must be an object")
            continue
        for k in THEME_REQUIRED:
            if k not in tokens:
                p.append(f"colors.{mode}: '{k}' is required")
        for k, v in tokens.items():
            if k not in THEME_TOKENS:
                p.append(f"colors.{mode}: unknown token '{k}'")
            elif not isinstance(v, str) or color_rgb(v) is None:
                p.append(f"colors.{mode}.{k}: use #hex, rgb() or oklch()")
        for fg, bg, minimum in CONTRAST:
            if fg in tokens and bg in tokens:
                ratio = contrast(str(tokens[fg]), str(tokens[bg]))
                if ratio is not None and ratio < minimum:
                    p.append(f"colors.{mode}: {fg} on {bg} has contrast {ratio:.1f}, needs {minimum}")
    fonts = t.get("fonts", {})
    if not isinstance(fonts, dict):
        p.append("fonts must be an object")
        fonts = {}
    for k, v in fonts.items():
        if k in ("body", "display", "mono"):
            if not isinstance(v, str) or not FONT_FAMILY.match(v):
                p.append(f"fonts.{k}: a font family name (letters, digits, spaces)")
        elif k == "files":
            # [{"family": "Sunrise Sans", "src": "assets/sunrise.woff2", "weight": "400", "style": "normal"}]
            if not isinstance(v, list) or len(v) > 12:
                p.append("fonts.files: a list of up to 12 font files")
                continue
            for f in v:
                if not (isinstance(f, dict) and set(f) <= {"family", "src", "weight", "style"}
                        and isinstance(f.get("family"), str) and FONT_FAMILY.match(f["family"])
                        and isinstance(f.get("src"), str) and FONT_FILE.match(f["src"])
                        and FONT_WEIGHT.match(str(f.get("weight", "400"))) and f.get("style", "normal") in ("normal", "italic")):
                    p.append("fonts.files: each is {family, src: assets/….woff2, weight: 400 or 100 900, style}")
        else:
            p.append(f"fonts.{k} isn't known (body, display, mono, files)")
    if "radius" in t and not (isinstance(t["radius"], str) and RADIUS.match(t["radius"])):
        p.append("radius: e.g. 0.75rem or 8px")
    for key, allowed in (("shadows", THEME_SHADOWS), ("motion", THEME_MOTION), ("density", THEME_DENSITY)):
        if key in t and t[key] not in allowed:
            p.append(f"{key} must be one of {', '.join(allowed)}")
    return p
