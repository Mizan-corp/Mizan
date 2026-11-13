"""Variant resolution (ADR-006 D1/D2).

A workspace has one activity; the activity says which variant of each module it runs
(`activity.json` "variants"), `standard` otherwise. A module's own defaults are its `standard`
variant (`<module>/variants/standard/`); an activity's adaptation of a module lives in the activity
(`activities/<activity>/variants/<module>/variant.json`, ADR-010), and its id is the activity's. A
variant changes how the module works for that activity: fields, terms, settings defaults, extra
permissions, screens, templates, widgets, the modules it uses, and rules in its `hooks.py`.

Resolution order: module (base) -> variant (chosen by the activity) -> workspace settings and
fields. A variant still marked "planned" isn't used: the module runs `standard` until it's built.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ACTIVITIES = Path(__file__).resolve().parents[1] / "activities"


@lru_cache(maxsize=None)
def activity(activity_id: str | None) -> dict:
    """An activity's definition, following a legacy activity to the one it maps to."""
    if not activity_id:
        return {}
    f = ACTIVITIES / activity_id / "activity.json"
    if not f.is_file():
        from app.framework import package_activities  # a developer's activity (ADR-012)

        d = package_activities.get(activity_id)
        return d.activity if d else {}
    data = json.loads(f.read_text(encoding="utf-8"))
    if data.get("legacy_of"):
        return activity(data["legacy_of"])
    return data


@lru_cache(maxsize=1)
def all_variants() -> dict[str, dict[str, dict]]:
    """module id -> {variant id -> variant.json}."""
    from app.framework.loader import module_dirs

    out: dict[str, dict[str, dict]] = {}
    for module_id, path in module_dirs().items():
        for f in sorted((path / "variants").glob("*/variant.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            out.setdefault(module_id, {})[data.get("id", f.parent.name)] = {**data, "_dir": str(f.parent)}
    # Activities' adaptations of modules: activities/<activity>/variants/<module>/.
    for f in sorted(ACTIVITIES.glob("*/variants/*/variant.json")):
        module_id, activity_id = f.parent.name, f.parent.parent.parent.name
        data = json.loads(f.read_text(encoding="utf-8"))
        out.setdefault(module_id, {})[activity_id] = {**data, "id": activity_id, "_dir": str(f.parent)}
    # Developers' activities' adaptations (ADR-012): fields, terms and settings only.
    from app.framework import package_activities

    for d in package_activities.all_defs().values():
        for module_id, data in d.variants.items():
            out.setdefault(module_id, {})[d.id] = data
    return out


def variant_of(module_id: str, activity_id: str | None) -> str:
    """The variant a workspace of this activity runs for the module."""
    wanted = (activity(activity_id).get("variants") or {}).get(module_id)
    variant = all_variants().get(module_id, {}).get(wanted or "")
    if variant and variant.get("status", "active") == "active":
        return wanted
    return "standard"


def variant(module_id: str, activity_id: str | None) -> dict:
    return all_variants().get(module_id, {}).get(variant_of(module_id, activity_id), {})


def variants_for(activity_id: str | None) -> dict[str, str]:
    """Every module's variant for this activity (only those that aren't `standard`)."""
    return {m: v for m in all_variants() if (v := variant_of(m, activity_id)) != "standard"}


def terms_for(activity_id: str | None) -> dict[str, str]:
    """The activity's words ("item" -> "دواء"), then each active variant's."""
    terms = dict(activity(activity_id).get("terms") or {})
    for module_id in variants_for(activity_id):
        terms.update(variant(module_id, activity_id).get("terms") or {})
    return terms


def setting_defaults(module_id: str, activity_id: str | None) -> dict:
    """Defaults for a module's settings: the variant's, then the activity's "<module>.<key>"."""
    out = dict(variant(module_id, activity_id).get("settings") or {})
    prefix = f"{module_id}."
    for key, value in (activity(activity_id).get("settings") or {}).items():
        if key.startswith(prefix):
            out[key[len(prefix):]] = value
    return out


def setting(module_id: str, key: str, activity_id: str | None, default=None):
    return setting_defaults(module_id, activity_id).get(key, default)
