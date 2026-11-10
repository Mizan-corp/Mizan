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


@lru_cache(maxsize=1)
def activities() -> dict[str, dict[str, Any]]:
    """Every activity, from app/activities/<activity_id>/activity.json."""
    found = {}
    for f in sorted(ACTIVITIES_DIR.glob("*/activity.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        found[data["id"]] = data
    return dict(sorted(found.items(), key=lambda kv: kv[1].get("order", 999)))


def family_of(activity_id: str) -> str | None:
    activity = activities().get(activity_id)
    return activity["family"] if activity else None


@lru_cache(maxsize=1)
def legacy_ids() -> dict[str, str]:
    """Old module id → current id. Stored data, licences and on-site installs may use either."""
    return json.loads((CATALOG_DIR / "legacy_ids.json").read_text(encoding="utf-8"))["legacy_ids"]


def canonical_module(module_id: str) -> str:
    return legacy_ids().get(module_id, module_id)


def canonical_modules(module_ids: list[str]) -> list[str]:
    """Current ids, in order, without duplicates."""
    return list(dict.fromkeys(canonical_module(m) for m in module_ids))
