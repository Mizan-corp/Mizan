"""The ADR-006 layout of a module, and the tool that creates it (`python manage.py module …`).

Backend, ``app/modules/<home_activity>/<module_id>/`` (platform and integration modules in
``app/platform/<id>/`` and ``app/integrations/<id>/``)::

    manifest.json  models.py  schemas.py  service.py  router.py  hooks.py  seed.py  README.md
    migrations/  templates/  tests/  variants/<variant>/{variant.json, hooks.py}

Frontend, ``system/frontend/src/modules/<home_activity>/<module_id>/`` (``src/platform/``,
``src/integrations/``)::

    index.ts  api.ts  screens/  components/  variants/

Only missing pieces are created; existing files are never changed. Standard library only, so it
runs without the API's settings.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
REPO = APP_DIR.parents[2]
FRONTEND = REPO / "system" / "frontend" / "src"
MODULE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
KIND_ROOT = {"platform": "platform", "integration": "integrations"}

BACKEND_FILES = {
    "models.py": '"""{name}: database models. None yet."""\n',
    "schemas.py": '"""{name}: request and response schemas. None yet."""\n',
    "service.py": '"""{name}: business logic, called by the router. None yet (logic may still be in router.py)."""\n',
    "router.py": '"""{name}: API routes. None yet."""\n',
    "hooks.py": (
        '"""{name}: extension points other modules and variants can hook into, e.g. before_confirm,\n'
        'after_confirm (ADR-006 phase 4). None yet."""\n'
    ),
    "seed.py": (
        '"""{name}: demo data for this module. Still in app/services/demo_seed.py; it moves here\n'
        'activity by activity (ADR-006)."""\n'
    ),
    "README.md": "# {name}\n\n`{id}`, home activity `{activity}`. See `manifest.json` and ADR-006.\n",
    "migrations/README.md": (
        "# Migrations\n\nThis module's own database migrations (ADR-006). Until the per-module runner exists,\n"
        "migrations live in `app/db/migrations.py`.\n"
    ),
    "templates/README.md": "# Templates\n\nPrint templates: `templates/<category>/<name>.html` (see `core/printing`).\n",
    "tests/README.md": "# Tests\n\nThis module's tests. Until module tests are collected, tests live in `system/backend/tests/`.\n",
}

FRONTEND_FILES = {
    "index.ts": (
        'import type {{ ModuleDefinition }} from "@app/framework/types";\n\n'
        "// {name}: the routes, screens, widgets and navigation entries this module provides (ADR-006).\n"
        "// Screens are still registered in App.tsx and lib/nav.ts until the framework renders them.\n"
        "const definition: ModuleDefinition = {{\n"
        '  id: "{id}",\n  activity: "{activity}",\n  kind: "{kind}",\n'
        "  screens: {{}},\n  widgets: {{}},\n  nav: [],\n}};\n\nexport default definition;\n"
    ),
    "api.ts": (
        "// {name}: API calls for this module. Screens still call @/lib/api directly; calls move here\n"
        "// as screens are reworked.\nexport {{}};\n"
    ),
    "screens/README.md": "# Screens\n\nFull screens of `{id}`. A variant can replace or add screens.\n",
    "components/README.md": "# Components\n\nParts used by this module's screens.\n",
    "variants/README.md": (
        "# Variants\n\n`variants/<activity_id>/`: screens and components that replace or add to this module's\n"
        "for one activity (ADR-006). The backend side is in the module's `variants/` folder.\n"
    ),
}


def variant_json(module_id: str, variant: str, **extra) -> dict:
    """What a variant can change (ADR-006 D1). `standard` fits every activity."""
    return {
        "id": variant,
        "module": module_id,
        "status": extra.pop("status", "planned" if variant != "standard" else "active"),
        "description": extra.pop("description", "The module as it is, for every activity." if variant == "standard" else ""),
        "screens": {},
        "fields": {},
        "uses": [],
        "terms": {},
        "settings": {},
        "permissions": [],
        "templates": {},
        "widgets": [],
        **extra,
    }


def manifests() -> list[tuple[Path, dict]]:
    """Every module folder with its manifest."""
    found = []
    roots = [(APP_DIR / "modules", 2), (APP_DIR / "platform", 1), (APP_DIR / "integrations", 1)]
    for root, depth in roots:
        if not root.exists():
            continue
        pattern = "*/*/manifest.json" if depth == 2 else "*/manifest.json"
        for f in sorted(root.glob(pattern)):
            if not any(part.startswith(("_", ".")) for part in f.relative_to(root).parts):
                found.append((f.parent, json.loads(f.read_text(encoding="utf-8"))))
    return found


def frontend_dir(module_dir: Path) -> Path:
    rel = module_dir.relative_to(APP_DIR)
    return FRONTEND.joinpath(*rel.parts)


def missing(module_dir: Path, manifest: dict) -> list[Path]:
    """The ADR-006 pieces this module doesn't have yet (backend and frontend)."""
    out = [module_dir / f for f in BACKEND_FILES if not (module_dir / f).exists()]
    if manifest.get("kind", "business") == "business":
        for variant in manifest.get("variants", ["standard"]):
            for f in ("variant.json", "hooks.py"):
                if not (module_dir / "variants" / variant / f).exists():
                    out.append(module_dir / "variants" / variant / f)
    fe = frontend_dir(module_dir)
    business = manifest.get("kind", "business") == "business"
    out += [fe / f for f in FRONTEND_FILES if not (fe / f).exists() and (business or not f.startswith("variants/"))]
    return out


def _fill(template: str, module_dir: Path, manifest: dict) -> str:
    return template.format(
        name=manifest.get("name_en") or manifest.get("name") or manifest["id"],
        id=manifest["id"],
        activity=manifest.get("activity", "general"),
        kind=manifest.get("kind", "business"),
    )


def scaffold(module_dir: Path, manifest: dict) -> list[Path]:
    """Create whatever is missing; return what was created."""
    created = []
    for path in missing(module_dir, manifest):
        path.parent.mkdir(parents=True, exist_ok=True)
        rel = path.name
        if path.parent.parent.name == "variants":
            variant = path.parent.name
            if rel == "variant.json":
                content = json.dumps(variant_json(manifest["id"], variant), ensure_ascii=False, indent=2) + "\n"
            else:
                content = f'"""{manifest["id"]}, {variant} variant: rules for this activity (ADR-006 phase 4). None yet."""\n'
        elif path.is_relative_to(FRONTEND):
            key = str(path.relative_to(frontend_dir(module_dir)))
            content = _fill(FRONTEND_FILES[key], module_dir, manifest)
        else:
            key = str(path.relative_to(module_dir))
            content = _fill(BACKEND_FILES[key], module_dir, manifest)
        path.write_text(content, encoding="utf-8")
        created.append(path)
    return created


def scaffold_all() -> list[Path]:
    created = []
    for module_dir, manifest in manifests():
        created += scaffold(module_dir, manifest)
    return created


def new_module(activity: str, module_id: str, name: str, name_en: str = "", kind: str = "business") -> Path:
    """A new module with its manifest and the full layout (ADR-006 `module new`)."""
    if not MODULE_ID.match(module_id):
        raise ValueError(f"module id '{module_id}' must be lowercase letters, digits and underscores")
    if any(m.get("id") == module_id for _, m in manifests()):
        raise ValueError(f"module id '{module_id}' is already used")
    if not (APP_DIR / "activities" / activity / "activity.json").exists():
        raise ValueError(f"unknown activity '{activity}'")
    if kind in KIND_ROOT:
        module_dir = APP_DIR / KIND_ROOT[kind] / module_id
    else:
        module_dir = APP_DIR / "modules" / activity / module_id
    manifest = {
        "id": module_id, "name": name, "name_en": name_en or name, "activity": activity, "kind": kind,
        "version": "0.1.0", "icon": "Blocks", "description": "", "dependencies": ["core"],
        "permissions": [], "screens": [], "widgets": [], "variants": ["standard"],
    }
    module_dir.mkdir(parents=True)
    (module_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scaffold(module_dir, manifest)
    return module_dir
