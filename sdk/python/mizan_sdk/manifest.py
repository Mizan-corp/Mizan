"""What outside developers ship, checked the same way by the platform and the `mizan` CLI:
community module manifests and entities (ADR-007), theme packs and activity packages (ADR-010),
and site page trees (ADR-015 S2, experimental and not wired into public routes).
Standard library only, so mizan-sdk ships this file as is (a test keeps the copy identical).

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
# A theme may also borrow a font another theme ships, by its public absolute path
# (mirrors the client's SAFE_ABS_SRC in shared/frontend/src/lib/theme.ts).
FONT_FILE_ABS = re.compile(r"^/themes/assets/files/[a-z][a-z0-9_]{0,47}/assets/[A-Za-z0-9_.-]+\.(woff2|woff|ttf|otf)$")
FONT_FILE_REGISTRY = re.compile(r"^/themes/assets/fonts/[a-z][a-z0-9_-]{0,47}/[A-Za-z0-9_.-]+\.(woff2|woff|ttf|otf)$")
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
    known = {"id", "name", "name_en", "version", "kind", "description", "colors", "palette", "fonts", "radius",
             "shadows", "motion", "density", "preview"}
    for k in sorted(set(t) - known):
        p.append(f"'{k}' isn't a theme field")
    palette = t.get("palette")
    if palette is not None:
        if package:
            p.append("a theme package embeds its colors; palette references are platform-side only")
        elif not (isinstance(palette, str) and THEME_ID.match(palette)):
            p.append("palette must be a palette id (lower-case letters, digits and _)")
    colors = t.get("colors")
    if colors is None and not package and isinstance(palette, str) and THEME_ID.match(palette):
        colors = None  # composed by reference; the palette registry supplies the tokens
    elif not isinstance(colors, dict) or set(colors) != {"light", "dark"}:
        p.append("colors must have 'light' and 'dark'")
        colors = {}
    for mode, tokens in (colors or {}).items():
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
        if k in ("body", "display", "mono", "body_arabic", "display_arabic"):
            if not isinstance(v, str) or not FONT_FAMILY.match(v):
                p.append(f"fonts.{k}: a font family name (letters, digits, spaces)")
        elif k == "files":
            # [{"family": "Sunrise Sans", "src": "assets/sunrise.woff2", "weight": "400", "style": "normal"}]
            if not isinstance(v, list) or len(v) > 12:
                p.append("fonts.files: a list of up to 12 font files")
                continue
            for f in v:
                is_ref = (isinstance(f, dict) and set(f) == {"ref"}
                          and isinstance(f.get("ref"), str) and THEME_ID.match(f["ref"]))
                if is_ref and not package:
                    continue  # platform theme composing a registry family by reference
                if is_ref and package:
                    p.append("fonts.files: a theme package embeds its files; registry refs are platform-side only")
                    continue
                if not (isinstance(f, dict) and set(f) <= {"family", "src", "weight", "style"}
                        and isinstance(f.get("family"), str) and FONT_FAMILY.match(f["family"])
                        and isinstance(f.get("src"), str) and (FONT_FILE.match(f["src"]) or FONT_FILE_ABS.match(f["src"])
                                                               or FONT_FILE_REGISTRY.match(f["src"]))
                        and FONT_WEIGHT.match(str(f.get("weight", "400"))) and f.get("style", "normal") in ("normal", "italic")):
                    p.append("fonts.files: each is {family, src: assets/….woff2, weight: 400 or 100 900, style}")
        else:
            p.append(f"fonts.{k} isn't known (body, display, mono, body_arabic, display_arabic, files)")
    if "radius" in t and not (isinstance(t["radius"], str) and RADIUS.match(t["radius"])):
        p.append("radius: e.g. 0.75rem or 8px")
    for key, allowed in (("shadows", THEME_SHADOWS), ("motion", THEME_MOTION), ("density", THEME_DENSITY)):
        if key in t and t[key] not in allowed:
            p.append(f"{key} must be one of {', '.join(allowed)}")
    return p


# ── Activity packages (ADR-010 D2) ───────────────────────────────────────────────
# A whole business activity, in the layout of activities/<activity>/, declarative: its definition
# (manifest.json, kind "activity"), its own community modules (modules/<id>/), how it adapts
# Mizan's modules (variants/<module>/variant.json: fields, terms, settings), its themes
# (themes/<theme>/theme.json) and demo records (seed/*.json). `known` (the platform's catalogue:
# {"modules": {...}, "screens": {...}, "widgets": {...}, "records": {...}, "themes": {...}})
# checks references to Mizan's own parts; the CLI checks without it.

FAMILIES = ("general", "commerce", "food_hospitality", "health", "education", "services", "logistics", "industry",
            "projects", "institutions")
ACTIVITY_KEYS = {"id", "name", "name_en", "version", "kind", "family", "description", "icon", "modules", "optional",
                 "terms", "home", "theme", "branding", "settings", "positions", "menu", "dashboard", "roles"}
VARIANT_KEYS = {"module", "description", "fields", "terms", "settings"}
VARIANT_FIELD_TYPES = ("text", "number", "date", "boolean", "select")
ROLE_CODE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
BUILT_IN_SCREEN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")  # pos.pos
OWN_SCREEN = re.compile(r"^([a-z][a-z0-9_]{1,31}\.[a-z][a-z0-9_]{1,47})/([a-z][a-z0-9_]{0,47})$")  # acme.orders/order
ACTIVITY_FILE = re.compile(
    r"^(manifest\.json|README\.md|CHANGELOG\.md"
    r"|modules/[a-z][a-z0-9_]{1,31}\.[a-z][a-z0-9_]{1,47}/(manifest\.json|README\.md|entities/[a-z][a-z0-9_]{0,47}\.json)"
    r"|variants/[a-z][a-z0-9_]*/variant\.json"
    r"|themes/[a-z][a-z0-9_]{0,47}/(theme\.json|assets/[A-Za-z0-9_.-]+\.(woff2|woff|ttf|otf|png|svg|webp|jpg))"
    r"|seed/[a-z][a-z0-9_]{0,47}\.json|i18n/[a-z]{2}\.json|assets/[A-Za-z0-9_.-]+\.(png|svg|webp|jpg))$")


def _menu_problems(where: str, menu, screen_ok) -> list[str]:
    p: list[str] = []
    if not isinstance(menu, list):
        return [f"{where} must be a list of groups"]
    for g in menu:
        if not isinstance(g, dict) or not KEY.match(str(g.get("id", ""))) or not _text(g.get("label"), 64):
            p.append(f"{where}: each group needs an id and a label")
            continue
        for item in g.get("items") or []:
            screen = item.get("screen") if isinstance(item, dict) else None
            if not isinstance(screen, str) or not screen_ok(screen):
                p.append(f"{where}: unknown screen {screen!r}")
    return p


def activity_package_problems(files: dict[str, bytes], known: dict | None = None) -> list[str]:
    """What's wrong with an activity package's files ({path: bytes}); [] when it's fine."""
    import json as _json

    p: list[str] = []
    for name in files:
        if not ACTIVITY_FILE.match(name):
            p.append(f"An activity package can't contain {name}")

    def load(name: str):
        try:
            return _json.loads(files[name])
        except (ValueError, KeyError) as e:
            p.append(f"{name}: invalid JSON ({e})")
            return None

    m = load("manifest.json") if "manifest.json" in files else None
    if not isinstance(m, dict):
        return p + ["manifest.json must be an activity's definition"]
    aid = m.get("id")
    if not isinstance(aid, str) or not MODULE_ID.match(aid):
        p.append("id must be '<developer>.<activity>' in lower case, e.g. acme.laundry")
        aid = "x.x"
    dev = aid.split(".")[0]
    for k in ("name", "name_en"):
        if not _text(m.get(k)):
            p.append(f"{k} is required (1–128 characters)")
    if not isinstance(m.get("version"), str) or not VERSION.match(m["version"]):
        p.append("version must be MAJOR.MINOR.PATCH, e.g. 1.0.0")
    if m.get("kind") != "activity":
        p.append("kind must be 'activity'")
    if m.get("family") not in FAMILIES:
        p.append(f"family must be one of {', '.join(FAMILIES)}")
    for k in sorted(set(m) - ACTIVITY_KEYS):
        p.append(f"'{k}' isn't an activity field")

    # Its own modules: community modules under modules/<id>/.
    own: dict[str, dict] = {}
    for mid in sorted({n.split("/")[1] for n in files if n.startswith("modules/")}):
        manifest = load(f"modules/{mid}/manifest.json") if f"modules/{mid}/manifest.json" in files else None
        if manifest is None:
            p.append(f"modules/{mid}/manifest.json is missing")
            continue
        entities = {n.rsplit("/", 1)[1][:-5]: load(n) for n in files if n.startswith(f"modules/{mid}/entities/")}
        p += [f"modules/{mid}: {x}" for x in community_manifest_problems(manifest, set(entities))]
        scopes = set(manifest.get("scopes") or []) if isinstance(manifest, dict) else set()
        for name, e in entities.items():
            p += [f"modules/{mid}: {x}" for x in entity_problems(e, set(entities), scopes)]
        if isinstance(manifest, dict) and manifest.get("id") != mid:
            p.append(f"modules/{mid}/manifest.json has id {manifest.get('id')!r}")
        if not mid.startswith(dev + "."):
            p.append(f"modules/{mid}: an activity's modules are named {dev}.…")
        own[mid] = {"entities": {k: v for k, v in entities.items() if isinstance(v, dict)}}

    builtin = (known or {}).get("modules")

    def module_ok(mid) -> bool:
        return mid in own or (builtin is None and isinstance(mid, str) and bool(KEY.match(mid))) or (builtin is not None and mid in builtin)

    for key in ("modules", "optional"):
        ids = m.get(key, [] if key == "optional" else None)
        if not isinstance(ids, list) or (key == "modules" and not ids):
            p.append(f"{key} must be a list of module ids" + (" (at least one)" if key == "modules" else ""))
            continue
        for mid in ids:
            if not module_ok(mid):
                p.append(f"{key}: unknown module {mid!r}")
    for mid in own:
        if mid not in (m.get("modules") or []) + (m.get("optional") or []):
            p.append(f"modules/{mid} isn't listed in 'modules' or 'optional'")

    screens = (known or {}).get("screens")

    def screen_ok(ref: str) -> bool:
        if (own_ref := OWN_SCREEN.match(ref)):
            return own_ref.group(2) in own.get(own_ref.group(1), {}).get("entities", {})
        return bool(BUILT_IN_SCREEN.match(ref)) and (screens is None or ref in screens)

    widgets = (known or {}).get("widgets")
    for where, block in [("", m), *[(f"roles.{code}.", r) for code, r in (m.get("roles") or {}).items()
                                    if isinstance(r, dict)]]:
        if "menu" in block:
            p += _menu_problems(f"{where}menu", block["menu"], screen_ok)
        for w in block.get("dashboard") or []:
            wid = w if isinstance(w, str) else (w.get("id") if isinstance(w, dict) else None)
            if not isinstance(wid, str) or (widgets is not None and wid not in widgets):
                p.append(f"{where}dashboard: unknown widget {wid!r}")
        home = block.get("home")
        if home is not None and not (isinstance(home, str) and (home.startswith("/") or screen_ok(home))):
            p.append(f"{where}home must be a path (/pos) or a screen")
    roles = m.get("roles", {})
    if not isinstance(roles, dict) or not all(ROLE_CODE.match(str(c)) and isinstance(r, dict) for c, r in roles.items()):
        p.append("roles: {role code: {home, menu, dashboard}}")
    terms = m.get("terms", {})
    if not isinstance(terms, dict) or not all(KEY.match(str(k)) and _text(v, 64) for k, v in terms.items()):
        p.append("terms: {word: its name in this activity}, e.g. {\"item\": \"قطعة\"}")
    if not isinstance(m.get("settings", {}), dict):
        p.append("settings must be an object of '<module>.<setting>' defaults")
    for pos in m.get("positions", []) if isinstance(m.get("positions", []), list) else [None]:
        if not (isinstance(pos, dict) and ROLE_CODE.match(str(pos.get("code", ""))) and _text(pos.get("name"))
                and _text(pos.get("name_en"))):
            p.append("positions: each is {code, name, name_en, suggested_roles}")

    # How it adapts Mizan's modules: variants/<module>/variant.json (no code yet).
    records = (known or {}).get("records")
    for name in sorted(n for n in files if n.startswith("variants/")):
        module = name.split("/")[1]
        v = load(name)
        if not isinstance(v, dict):
            continue
        if module in own or not module_ok(module):
            p.append(f"{name}: a variant adapts one of Mizan's modules the activity uses")
        if v.get("module", module) != module:
            p.append(f"{name}: module must be {module!r}")
        for k in sorted(set(v) - VARIANT_KEYS):
            p.append(f"{name}: '{k}' isn't allowed (a package's variant has fields, terms and settings)")
        for record, fields in (v.get("fields") or {}).items() if isinstance(v.get("fields") or {}, dict) else []:
            if records is not None and record not in records.get(module, set()):
                p.append(f"{name}: {module} has no record {record!r} to add fields to")
            for f in fields if isinstance(fields, list) else [None]:
                ok = (isinstance(f, dict) and KEY.match(str(f.get("key", ""))) and _text(f.get("label"))
                      and f.get("type", "text") in VARIANT_FIELD_TYPES
                      and (f.get("type") != "select" or (isinstance(f.get("options"), list) and f["options"])))
                if not ok:
                    p.append(f"{name}: fields.{record}: each is {{key, label, type ({', '.join(VARIANT_FIELD_TYPES)})}}")

    # Its themes.
    own_themes = set()
    for tname in sorted({n.split("/")[1] for n in files if n.startswith("themes/")}):
        t = load(f"themes/{tname}/theme.json") if f"themes/{tname}/theme.json" in files else None
        if not isinstance(t, dict):
            p.append(f"themes/{tname}/theme.json is missing")
            continue
        p += [f"themes/{tname}: {x}" for x in theme_problems(t, package=True)]
        if not str(t.get("id", "")).startswith(dev + "."):
            p.append(f"themes/{tname}: an activity's themes are named {dev}.…")
        for f in (t.get("fonts") or {}).get("files") or []:
            if isinstance(f, dict) and f"themes/{tname}/{f.get('src')}" not in files:
                p.append(f"themes/{tname}: {f.get('src')} isn't in the package")
        own_themes.add(t.get("id"))
    theme = m.get("theme")
    mizan_themes = (known or {}).get("themes")
    if theme is not None and theme not in own_themes and (mizan_themes is None or theme not in mizan_themes):
        if mizan_themes is not None or not (isinstance(theme, str) and THEME_ID.match(theme)):
            p.append(f"theme: {theme!r} is neither one of its themes nor Mizan's")

    # Demo records for its own entities.
    for name in sorted(n for n in files if n.startswith("seed/")):
        s = load(name)
        if not isinstance(s, dict) or not isinstance(s.get("records"), list) or len(s["records"]) > 500:
            p.append(f"{name}: {{module, entity, records: [up to 500]}}")
            continue
        entity = own.get(s.get("module"), {}).get("entities", {}).get(s.get("entity"))
        if entity is None:
            p.append(f"{name}: {s.get('module')}/{s.get('entity')} isn't one of its entities")
            continue
        keys = {f.get("key") for f in entity.get("fields") or [] if isinstance(f, dict)}
        for r in s["records"]:
            if not isinstance(r, dict) or set(r) - keys:
                p.append(f"{name}: records may only use {s['entity']}'s fields")
                break
    return p


# --- Site page trees (ADR-015 step S2, docs/builder/page-engine.md) -------------------------------
#
# A page is a JSON tree of nodes {"id", "type", "settings", "content", "children"}: the root is a
# section, sections hold columns containers or one canvas, columns hold column, and columns/canvas
# hold the basic blocks. This registry is data, versioned, and shared with the SDK byte for byte
# (this file is that copy), so the studio, the API and `mizan site-theme` all validate the same way.

PAGE_DEVICES = ("desktop", "tablet", "mobile")
PAGE_SPACING = ("none", "xs", "s", "m", "l", "xl")
PAGE_NODE_ID = re.compile(r"^n_[a-z0-9]{4,16}$")
PAGE_LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")  # ar, en, en-US
PAGE_MAX_NODES = 500
PAGE_MAX_DEPTH = 12
# The only hosts a video_embed may frame (ADR-015 D2); the html block may not frame anything.
PAGE_EMBED_HOSTS = ("www.youtube.com", "www.youtube-nocookie.com", "maps.google.com", "www.google.com")

# Bounded inline icon set names for icon blocks and icon_list items: the renderers carry the
# matching inline SVG markup (no icon font, no network fetch); mirrored in
# shared/backend/app/platform/site/render.py (_ICON_MARKUP) and nativeIcons.tsx (ICON_MARKUP).
PAGE_ICONS = ("Wrench", "Laptop", "Smartphone", "ShieldCheck", "Truck", "Check", "Star", "Headphones",
              "Cpu", "BatteryCharging", "Camera", "Home", "Mail", "MapPin", "ArrowRight", "Sparkles",
              "Clock", "CreditCard", "Package", "Heart", "ShoppingBag", "BookOpen", "Stethoscope",
              "HardDriveDownload", "MemoryStick", "MonitorCog", "Network", "Globe", "Building2",
              "MessageCircle", "Banknote")


def _choices(*values):
    return ("choice", values)


def _count(lo: int, hi: int):
    return ("count", lo, hi)


# Each block declares: version, category, which children it holds, a settings schema (validated
# per device) and a translatable content schema. Settings kinds: "bool", "string", "url",
# ("choice", …), ("count", lo, hi). Content kinds: ("text", limit), "url", "href", "embed",
# "images", "icons".
PAGE_BLOCKS = {
    "section": {"version": 1, "category": "layout", "children": ("columns", "canvas"),
                "settings": {"visible": "bool", "padding": _choices(*PAGE_SPACING), "gap": _choices(*PAGE_SPACING),
                             "background": _choices("background", "card", "primary", "dark", "dark_raised"), "max_width": _choices("narrow", "normal", "wide", "full"),
                             "background_image": "url", "background_dim": _choices("none", "soft", "strong")},
                "content": {}},
    "columns": {"version": 1, "category": "layout", "children": ("column",),
                "settings": {"visible": "bool", "columns": _count(1, 6), "gap": _choices(*PAGE_SPACING),
                             "stack": "bool", "reverse": "bool", "bleed": "bool",
                             "background": _choices("background", "card", "primary", "dark", "dark_raised")},
                "content": {}},
    "column": {"version": 1, "category": "layout", "children": "blocks",
               "settings": {"visible": "bool", "width": _choices("auto", "full", "half", "third", "two_thirds"), "padding": _choices(*PAGE_SPACING),
                            "align": _choices("start", "center", "end"), "background": _choices("background", "card", "primary", "dark", "dark_raised"), "rounded": "bool",
                            "min_height": _choices("s", "m", "l"),
                            "background_image": "url", "background_dim": _choices("none", "soft", "strong"),
                            "background_fit": _choices("cover", "end_band")},
               "content": {}},
    "canvas": {"version": 1, "category": "layout", "children": "blocks", "per_page": 1,
               "settings": {"visible": "bool", "min_height": _choices("s", "m", "l")},
               "content": {}},
    "heading": {"version": 1, "category": "basic",
                "settings": {"visible": "bool", "level": _count(1, 6), "align": _choices("start", "center", "end"),
                             "size": _choices("auto", "s", "m", "l"), "wrap": _choices("normal", "balance")},
                "content": {"text": ("text", 200)}},
    "text": {"version": 1, "category": "basic",
             "settings": {"visible": "bool", "align": _choices("start", "center", "end"),
                          "variant": _choices("body", "eyebrow", "note", "check_list")},
             "content": {"html": ("text", 20000)}},
    "image": {"version": 1, "category": "basic",
              "settings": {"visible": "bool", "width": _choices("auto", "full", "half", "third", "two_thirds"), "rounded": "bool",
                       "art": _choices("none", "sculpture", "sculpture_alt")},
              "content": {"src": "url", "alt": ("text", 300)}},
    "gallery": {"version": 1, "category": "basic",
                "settings": {"visible": "bool", "mode": _choices("grid", "slider"), "gap": _choices(*PAGE_SPACING)},
                "content": {"images": "images"}},
    "video_embed": {"version": 1, "category": "basic",
                    "settings": {"visible": "bool", "aspect": _choices("16:9", "4:3", "1:1")},
                    "content": {"url": "embed"}},
    "button": {"version": 1, "category": "basic",
               "settings": {"visible": "bool", "style": _choices("primary", "secondary", "ghost", "soft"),
                            "align": _choices("start", "center", "end")},
               "content": {"label": ("text", 80), "href": "href"}},
    "icon_list": {"version": 1, "category": "basic",
                  "settings": {"visible": "bool", "gap": _choices(*PAGE_SPACING)},
                  "content": {"items": "icons"}},
    "icon": {"version": 1, "category": "basic",
             "settings": {"visible": "bool", "icon": _choices(*PAGE_ICONS), "size": _choices("s", "m", "l"),
                          "tone": _choices("none", "primary", "dark", "card"),
                          "align": _choices("start", "center", "end")},
             "content": {}},
    "spacer": {"version": 1, "category": "basic",
               "settings": {"visible": "bool", "height": _choices(*PAGE_SPACING)},
               "content": {}},
    "divider": {"version": 1, "category": "basic",
                "settings": {"visible": "bool", "style": _choices("solid", "dashed", "dotted")},
                "content": {}},
    "html": {"version": 1, "category": "advanced",
             "settings": {"visible": "bool"},
             "content": {"html": ("text", 50000)}},
}


# Shared motion contract: finite entrance effects only, no script/CSS payloads.
PAGE_ANIMATIONS = ("none", "fade", "rise", "slide", "zoom")
for _motion_block in PAGE_BLOCKS.values():
    _motion_block["settings"].update({
        "animation": _choices(*PAGE_ANIMATIONS),
        "animation_speed": _choices("quick", "normal", "slow"),
        "animation_delay": _choices("none", "short", "long"),
    })


def page_url(value, kind: str = "href") -> bool:
    """Constrained URLs: no protocol-relative paths, backslashes, controls or credentials.
    Embeds use HTTPS, default ports and provider-specific embed paths only."""
    from urllib.parse import urlsplit

    if not isinstance(value, str) or not 0 < len(value) <= 2000:
        return False
    if any(ord(c) < 33 or ord(c) == 127 for c in value) or "\\" in value:
        return False
    if any(c in value for c in '<>"\''):
        return False
    if value.startswith("/"):
        return kind != "embed" and not value.startswith("//")
    if value.startswith("#"):
        return kind == "href"
    try:
        u = urlsplit(value)
        if kind == "href" and u.scheme in ("mailto", "tel"):
            return bool(u.path) and not u.netloc
        if u.scheme not in (("https",) if kind == "embed" else ("http", "https")):
            return False
        if not u.hostname or u.username is not None or u.password is not None:
            return False
        if u.port not in (None, 443 if u.scheme == "https" else 80):
            return False
        host = u.hostname.lower()
    except ValueError:
        return False
    if kind != "embed":
        return True
    return ((host in ("www.youtube.com", "www.youtube-nocookie.com") and u.path.startswith("/embed/"))
            or (host in ("www.google.com", "maps.google.com") and u.path.startswith("/maps/embed")))


def _page_value_problems(where: str, kind, value) -> list[str]:
    """One content value against its schema kind."""
    if isinstance(kind, tuple) and kind[0] == "text":
        if not isinstance(value, str) or len(value) > kind[1]:
            return [f"{where} must be text of at most {kind[1]} characters"]
        return []
    if kind in ("url", "href", "embed"):
        if page_url(value, kind):
            return []
        return [f"{where} must be a permitted {kind} link; embed hosts and paths are allow-listed"]
    if kind in ("images", "icons"):
        if not isinstance(value, list) or len(value) > 24:
            return [f"{where} must be a list of at most 24 entries"]
        problems = []
        for i, entry in enumerate(value):
            if not isinstance(entry, dict):
                problems.append(f"{where}[{i}] must be an object")
                continue
            if kind == "images":
                problems += _page_value_problems(f"{where}[{i}].src", "url", entry.get("src"))
                problems += _page_value_problems(f"{where}[{i}].alt", ("text", 300), entry.get("alt", ""))
            else:
                if not (isinstance(entry.get("icon"), str) and ICON.match(entry["icon"])):
                    problems.append(f"{where}[{i}].icon must be a lucide icon name, e.g. CalendarCheck")
                problems += _page_value_problems(f"{where}[{i}].text", ("text", 120), entry.get("text", ""))
            if set(entry) - ({"src", "alt"} if kind == "images" else {"icon", "text"}):
                problems.append(f"{where}[{i}] has fields it shouldn't")
        return problems
    return [f"{where} has a kind this validator doesn't know"]  # a registry bug, not user data


def _page_setting_problems(where: str, kind, value) -> list[str]:
    if kind == "bool":
        return [] if isinstance(value, bool) else [f"{where} must be true or false"]
    if kind == "string":
        return [] if isinstance(value, str) and len(value) <= 200 else [f"{where} must be text of at most 200 characters"]
    if kind == "url":
        # An empty string clears the setting (the UI cannot unset keys otherwise).
        if value == "":
            return []
        # Setting URLs may land inside a style attribute (background_image), so on top of
        # page_url's rules they never carry CSS-significant characters.
        ok = page_url(value, "url") and not any(ch in value for ch in "();")
        return [] if ok else [f"{where} must be a permitted link"]
    if isinstance(kind, tuple) and kind[0] == "choice":
        return [] if value in kind[1] else [f"{where} must be one of: {', '.join(map(str, kind[1]))}"]
    if isinstance(kind, tuple) and kind[0] == "count":
        ok = isinstance(value, int) and not isinstance(value, bool) and kind[1] <= value <= kind[2]
        return [] if ok else [f"{where} must be a whole number between {kind[1]} and {kind[2]}"]
    return [f"{where} has a kind this validator doesn't know"]  # a registry bug, not user data


PAGE_BINDINGS_SCHEMA = "mizan.page-bindings.experimental.v0"
PAGE_BINDINGS_ITEM_SCHEMA = "mizan.page-bindings.experimental.v1"
# Individually bound elements (v1 envelope): which content field each node type
# may bind, and which provider fields may fill it. Shape only; consent and
# record scope are runtime checks (docs/studio-consent-scope-v2.md).
_BINDING_ITEM_TARGETS = {
    "heading": ("text", frozenset({"name"})),
    "text": ("html", frozenset({"name", "price"})),
    "image": ("src", frozenset({"image"})),
}


def _page_binding_item_problems(value, node_type, languages) -> list[str]:
    content = value.get("content")
    if not isinstance(content, dict) or not content or len(content) > 2:
        return ["bindings: bounded nonempty language map required"]
    errors = []
    target = _BINDING_ITEM_TARGETS.get(node_type) if isinstance(node_type, str) else None
    for language, fields in content.items():
        if not isinstance(language, str) or language not in ("en", "ar") or (languages is not None and language not in languages):
            errors.append("bindings: unsupported language")
        if target is None or not isinstance(fields, dict) or set(fields) != {target[0]}:
            errors.append("bindings: unsupported element binding target")
            continue
        b = fields[target[0]]
        required = {"mode", "module", "source", "item_key", "field", "on_missing"}
        if not isinstance(b, dict) or set(b) != required:
            errors.append("bindings: exact declarative item reference required")
            continue
        if b.get("mode") != "dynamic" or b.get("on_missing") not in ("hide", "empty"):
            errors.append("bindings: explicit dynamic mode and missing behavior required")
        for key in ("module", "source", "field"):
            v = b.get(key)
            pattern = r"[a-z][a-z0-9_]{0,47}(?:\.[a-z][a-z0-9_]{0,47})?" if key == "module" else r"[a-z][a-z0-9_]{0,47}"
            if not isinstance(v, str) or re.fullmatch(pattern, v) is None:
                errors.append("bindings: invalid source identifier")
        if b.get("field") not in target[1]:
            errors.append("bindings: field not bindable to this element")
        key = b.get("item_key")
        if not isinstance(key, str) or not 1 <= len(key) <= 64 or re.fullmatch(r"[A-Za-z0-9_-]+", key) is None:
            errors.append("bindings: invalid record identity")
    return errors



def page_binding_problems(value, node_type, languages=None) -> list[str]:
    """Shape only. Provider existence, activation and access require runtime checks.

    This explicit experimental extension never embeds executable expressions or values.
    Unknown schemas, targets and fields fail closed. Static content remains independently
    validated and is retained when a binding is removed.
    """
    if not isinstance(value, dict) or set(value) != {"schema", "content"}:
        return ["bindings: schema and content are required, no extra fields"]
    if value.get("schema") == PAGE_BINDINGS_ITEM_SCHEMA:
        return _page_binding_item_problems(value, node_type, languages)
    if value.get("schema") != PAGE_BINDINGS_SCHEMA:
        return ["bindings: unsupported experimental schema"]
    content=value.get("content")
    if not isinstance(content, dict) or not content or len(content)>2:
        return ["bindings: bounded nonempty language map required"]
    errors=[]
    for language, fields in content.items():
        if not isinstance(language,str) or language not in ("en", "ar") or (languages is not None and language not in languages):
            errors.append("bindings: unsupported language")
        if not isinstance(node_type,str) or node_type != "heading" or not isinstance(fields,dict) or set(fields)!={"text"}:
            errors.append("bindings: only heading.text supported")
            continue
        b=fields["text"]
        required={"mode","module","source","field","on_missing"}
        if not isinstance(b,dict) or set(b)!=required:
            errors.append("bindings: exact declarative reference required")
            continue
        if b.get("mode")!="dynamic" or b.get("on_missing") not in ("hide","empty"):
            errors.append("bindings: explicit dynamic mode and missing behavior required")
        for key in ("module","source","field"):
            v=b.get(key)
            pattern=r"[a-z][a-z0-9_]{0,47}(?:\.[a-z][a-z0-9_]{0,47})?" if key=="module" else r"[a-z][a-z0-9_]{0,47}"
            if not isinstance(v,str) or re.fullmatch(pattern,v) is None:
                errors.append("bindings: invalid source identifier")
    return errors


PAGE_REPEAT_SCHEMA = "mizan.page-repeat.experimental.v0"
PAGE_REPEAT_CARD_SCHEMA = "mizan.page-repeat.experimental.v1"
_REPEAT_CARD_SLOT_TYPES = {"heading": ("text",), "text": ("text", "money"), "image": ("media",)}


def page_repeat_problems(value, node_type, languages=None) -> list[str]:
    """Shape only; provider compatibility and native expansion require runtime checks."""
    if not isinstance(value, dict):
        return ["repeat: exact versioned language declaration required"]
    if value.get("schema") == PAGE_REPEAT_CARD_SCHEMA:
        return _page_repeat_card_problems(value, node_type, languages)
    if set(value) != {"schema", "content"}:
        return ["repeat: exact versioned language declaration required"]
    if value.get("schema") != PAGE_REPEAT_SCHEMA or node_type != "heading":
        return ["repeat: only experimental heading templates supported"]
    content = value.get("content")
    if not isinstance(content, dict) or not content or len(content) > 2:
        return ["repeat: bounded nonempty language map required"]
    errors = []
    for lang, plan in content.items():
        if lang not in ("en", "ar") or (languages is not None and lang not in languages):
            errors.append("repeat: unsupported language")
        if not isinstance(plan, dict) or set(plan) != {"module", "source", "field", "limit", "on_missing"}:
            errors.append("repeat: exact collection reference required")
            continue
        for name in ("module", "source", "field"):
            if not isinstance(plan[name], str) or re.fullmatch(r"[a-z][a-z0-9_]{0,47}", plan[name]) is None:
                errors.append("repeat: invalid identifier")
        if type(plan["limit"]) is not int or not 1 <= plan["limit"] <= 24 or plan["on_missing"] not in ("hide", "empty"):
            errors.append("repeat: explicit bounded limit and missing behavior required")
    return errors


def _page_repeat_card_problems(value, node_type, languages=None) -> list[str]:
    """v1 bounded card template: a column of heading/text/image slots filled
    from one collection item each. Slots are structural (shared across
    languages); only the source reference varies per language."""
    if set(value) != {"schema", "slots", "content"} or node_type != "column":
        return ["repeat: only experimental column card templates supported"]
    slots = value.get("slots")
    if not isinstance(slots, dict) or not slots or "heading" not in slots or not set(slots) <= set(_REPEAT_CARD_SLOT_TYPES):
        return ["repeat: card slots need a heading and only heading/text/image keys"]
    errors = []
    for kind, field in slots.items():
        if not isinstance(field, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,47}", field) is None:
            errors.append("repeat: invalid card slot field identifier")
    content = value.get("content")
    if not isinstance(content, dict) or not content or len(content) > 2:
        return errors + ["repeat: bounded nonempty language map required"]
    for lang, plan in content.items():
        if lang not in ("en", "ar") or (languages is not None and lang not in languages):
            errors.append("repeat: unsupported language")
        if not isinstance(plan, dict) or set(plan) != {"module", "source", "limit", "on_missing"}:
            errors.append("repeat: exact collection reference required")
            continue
        for name in ("module", "source"):
            if not isinstance(plan[name], str) or re.fullmatch(r"[a-z][a-z0-9_]{0,47}", plan[name]) is None:
                errors.append("repeat: invalid identifier")
        if type(plan["limit"]) is not int or not 1 <= plan["limit"] <= 24 or plan["on_missing"] not in ("hide", "empty"):
            errors.append("repeat: explicit bounded limit and missing behavior required")
    return errors


PAGE_CARD_SCHEMA = "mizan.page-card.experimental.v0"

def page_card_problems(value, node_type, languages=None):
    if not isinstance(value, dict) or set(value) != {"schema", "content"} or value.get("schema") != PAGE_CARD_SCHEMA or node_type != "column":
        return ["card: exact native column declaration required"]
    content=value.get("content")
    if not isinstance(content, dict) or not 1 <= len(content) <= 2:
        return ["card: bounded language map required"]
    errors=[]
    for language, plan in content.items():
        if language not in ("en","ar") or (languages is not None and language not in languages):errors.append("card: unsupported language")
        if not isinstance(plan, dict) or set(plan) not in ({"module","source","limit","targets"},{"module","source","limit","targets","products"}):
            errors.append("card: exact source and targets required");continue
        if plan['module'] != 'inventory' or plan['source'] != 'website_cards' or type(plan['limit']) is not int or not 1 <= plan['limit'] <= 6:errors.append("card: unsupported source or bound")
        if 'products' in plan:
            from uuid import UUID
            ids=plan['products']
            try:
                if not isinstance(ids,list) or len(ids)>6 or any(not isinstance(x,str) or str(UUID(x))!=x for x in ids) or len(set(ids))!=len(ids):errors.append('card: exact bounded product subset required')
            except (ValueError,TypeError):errors.append('card: invalid product identity')
        targets=plan['targets']
        if not isinstance(targets,dict) or set(targets) != {'name','price','image'} or any(not isinstance(v,str) or not PAGE_NODE_ID.fullmatch(v) for v in targets.values()) or len(set(v for v in targets.values() if isinstance(v,str))) != 3:errors.append("card: distinct native targets required")
    return errors


def page_problems(tree: dict, languages: tuple[str, ...] | None = None) -> list[str]:
    """What's wrong with a page tree; [] when it's fine. `languages`: the site's language codes;
    content in any other language is rejected. None accepts any well-formed code."""
    if not isinstance(tree, dict):
        return ["the page tree must be a JSON object"]
    if tree.get("type") != "section":
        return ["the root of a page is a section"]
    problems: list[str] = []
    state = {"nodes": 0, "canvas": 0, "ids": set()}

    def walk(node, where: str, depth: int, allowed: tuple[str, ...] | str | None):
        state["nodes"] += 1
        if state["nodes"] > PAGE_MAX_NODES:
            problems.append(f"a page holds at most {PAGE_MAX_NODES} blocks")
            return
        if depth > PAGE_MAX_DEPTH:
            problems.append(f"{where}: blocks nest at most {PAGE_MAX_DEPTH} levels deep")
            return
        if not isinstance(node, dict):
            problems.append(f"{where} must be an object")
            return
        nid = node.get("id")
        ntype = node.get("type")
        label = f"{where} › {ntype} {nid}" if isinstance(ntype, str) else where
        extra = set(node) - {"id", "type", "settings", "content", "children", "bindings", "repeat", "card"}
        for k in sorted(extra):
            problems.append(f"{label}: '{k}' isn't a page node field")
        if not isinstance(nid, str) or not PAGE_NODE_ID.match(nid):
            problems.append(f"{label}: id must look like n_k3j9x2 (n_ plus 4–16 lower-case letters or digits)")
        elif nid in state["ids"]:
            problems.append(f"{label}: this id is already used in the page")
        else:
            state["ids"].add(nid)
        block = PAGE_BLOCKS.get(ntype) if isinstance(ntype, str) else None
        if block is None:
            problems.append(f"{label}: unknown block type")
            return
        if allowed == "blocks":
            if block["category"] == "layout":
                problems.append(f"{label}: a {ntype} block can't sit here")
        elif allowed is None or ntype not in allowed:
            problems.append(f"{label}: a {ntype} block can't sit here")
        if ntype == "canvas":
            state["canvas"] += 1

        settings = node.get("settings", {})
        if not isinstance(settings, dict):
            problems.append(f"{label}: settings must be per device")
            settings = {}
        for device, declared in settings.items():
            if device not in PAGE_DEVICES:
                problems.append(f"{label}: settings.{device} isn't a device ({', '.join(PAGE_DEVICES)})")
                continue
            if not isinstance(declared, dict):
                problems.append(f"{label}: settings.{device} must be an object")
                continue
            for key, value in declared.items():
                kind = block["settings"].get(key)
                if kind is None:
                    problems.append(f"{label}: '{key}' isn't a {ntype} setting")
                else:
                    problems.extend(_page_setting_problems(f"{label} {device}.{key}", kind, value))

        content = node.get("content", {})
        if not isinstance(content, dict):
            problems.append(f"{label}: content must be keyed by language")
            content = {}
        for lang, fields in content.items():
            if not isinstance(lang, str) or not PAGE_LANGUAGE.match(lang):
                problems.append(f"{label}: '{lang}' isn't a language code")
                continue
            if languages is not None and lang not in languages:
                problems.append(f"{label}: the site has no '{lang}' language")
                continue
            if not isinstance(fields, dict):
                problems.append(f"{label}: content.{lang} must be an object")
                continue
            for field, value in fields.items():
                kind = block["content"].get(field)
                if kind is None:
                    problems.append(f"{label}: '{field}' isn't a {ntype} content field")
                else:
                    problems.extend(_page_value_problems(f"{label} {lang}.{field}", kind, value))

        if "bindings" in node:
            problems.extend(f"{label}: {problem}" for problem in page_binding_problems(node["bindings"], ntype, languages))

        if "card" in node:
            problems.extend(f"{label}: {problem}" for problem in page_card_problems(node["card"], ntype, languages))
            if "bindings" in node or "repeat" in node:problems.append(f"{label}: card conflicts with scalar/repeat")
        if "repeat" in node:
            problems.extend(f"{label}: {problem}" for problem in page_repeat_problems(node["repeat"], ntype, languages))
            if "bindings" in node:
                problems.append(f"{label}: mixed repeat and scalar bindings not supported")

        children = node.get("children", [])
        if block["category"] != "layout" and children not in ([], None):
            problems.append(f"{label}: a {ntype} block holds no children")
            return
        if block["category"] == "layout":
            if not isinstance(children, list):
                problems.append(f"{label}: children must be a list")
                return
            if ntype == "columns" and not 1 <= len(children) <= 6:
                problems.append(f"{label}: columns holds 1 to 6 column nodes")
            for child in children[:PAGE_MAX_NODES + 1]:
                walk(child, label, depth + 1, block["children"])

    walk(tree, "page", 1, ("section",))
    if state["canvas"] > 1:
        problems.append("a page holds at most one canvas")
    return problems
