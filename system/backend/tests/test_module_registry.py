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
        assert not re.search(r"\bMODULE_CATALOG\b(?!\.md)", text), py  # the constant, not docs/MODULE_CATALOG.md
        assert '"installed_modules"' not in text, py


def test_manifest_index_covers_every_module():
    from app.framework.loader import manifest_index

    assert set(manifest_index()) == {m.id for m in registry.get_all_manifests()}


def test_every_checked_permission_is_declared_once():
    """One permission system (ADR-006 phase 3): ids live in one module's manifest, and every
    require_perm(...) names a declared id."""
    from app.framework.loader import manifest_index

    owners: dict[str, list[str]] = {}
    for module_id, manifest in manifest_index().items():
        for p in manifest.get("permissions", []):
            owners.setdefault(p["id"] if isinstance(p, dict) else p, []).append(module_id)
    assert not {k: v for k, v in owners.items() if len(v) > 1}

    root = Path(__file__).resolve().parents[3] / "shared" / "backend" / "app"
    checked = set()
    for f in root.rglob("*.py"):
        for call in re.findall(r"require_perm\(([^)]*)\)", f.read_text(errors="ignore")):
            checked.update(re.findall(r"[\"']([^\"']+)[\"']", call))
    assert checked - set(owners) == set()


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
async def test_active_modules_live_on_the_workspace():
    from sqlalchemy import delete, text

    from app.framework.activation import get_active_modules, set_active_modules
    from app.db.base import engine

    await engine.dispose()  # this test's event loop gets its own connections
    from app.platform.tenancy.context import bind_tenant
    from app.db.base import AsyncSessionLocal
    from app.platform.tenancy.models import Tenant

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
ACTIVITIES = APP / "activities"
FRONTEND = REPO / "system" / "frontend" / "src"
# What an activity's folder may hold (ADR-010 D1); first-party activities may also share Python
# code between their modules at the root (healthcare's seeder).
ACTIVITY_ENTRIES = {"activity.json", "positions.json", "seed.py", "README.md", "modules", "variants", "themes",
                    "seed", "i18n", "assets", "__pycache__", "__init__.py"}


def test_modules_live_in_their_home_activity():
    # activities/<home_activity>/modules/<module_id>/, platform/<id>/, integrations/<id>/ (ADR-010).
    from app.framework.loader import manifest_files

    for manifest in manifest_files():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        folder = manifest.parent
        where = folder.relative_to(APP).parts
        kind = data.get("kind", "business")
        if kind == "business":
            assert where[:3] == ("activities", data["activity"], "modules"), f"{folder} is not in activities/{data['activity']}/modules/"
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
    for folder in ACTIVITIES.iterdir():
        if folder.is_dir() and not folder.name.startswith(("_", ".")):
            assert (folder / "activity.json").is_file(), f"activities/{folder.name} has no activity.json"


def test_activities_are_self_contained_folders():
    """ADR-010: an activity's folder holds its definition, modules, variants, themes and data."""
    for folder in (p for p in ACTIVITIES.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        extra = {e.name for e in folder.iterdir()} - ACTIVITY_ENTRIES
        assert all(n.endswith(".py") for n in extra), f"activities/{folder.name}: unexpected {sorted(extra)}"
    for side in (APP, FRONTEND):
        for folder in (side / "activities").iterdir():
            if folder.is_dir():
                unexpected = {e.name for e in folder.iterdir() if e.is_dir()} - ACTIVITY_ENTRIES
                assert not unexpected, f"{folder}: unexpected folders {sorted(unexpected)}"


def test_activity_variants_adapt_real_modules():
    """activities/<activity>/variants/<module>/: the module exists and lists the variant."""
    from app.framework.loader import manifest_index

    index = manifest_index()
    for f in ACTIVITIES.glob("*/variants/*/variant.json"):
        module_id, activity_id = f.parent.name, f.parent.parent.parent.name
        assert module_id in index, f"{f}: no module {module_id}"
        assert activity_id in index[module_id].get("variants", []), f"{module_id} doesn't list the variant {activity_id}"
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data.get("module", module_id) == module_id and data.get("id", activity_id) == activity_id, f
    for f in ACTIVITIES.glob("*/modules/*/variants/*/variant.json"):
        assert f.parent.name == "standard", f"{f}: an activity's variant belongs in activities/<activity>/variants/"


WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE)


def test_module_paths_are_valid_on_windows():
    # The installers are built on Windows.
    roots = [APP / "platform", APP / "integrations", APP / "framework", APP / "activities", APP / "catalog",
             FRONTEND / "activities", FRONTEND / "platform",
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
    # src/activities/<home_activity>/modules/<module_id>/, src/platform/<id>/, src/integrations/<id>/
    from app.framework import scaffold

    frontend = REPO / "system" / "frontend" / "src"
    by_activity: dict[str, set[str]] = {}
    for folder, m in scaffold.manifests():
        if m.get("kind", "business") == "business":
            by_activity.setdefault(m["activity"], set()).add(folder.name)
    for activity_dir in (frontend / "activities").iterdir():
        assert (APP / "activities" / activity_dir.name).is_dir(), f"src/activities/{activity_dir.name} is not an activity"
        modules = activity_dir / "modules"
        for module_dir in (p for p in modules.iterdir() if p.is_dir()) if modules.is_dir() else []:
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


def test_demo_catalogue_follows_the_activity():
    # Activities without a catalogue used to get the plumbing one (a pharmacy full of taps).
    from app.activities.consulting.seed import CATALOG as consulting
    from app.activities.healthcare.seed import CATALOG as healthcare
    from app.activities.pharmacy.seed import CATALOG as pharmacy
    from app.activities.retail.seed import CATALOG as retail
    from app.framework.demo import catalog_for

    assert catalog_for("pharmacy") == pharmacy != healthcare  # its own drugs, with their details
    assert catalog_for("consulting") == consulting and catalog_for("services") == consulting
    assert catalog_for("gym") == retail and catalog_for("petroleum") == retail
    assert catalog_for("plumbing") != retail


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
async def test_new_workspaces_get_their_activitys_demo_data():
    from sqlalchemy import delete, text

    from app.db.base import AsyncSessionLocal, engine
    from app.platform.tenancy.models import Tenant
    from app.platform.tenancy.service import create_workspace

    await engine.dispose()
    created = []
    try:
        for sector, item in (("healthcare", "باراسيتامول"), ("gym", "أرز مصري")):
            async with AsyncSessionLocal() as db:
                tenant, _ = await create_workspace(
                    db, name=f"Demo {sector} {uuid.uuid4().hex[:6]}", sector=sector, scale="small",
                    admin_username=f"demo_{uuid.uuid4().hex[:8]}", admin_full_name="Demo", admin_password_hash="x")
                await db.commit()
                created.append(tenant.id)
                names = (await db.execute(text("SELECT name FROM products WHERE tenant_id = :t"), {"t": tenant.id})).scalars().all()
                assert len(names) == 24 and any(item in n for n in names), (sector, names[:3])
                if sector == "healthcare":
                    patients = await db.scalar(text("SELECT count(*) FROM clinic_patients WHERE tenant_id = :t"), {"t": str(tenant.id)})
                    assert patients and patients > 0
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(delete(Tenant).where(Tenant.id.in_(created)))
            await db.commit()
        await engine.dispose()


def test_menus_point_at_declared_screens_and_permissions():
    """Role screens (ADR-006 phase 5): every menu entry, home and dashboard widget an activity
    arranges is something a module declares, guarded by a declared permission."""
    from app.catalog import activities
    from app.framework.loader import manifest_index
    from app.framework.screens import catalogue

    screens, widgets = catalogue()
    declared = {p["id"] if isinstance(p, dict) else p for m in manifest_index().values() for p in m.get("permissions", [])}

    def perms_ok(perm, where):
        for p in (perm or "").split("|"):
            assert not p or p in declared, f"{where}: permission '{p}' isn't declared"

    paths = {}
    for sid, s in screens.items():
        assert sid.startswith(s["module"] + "."), sid
        assert s["path"].startswith("/") and s.get("label") and s.get("icon"), sid
        assert paths.setdefault(s["path"], sid) == sid, f"{s['path']} declared twice"
        perms_ok(s.get("permission"), sid)
    for wid, w in widgets.items():
        assert wid.startswith(w["module"] + ".") and w.get("label"), wid
        perms_ok(w.get("permission"), wid)

    assert activities()["general"]["menu"], "general's menu is everyone's default"
    for aid, activity in activities().items():
        layouts = [activity, *activity.get("roles", {}).values()]
        for layout in layouts:
            for group in layout.get("menu", []):
                assert group.get("id") and group.get("label") and group.get("items"), f"{aid}: {group}"
                for item in group["items"]:
                    assert item["screen"] in screens, f"{aid}: unknown screen {item['screen']}"
                    perms_ok(item.get("permission"), f"{aid}/{item['screen']}")
            for entry in layout.get("dashboard", []):
                wid = entry if isinstance(entry, str) else entry.get("id")
                assert wid in widgets, f"{aid}: unknown widget {wid}"
                assert isinstance(entry, str) or entry.get("size") in (None, "s", "m", "l"), f"{aid}: {entry}"
            if layout.get("home_screen"):
                assert layout["home_screen"] in screens, f"{aid}: unknown home {layout['home_screen']}"


def test_frontend_definitions_match_the_manifests():
    """A module's index.ts has its manifest's status, and renders every widget it declares."""
    from app.framework import scaffold

    for folder, m in scaffold.manifests():
        index = FRONTEND / "activities" / m.get("activity", "") / "modules" / folder.name / "index.ts"
        if m.get("kind", "business") != "business" or not index.exists():
            continue
        source = index.read_text(encoding="utf-8")
        assert f'status: "{m.get("status", "active")}"' in source, f"{index}: status"
        for w in m.get("widgets") or []:
            assert f'"{w["id"]}"' in source, f"{index}: no component for widget {w['id']}"


def test_the_module_catalogue_is_current():
    from app.framework.scaffold import catalog_markdown

    current = (REPO / "docs" / "MODULE_CATALOG.md").read_text(encoding="utf-8")
    assert current == catalog_markdown(), "docs/MODULE_CATALOG.md is out of date: run `python manage.py module catalog`"
