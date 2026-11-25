"""Theme packs (ADR-010 D3): the format, Mizan's themes, and a workspace's theme."""
import copy
import json
import os
import uuid

import pytest

import main  # noqa: F401
from app.framework import package as mzm
from app.framework.manifest import theme_problems
from tests.test_community_packages import developer, files

FONT = b"wOF2\x00\x01fake-font"


def platform_theme(theme_id: str) -> dict:
    """A platform theme as consumers see it: palette + font refs expanded."""
    base = os.path.join(os.path.dirname(__file__), "../../../shared/backend/app/themes")
    t = json.loads(open(os.path.join(base, theme_id, "theme.json"), encoding="utf-8").read())
    if "colors" not in t and isinstance(t.get("palette"), str):
        pal = json.loads(open(os.path.join(base, "_palettes", t["palette"] + ".json"), encoding="utf-8").read())
        t = {**t, "colors": pal["colors"]}
    t.pop("palette", None)  # a package embeds its colors; the ref is platform-side only
    return t


def sunrise(**over) -> dict:
    mizan = platform_theme("mizan")
    theme = {**mizan, "id": "acme.sunrise", "name": "شروق", "name_en": "Sunrise", "version": "1.0.0",
             "fonts": {"body": "Sunrise Sans", "files": [{"family": "Sunrise Sans", "src": "assets/sunrise.woff2", "weight": "100 900"}]}, "motion": "reduced"}
    theme["colors"]["light"]["primary"] = "oklch(0.55 0.17 40)"
    return {**theme, **over}


def theme_package(theme: dict | None = None) -> bytes:
    key, cert = developer()
    body = {"manifest.json": json.dumps(theme or sunrise(), ensure_ascii=False).encode(), "assets/sunrise.woff2": FONT}
    return mzm.build(body, key, cert)


def test_mizans_themes_are_valid():
    from app.platform.themes.service import check_file_themes, file_themes

    assert {"mizan", "slate", "cobalt", "emerald", "amber", "monokai"} <= set(file_themes())
    assert check_file_themes() == []


def test_themes_refuse_what_could_break_the_app():
    good = sunrise()
    assert theme_problems(good, package=True) == []
    bad = copy.deepcopy(good)
    bad["colors"]["light"]["primary"] = "red; } body { display: none"
    assert any("primary" in p for p in theme_problems(bad))
    bad = copy.deepcopy(good)
    bad["colors"]["dark"]["--x"] = "#fff"
    assert any("unknown token" in p for p in theme_problems(bad))
    bad = copy.deepcopy(good)
    del bad["colors"]["dark"]["sidebar"]
    assert any("'sidebar' is required" in p for p in theme_problems(bad))
    bad = copy.deepcopy(good)
    bad["colors"]["light"]["foreground"] = "#EEEEEE"  # light grey text on cream
    assert any("contrast" in p for p in theme_problems(bad))
    assert any("radius" in p for p in theme_problems({**good, "radius": "calc(1px)"}))
    assert any("fonts.files" in p for p in theme_problems({**good, "fonts": {"files": [{"family": "X", "src": "../x.woff2"}]}}))
    assert any("fonts.files" in p for p in theme_problems({**good, "fonts": {"files": [{"family": "X';}", "src": "assets/x.woff2"}]}}))
    assert any("'script' isn't a theme field" in p for p in theme_problems({**good, "script": "alert(1)"}))
    assert any("<developer>.<theme>" in p for p in theme_problems({**good, "id": "sunrise"}, package=True))
    with pytest.raises(mzm.PackageError, match="isn't in the package"):  # a declared font that isn't shipped
        key, cert = developer()
        mzm.build({"manifest.json": json.dumps(good).encode()}, key, cert)


pytestmark_db = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")


@pytest.fixture
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


@pytestmark_db
async def test_a_workspace_chooses_installs_and_removes_themes(fresh_engine):
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text

    from app.db.base import AsyncSessionLocal
    from app.platform.auth.models.user import User
    from app.platform.auth.security import create_access_token, hash_password
    from app.platform.permissions.access import set_access
    from app.platform.tenancy.context import bind_tenant, current_tenant_id
    from app.platform.tenancy.models import Tenant

    tid, tokens = uuid.uuid4(), {}
    slug = f"themes-{tid.hex[:8]}"
    async with AsyncSessionLocal() as db:
        db.add(Tenant(id=tid, name="Themes", slug=slug, status="active", sector="retail", palette={"name": "mizan"}))
        await db.commit()
    try:
        async with AsyncSessionLocal() as db:
            await bind_tenant(db, tid)
            for role in ("admin", "cashier"):
                u = User(id=uuid.uuid4(), tenant_id=tid, username=f"{role}-{tid.hex[:6]}", full_name=role, role=role,
                         password_hash=hash_password("x"))
                db.add(u)
                await db.flush()
                await set_access(db, u, role)
                tokens[role] = {"Authorization": f"Bearer {create_access_token({'sub': str(u.id), 'tid': str(tid)})}"}
            await db.commit()
        current_tenant_id.set(None)

        admin, cashier = tokens["admin"], tokens["cashier"]
        upload = {"file": ("acme.sunrise-1.0.0.mzm", theme_package(), "application/zip")}
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            # Everyone gets the workspace's theme; only the admin manages them.
            assert (await c.get("/themes/current", headers=cashier)).json()["id"] == "mizan"
            assert (await c.get("/themes", headers=cashier)).status_code == 403
            listed = (await c.get("/themes", headers=admin)).json()
            assert listed["current"] == "mizan" and {t["id"] for t in listed["items"]} >= {"mizan", "cobalt", "monokai"}
            assert (await c.put("/themes/current", headers=cashier, json={"id": "cobalt"})).status_code == 403
            assert (await c.put("/themes/current", headers=admin, json={"id": "nope"})).status_code == 404

            # A theme package: inspected, installed, chosen; its font is served.
            info = (await c.post("/themes/packages/inspect", files=upload, headers=admin)).json()
            assert info["id"] == "acme.sunrise" and info["developer"] == "acme" and info["files"] == ["assets/sunrise.woff2"]
            module = {"file": ("x.mzm", mzm.build(files(), *developer()), "application/zip")}
            refused = await c.post("/themes/packages/install", files=module, headers=admin)
            assert refused.status_code == 422 and "وحدة" in refused.json()["detail"]
            wrong_place = await c.post("/community/packages/inspect", files=upload, headers=admin)
            assert wrong_place.status_code == 422 and "مظهر" in wrong_place.json()["detail"]
            assert (await c.post("/themes/packages/install", files=upload, headers=admin)).status_code == 200
            chosen = (await c.put("/themes/current", headers=admin, json={"id": "acme.sunrise"})).json()
            assert chosen["id"] == "acme.sunrise" and chosen["assets_base"] == f"/themes/assets/{tid}/acme.sunrise/"
            assert (await c.get("/themes/current", headers=cashier)).json()["colors"]["light"]["primary"] == "oklch(0.55 0.17 40)"
            font = await c.get(f"/themes/assets/{tid}/acme.sunrise/assets/sunrise.woff2")  # public, no token
            assert font.status_code == 200 and font.content == FONT and font.headers["content-type"] == "font/woff2"
            assert (await c.get(f"/themes/assets/{uuid.uuid4()}/acme.sunrise/assets/sunrise.woff2")).status_code == 404
            resolved = (await c.get(f"/tenants/resolve/{slug}")).json()
            assert resolved["theme"]["id"] == "acme.sunrise"  # the login page shows it too
            from app.platform.themes.service import print_color

            async with AsyncSessionLocal() as db:
                await bind_tenant(db, tid)
                hexed = await print_color(db, await db.get(Tenant, tid))  # printed documents: the brand colour as hex
            current_tenant_id.set(None)
            assert hexed is not None and len(hexed) == 7 and hexed.startswith("#") and hexed != "#651e2c"

            # The current theme can't be removed; after switching back it can.
            assert (await c.delete("/themes/acme.sunrise", headers=admin)).status_code == 409
            await c.put("/themes/current", headers=admin, json={"id": "mizan"})
            assert (await c.delete("/themes/acme.sunrise", headers=admin)).status_code == 204
            assert "acme.sunrise" not in {t["id"] for t in (await c.get("/themes", headers=admin)).json()["items"]}
    finally:
        current_tenant_id.set(None)
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
            await db.commit()


def test_the_sdk_starts_themes_from_mizans_own_and_checks_them_the_same_way(tmp_path):
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    platform = json.loads((repo / "shared/backend/app/themes/mizan/theme.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(repo / "sdk/python"))
    try:
        from mizan_sdk.cli import theme_starter
        from mizan_sdk.package import build as sdk_build
        from mizan_sdk.themes import MIZAN
    finally:
        sys.path.pop(0)
    assert MIZAN == platform, "sdk/python/mizan_sdk/themes.py is out of date with app/themes/mizan/theme.json"
    from mizan_sdk.themes import MIZAN_COLORS

    palette = json.loads((repo / "shared/backend/app/themes/_palettes/mizan.json").read_text(encoding="utf-8"))
    assert MIZAN_COLORS == palette["colors"], "MIZAN_COLORS is out of date with _palettes/mizan.json"
    key, cert = developer()
    pkg = mzm.verify(sdk_build({"manifest.json": json.dumps(theme_starter("acme.dawn")).encode()}, key, cert))
    assert pkg.kind == "theme" and pkg.manifest["id"] == "acme.dawn"
