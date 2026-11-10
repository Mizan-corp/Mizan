"""The module registry is the only way modules reach the API (ADR-006, phase 1)."""
import json
import os
import re
import uuid
from pathlib import Path

import pytest

from fastapi.routing import APIRoute

from app.framework.loader import registry
from main import app

SYSTEM_API = Path(__file__).resolve().parents[1] / "system_api"


def _routes(router) -> set[tuple[str, str]]:
    return {(m, r.path) for r in router.routes if isinstance(r, APIRoute) for m in r.methods}


def test_every_module_loads():
    registry.get_all_manifests()
    assert registry.errors == []


def test_no_module_router_is_mounted_by_hand():
    pattern = re.compile(r"from app\.modules\.[\w.]+\.router import")
    for py in SYSTEM_API.rglob("*.py"):
        assert not pattern.search(py.read_text(encoding="utf-8")), py


def test_every_module_router_is_served():
    served = _routes(app.router)
    for module_id, router in registry.get_routers().items():
        missing = _routes(router) - served
        assert not missing, f"{module_id}: {sorted(missing)[:3]}"


def test_industry_routes_are_guarded_by_their_module():
    # Before the single loader, these were also served without the module guard under
    # /restaurant, /school and /services.
    paths = {p for _, p in _routes(app.router)}
    for prefix in ("/restaurant/", "/school/", "/services/"):
        assert not [p for p in paths if p.startswith(prefix)], prefix
    for module_id in ("restaurant", "kitchen_display", "school", "services"):
        router = registry.get_routers()[module_id]
        assert router.prefix.startswith("/modules/"), module_id
        assert router.dependencies, f"{module_id} has no module guard"


def test_one_catalogue_and_one_store_of_active_modules():
    # The hard-coded MODULE_CATALOG and the installed_modules setting are gone (migration v50).
    app_dir = Path(__file__).resolve().parents[3] / "shared" / "backend" / "app"
    for py in app_dir.rglob("*.py"):
        if py.name == "migrations.py" or "__pycache__" in py.parts:
            continue
        text = py.read_text(encoding="utf-8")
        assert "MODULE_CATALOG" not in text, py
        assert '"installed_modules"' not in text, py


def test_manifest_index_covers_every_module():
    from app.framework.loader import manifest_index

    assert set(manifest_index()) == {m.id for m in registry.get_all_manifests()}


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
async def test_active_modules_live_on_the_workspace():
    from sqlalchemy import delete, text

    from app.framework.activation import get_active_modules, set_active_modules
    from app.db.base import engine

    await engine.dispose()  # this test's event loop gets its own connections
    from app.platform.tenancy.context import bind_tenant
    from app.db.base import AsyncSessionLocal
    from app.models.tenant import Tenant

    tid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        db.add(Tenant(id=tid, name="Modules test", slug=f"mods-{tid.hex[:8]}"))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            await bind_tenant(db, tid)
            await set_active_modules(db, ["storefront"])
            active = await get_active_modules(db)
            assert {"core", "storefront", "inventory"} <= set(active)  # inventory: a dependency
            stored = await db.scalar(text("SELECT active_modules FROM tenants WHERE id = :t"), {"t": tid})
            assert set(stored) == set(active)
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(delete(Tenant).where(Tenant.id == tid))
            await db.commit()
        await engine.dispose()


def test_activities_and_families_are_consistent():
    from app.catalog import GENERAL, activities, families
    from app.framework.loader import manifest_index

    index = manifest_index()
    assert GENERAL in activities()
    for activity in activities().values():
        assert activity["family"] in families(), activity["id"]
        unknown = [m for m in activity["modules"] if m not in index]
        assert not unknown, f"{activity['id']}: {unknown}"
        if "legacy_of" in activity:
            assert activity["legacy_of"] in activities()
    for module in registry.get_all_manifests():
        assert module.activity in activities(), module.id
        assert module.category == activities()[module.activity]["family"], module.id


REPO = Path(__file__).resolve().parents[3]
APP = REPO / "shared" / "backend" / "app"
MODULES = APP / "modules"


def test_modules_live_in_their_home_activity():
    # modules/<home_activity>/<module_id>/, platform/<id>/, integrations/<id>/ (ADR-006).
    from app.framework.loader import manifest_files

    for manifest in manifest_files():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        folder = manifest.parent
        where = folder.relative_to(APP).parts
        kind = data.get("kind", "business")
        if kind == "business":
            assert where[0] == "modules" and where[1] == data["activity"], f"{folder} is not in modules/{data['activity']}/"
        else:
            assert where[0] == {"platform": "platform", "integration": "integrations"}[kind], folder
        assert folder.name == data["id"], f"{folder.relative_to(APP)} holds '{data['id']}'"


def test_activity_ids_are_full_one_word_names():
    from app.catalog import activities

    for aid in activities():
        assert re.fullmatch(r"[a-z]+", aid), f"activity '{aid}' should be one full word"


def test_activity_folders_match_their_ids():
    for f in (APP / "activities").glob("*/activity.json"):
        assert json.loads(f.read_text(encoding="utf-8"))["id"] == f.parent.name, f
    activities = {f.parent.name for f in (APP / "activities").glob("*/activity.json")}
    for folder in MODULES.iterdir():
        if folder.is_dir() and not folder.name.startswith(("_", ".")):
            assert folder.name in activities, f"modules/{folder.name} is not an activity"


WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE)


def test_module_paths_are_valid_on_windows():
    # The installers are built on Windows.
    roots = [MODULES, APP / "platform", APP / "integrations", APP / "framework", APP / "activities", APP / "catalog",
             REPO / "system" / "frontend" / "src" / "modules", REPO / "system" / "frontend" / "src" / "platform",
             REPO / "system" / "frontend" / "src" / "integrations"]
    for root in roots:
        for path in root.rglob("*"):
            if "__pycache__" in path.parts:
                continue
            assert not WINDOWS_RESERVED.match(path.name), path
            assert not re.search(r'[<>:"|?*]', path.name), path
        for folder in [root, *[p for p in root.rglob("*") if p.is_dir()]]:
            names = [p.name.lower() for p in folder.iterdir()]
            assert len(names) == len(set(names)), f"names differing only in case in {folder}"


def test_legacy_ids_point_to_current_modules():
    from app.catalog import canonical_modules, legacy_ids

    current = {m.id for m in registry.get_all_manifests()}
    for old, new in legacy_ids().items():
        assert old not in current, old
        assert new in current, f"{old} -> {new}"
    assert canonical_modules(["prn", "printing", "retail-pos", "pos", "cst"]) == ["printing", "pos", "construction"]
    assert canonical_modules(["hlt_pharmacy", "hot_pms", "hlt_emr"]) == ["hospital_pharmacy", "hotel_pms", "emr"]
    from app.catalog import canonical_activity
    assert canonical_activity("oil_gas") == "petroleum" and canonical_activity("retail") == "retail"


def test_frontend_mirrors_the_backend_layout():
    # system/frontend/src/modules/<home_activity>/<module_id>/, src/platform/<id>/, src/integrations/<id>/
    from app.framework import scaffold

    frontend = REPO / "system" / "frontend" / "src"
    by_activity: dict[str, set[str]] = {}
    for folder, m in scaffold.manifests():
        if m.get("kind", "business") == "business":
            by_activity.setdefault(m["activity"], set()).add(folder.name)
    for activity_dir in (frontend / "modules").iterdir():
        assert (APP / "activities" / activity_dir.name).is_dir(), f"src/modules/{activity_dir.name} is not an activity"
        for module_dir in (p for p in activity_dir.iterdir() if p.is_dir()):
            assert module_dir.name in by_activity.get(activity_dir.name, set()), f"{module_dir.relative_to(frontend)}"
    kinds = {folder.name: m.get("kind") for folder, m in scaffold.manifests()}
    for root, kind in (("platform", "platform"), ("integrations", "integration")):
        for module_dir in (frontend / root).iterdir():
            assert kinds.get(module_dir.name) == kind, module_dir

def test_every_module_has_the_adr_layout():
    # python manage.py module scaffold creates what's missing; new modules: module new.
    from app.framework import scaffold

    gaps = {str(d.relative_to(APP)): [p.name for p in scaffold.missing(d, m)] for d, m in scaffold.manifests()}
    assert not {k: v for k, v in gaps.items() if v}


def test_activities_have_the_adr_fields_and_valid_variants():
    from app.catalog import activities
    from app.framework.loader import manifest_index

    index = manifest_index()
    general = set(activities()["general"]["modules"])
    for aid, activity in activities().items():
        for key in ("family", "modules", "variants", "optional", "terms", "positions", "roles", "settings", "home"):
            assert key in activity, f"{aid}: '{key}'"
        assert (APP / "activities" / aid / "seed.py").exists(), aid
        for module_id, variant in activity["variants"].items():
            assert module_id in set(activity["modules"]) | general, f"{aid}: {module_id} isn't one of its modules"
            assert variant in index[module_id].get("variants", ["standard"]), f"{aid}: {module_id} has no '{variant}' variant"


def test_planned_modules_have_the_standard_structure_but_are_not_offered():
    # SRS modules not built yet: the full standard structure, status "planned" (ADR-006).
    from app.framework import scaffold
    from app.framework.loader import manifest_index

    all_ids = [m["id"] for _, m in scaffold.manifests()]
    assert len(all_ids) == len(set(all_ids)), "module ids (built and planned) must be unique"
    planned = [(d, m) for d, m in scaffold.manifests() if m.get("status") == "planned"]
    assert planned
    for folder, m in planned:
        assert m["id"] not in manifest_index(), f"{m['id']} is planned but offered"
        assert m["id"] not in registry.get_routers(), f"{m['id']} is planned but mounted"
        assert "(planned)" in (folder / "README.md").read_text(encoding="utf-8"), folder
        index_ts = scaffold.frontend_dir(folder) / "index.ts"
        assert 'status: "planned"' in index_ts.read_text(encoding="utf-8"), index_ts


def test_the_written_standard_covers_the_template():
    # docs/MODULE_STANDARD.md and app/framework/module_template/ describe the same files.
    from app.framework import scaffold

    doc = (REPO / "docs" / "MODULE_STANDARD.md").read_text(encoding="utf-8")
    for side in ("backend", "frontend"):
        for rel in (scaffold.TEMPLATE / side).rglob("*.tmpl"):
            name = rel.relative_to(scaffold.TEMPLATE / side).with_suffix("").as_posix().replace("{{variant}}", "<variant>")
            assert f"`{name}`" in doc, f"{side}/{name} is not described in docs/MODULE_STANDARD.md"
