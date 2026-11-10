"""The module registry is the only way modules reach the API (ADR-006, phase 1)."""
import os
import re
import uuid
from pathlib import Path

import pytest

from fastapi.routing import APIRoute

from app.modules.loader import registry
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
    from app.modules.loader import manifest_index

    assert set(manifest_index()) == {m.id for m in registry.get_all_manifests()}


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
async def test_active_modules_live_on_the_workspace():
    from sqlalchemy import delete, text

    from app.core.modules import get_active_modules, set_active_modules
    from app.db.base import engine

    await engine.dispose()  # this test's event loop gets its own connections
    from app.core.tenancy import bind_tenant
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
