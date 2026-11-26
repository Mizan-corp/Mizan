"""Families and activities as data (ADR-006).

Families (catalog/families.json) only group activities. Activities live in
app/activities/<activity_id>/activity.json. An activity is a business activity a workspace runs (exactly
one per workspace); every activity inherits ``general``. Modules name their home activity in
their manifest (``"activity"``), and take their family from it.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_DIR = Path(__file__).resolve().parent
GENERAL = "general"


def _read(name: str, key: str) -> list[dict[str, Any]]:
    return json.loads((CATALOG_DIR / name).read_text(encoding="utf-8"))[key]


@lru_cache(maxsize=1)
def families() -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in sorted(_read("families.json", "families"), key=lambda f: f["order"])}


ACTIVITIES_DIR = CATALOG_DIR.parent / "activities"


LAYOUT_KEYS = ("home", "menu", "dashboard", "roles", "shell", "shells")


def layout_of(folder: Path) -> dict[str, Any]:
    """An activity's layout as data (migration step 4): `layout.json` next to `activity.json`,
    `{"schema": 1, "home", "menu", "dashboard", "roles"}` (framework/layout_schema.py). Its keys
    take the place of the same keys in activity.json; an activity without the file is unchanged."""
    f = folder / "layout.json"
    if not f.is_file():
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise ValueError(f"{f}: unsupported layout schema {data.get('schema')!r}")
    return {k: data[k] for k in LAYOUT_KEYS if k in data}


@lru_cache(maxsize=1)
def activities() -> dict[str, dict[str, Any]]:
    """Every activity, from app/activities/<activity_id>/activity.json."""
    found = {}
    for f in sorted(ACTIVITIES_DIR.glob("*/activity.json")):
        data = {**json.loads(f.read_text(encoding="utf-8")), **layout_of(f.parent)}
        found[data["id"]] = data
    return dict(sorted(found.items(), key=lambda kv: kv[1].get("order", 999)))


def family_of(activity_id: str) -> str | None:
    activity = activities().get(activity_id)
    if activity is None:  # a developer's activity (ADR-012)
        from app.framework import package_activities

        d = package_activities.get(activity_id)
        return d.manifest.get("family") if d else None
    return activity["family"]


@lru_cache(maxsize=1)
def legacy_ids() -> dict[str, str]:
    """Old module id → current id. Stored data, licences and on-site installs may use either."""
    return json.loads((CATALOG_DIR / "legacy_ids.json").read_text(encoding="utf-8"))["legacy_ids"]


def canonical_module(module_id: str) -> str:
    return legacy_ids().get(module_id, module_id)


def canonical_modules(module_ids: list[str]) -> list[str]:
    """Current ids, in order, without duplicates."""
    return list(dict.fromkeys(canonical_module(m) for m in module_ids))


@lru_cache(maxsize=1)
def legacy_activities() -> dict[str, str]:
    """Old activity id → current id (stored as tenants.sector)."""
    return json.loads((CATALOG_DIR / "legacy_ids.json").read_text(encoding="utf-8")).get("legacy_activities", {})


def canonical_activity(activity_id: str) -> str:
    return legacy_activities().get(activity_id, activity_id)
