"""The module registry is the only way modules reach the API (ADR-006, phase 1)."""
import re
from pathlib import Path

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
