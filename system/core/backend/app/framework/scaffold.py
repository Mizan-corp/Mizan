"""The standard module structure (docs/MODULE_STANDARD.md) and the tool that applies it.

The structure itself is the template in ``app/framework/module_template/``: ``backend/`` becomes
``app/activities/<activity>/modules/<id>/`` (``app/platform/<id>/``, ``app/integrations/<id>/`` by kind),
``frontend/`` the matching folder under ``system/frontend/src/``. Used by
``python manage.py module new|scaffold|check``. Only missing files are created; existing files
are never changed. Standard library only, so it runs without the API's settings.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parents[2]
FRONTEND = REPO / "system" / "frontend" / "src"
TEMPLATE = Path(__file__).resolve().parent / "module_template"
MODULE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
KIND_ROOT = {"platform": "platform", "integration": "integrations"}
STATUSES = ("active", "planned")
VARIANT_DIR = "{{variant}}"


def _templates(side: str) -> list[Path]:
    """Template files of one side (backend/frontend), relative to it, without .tmpl."""
    root = TEMPLATE / side
    return sorted(p.relative_to(root) for p in root.rglob("*.tmpl"))


def _target(rel: Path) -> Path:
    return rel.with_suffix("") if rel.suffix == ".tmpl" else rel


def _values(manifest: dict, variant: str | None = None) -> dict[str, str]:
    values = {
        "id": manifest["id"],
        "name": manifest.get("name") or manifest["id"],
        "name_en": manifest.get("name_en") or manifest.get("name") or manifest["id"],
        "activity": manifest.get("activity", "general"),
        "kind": manifest.get("kind", "business"),
        "status": manifest.get("status", "active"),
    }
    if variant:
        values["variant"] = variant
        values["variant_status"] = "active" if variant == "standard" else "planned"
        values["variant_description"] = "The module as it is, for every activity." if variant == "standard" else ""
    return values


def render(template: Path, values: dict[str, str]) -> str:
    text = template.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def manifests() -> list[tuple[Path, dict]]:
    """Every module folder (built or planned) with its manifest."""
    found = []
    for root, pattern in ((APP_DIR / "activities", "*/modules/*/manifest.json"), (APP_DIR / "platform", "*/manifest.json"),
                          (APP_DIR / "integrations", "*/manifest.json")):
        if root.exists():
            for f in sorted(root.glob(pattern)):
                if not any(part.startswith(("_", ".")) for part in f.relative_to(root).parts):
                    found.append((f.parent, json.loads(f.read_text(encoding="utf-8"))))
    return found


def frontend_dir(module_dir: Path) -> Path:
    return FRONTEND.joinpath(*module_dir.resolve().relative_to(APP_DIR).parts)


def _plan(module_dir: Path, manifest: dict) -> list[tuple[Path, Path, dict[str, str]]]:
    """(target file, template, values) for every file the standard asks for."""
    business = manifest.get("kind", "business") == "business"
    out = []
    for rel in _templates("backend"):
        if rel.name == "manifest.json.tmpl":
            continue  # the manifest is written by new_module, never regenerated
        if rel.parts[0] == "variants":
            if not business:
                continue
            for variant in manifest.get("variants", ["standard"]):
                if variant == "standard":  # the module's own defaults stay in the module
                    target = module_dir / _target(Path(*[variant if p == VARIANT_DIR else p for p in rel.parts]))
                else:  # an activity's adaptation lives in that activity (ADR-010)
                    inner = rel.parts[rel.parts.index(VARIANT_DIR) + 1:]
                    target = APP_DIR / "activities" / variant / "variants" / manifest["id"] / _target(Path(*inner))
                out.append((target, TEMPLATE / "backend" / rel, _values(manifest, variant)))
            continue
        out.append((module_dir / _target(rel), TEMPLATE / "backend" / rel, _values(manifest)))
    fe = frontend_dir(module_dir)
    for rel in _templates("frontend"):
        if rel.parts[0] == "variants" and not business:
            continue
        out.append((fe / _target(rel), TEMPLATE / "frontend" / rel, _values(manifest)))
    return out


# A larger module may split a file into a package (docs/MODULE_STANDARD.md, "Larger modules").
PACKAGE_FORM = {"models.py": "models", "schemas.py": "schemas", "service.py": "services", "router.py": "routes"}


def _present(target: Path) -> bool:
    if target.exists():
        return True
    package = target.parent / PACKAGE_FORM[target.name] if target.name in PACKAGE_FORM else None
    return bool(package and package.is_dir() and any(package.glob("*.py")))


def missing(module_dir: Path, manifest: dict) -> list[Path]:
    """The standard files this module doesn't have yet (backend and frontend)."""
    return [target for target, _, _ in _plan(module_dir, manifest) if not _present(target)]


def scaffold(module_dir: Path, manifest: dict) -> list[Path]:
    """Create whatever is missing; return what was created."""
    created = []
    for target, template, values in _plan(module_dir, manifest):
        if _present(target):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(template, values), encoding="utf-8")
        created.append(target)
    return created


def regenerate(module_dir: Path, manifest: dict, files: set[Path]) -> list[Path]:
    """Rewrite the given standard files from the template (used to refresh placeholders)."""
    done = []
    for target, template, values in _plan(module_dir, manifest):
        if target in files:
            target.write_text(render(template, values), encoding="utf-8")
            done.append(target)
    return done


def scaffold_all() -> list[Path]:
    created = []
    for module_dir, manifest in manifests():
        created += scaffold(module_dir, manifest)
    return created


def new_module(activity: str, module_id: str, name: str, name_en: str = "", kind: str = "business",
               status: str = "active") -> Path:
    """A new module (or a planned one) with the full standard structure."""
    if not MODULE_ID.match(module_id):
        raise ValueError(f"module id '{module_id}' must be lowercase letters, digits and underscores")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    existing = {m["id"]: d for d, m in manifests()}
    if module_id in existing:
        planned = json.loads((existing[module_id] / "manifest.json").read_text(encoding="utf-8")).get("status") == "planned"
        if not (planned and status == "active"):
            raise ValueError(f"module id '{module_id}' is already used")
        # Building a planned module: it becomes active; its files are already in place.
        manifest_file = existing[module_id] / "manifest.json"
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        data["status"] = "active"
        manifest_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _activate_frontend(existing[module_id])
        scaffold(existing[module_id], data)
        return existing[module_id]
    if not (APP_DIR / "activities" / activity / "activity.json").exists():
        raise ValueError(f"unknown activity '{activity}'")
    module_dir = APP_DIR / KIND_ROOT[kind] / module_id if kind in KIND_ROOT else APP_DIR / "activities" / activity / "modules" / module_id
    if module_dir.exists() and {f.name for f in module_dir.iterdir()} - {"README.md"}:
        raise ValueError(f"{module_dir} already exists")
    module_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(render(TEMPLATE / "backend" / "manifest.json.tmpl", {
        "id": module_id, "name": name, "name_en": name_en or name, "activity": activity, "kind": kind, "status": status,
    }))
    if kind != "business":
        manifest.pop("variants")
    (module_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scaffold(module_dir, manifest)
    return module_dir


def _activate_frontend(module_dir: Path) -> None:
    index = frontend_dir(module_dir) / "index.ts"
    if index.exists():
        index.write_text(index.read_text(encoding="utf-8").replace('status: "planned"', 'status: "active"'), encoding="utf-8")


def catalog_markdown() -> str:
    """docs/MODULE_CATALOG.md, generated from the manifests (`manage.py module catalog`)."""
    acts = {f.parent.name: json.loads(f.read_text(encoding="utf-8")) for f in sorted((APP_DIR / "activities").glob("*/activity.json"))}

    def mods(folder: Path) -> list[dict]:
        return [json.loads(m.read_text(encoding="utf-8")) for m in sorted(folder.glob("*/manifest.json"))]

    def short(text: str) -> str:
        text = (text or "").replace("|", "/").replace("\n", " ")
        return text if len(text) <= 140 else text[:137].rsplit(" ", 1)[0] + "…"

    def subdirs(folder: Path) -> list[str]:
        return sorted(p.name for p in folder.iterdir() if p.is_dir() and p.name != "__pycache__") if folder.is_dir() else []

    lines = ["# Mizan ERP — Module Catalog", "",
             "Every module, generated from the manifests by `python manage.py module catalog` (a test fails when",
             "it's out of date); ids are folder names. A business activity is one folder (ADR-010):",
             "`system/core/backend/app/activities/<activity>/modules/<module_id>/`, screens in",
             "`system/frontend/src/activities/<activity>/modules/<module_id>/`, with the activity's variants of",
             "other activities' modules in `activities/<activity>/variants/<module>/`.",
             "Status: **active** (built, offered) or *planned* (laid out from the SRS, not offered yet).", ""]
    for a in ["general"] + sorted(x for x in acts if x != "general"):
        act = acts[a]
        if act.get("legacy_of"):
            continue
        folder = APP_DIR / "activities" / a
        lines += [f"## {act.get('name_en', a)} (`{a}`, {act.get('family')})", ""]
        if act.get("description"):
            lines += [act["description"], ""]
        variants, themes = subdirs(folder / "variants"), subdirs(folder / "themes")
        lines += ["Turns on: " + (", ".join(f"`{m}`" for m in act.get("modules", [])) or "—") + "."
                  + (" Adapts: " + ", ".join(f"`{v}`" for v in variants) + "." if variants else "")
                  + (" Themes: " + ", ".join(themes) + "." if themes else ""), ""]
        ms = mods(folder / "modules")
        if ms:
            lines += ["| Module | Name | Status | What it does |", "|---|---|---|---|"]
            for d in ms:
                status = "**active**" if d.get("status", "active") == "active" else "*planned*"
                lines.append(f"| `{d['id']}` | {d.get('name_en') or d.get('name')} | {status} | {short(d.get('description'))} |")
            lines.append("")
    for title, folder in (("Platform modules (`app/platform/`)", APP_DIR / "platform"),
                          ("Connectors (`app/integrations/`)", APP_DIR / "integrations")):
        lines += [f"## {title}", "", "| Module | Name | What it does |", "|---|---|---|"]
        lines += [f"| `{d['id']}` | {d.get('name_en') or d.get('name')} | {short(d.get('description'))} |" for d in mods(folder)]
        lines.append("")
    lines += ["## From outside developers", "",
              "Community modules, theme packs and whole activities from developers are installed per workspace",
              "from signed packages (ADR-007, ADR-010); they aren't in this catalogue. See `dev.allmizan.live/docs`.", ""]
    return "\n".join(lines)
