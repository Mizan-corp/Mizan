"""Owner branding profiles: owner-scoped CRUD and apply, with cross-owner denial."""
import os

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from tests.test_owner_api import client, fresh_engine, login, make_owner  # noqa: F401 - helpers + autouse engine fixture

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


async def test_create_list_validate_and_duplicate():
    owner, tenant, user = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        bad = await c.post("/account/branding-profiles", json={"name": "هوية", "theme": "nope"}, headers=h)
        assert bad.status_code == 422
        bad = await c.post("/account/branding-profiles", json={"name": "هوية", "theme": "mizan", "palette": "nope"}, headers=h)
        assert bad.status_code == 422
        bad = await c.post("/account/branding-profiles", json={"name": "هوية", "theme": "mizan", "fonts": {"body": "Comic Sans"}}, headers=h)
        assert bad.status_code == 422
        r = await c.post("/account/branding-profiles",
                         json={"name": "هوية المتجر", "theme": "tangerine", "palette": "grape",
                               "fonts": {"body": "Cairo", "display": "Almarai"}}, headers=h)
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        dupe = await c.post("/account/branding-profiles", json={"name": "هوية المتجر", "theme": "mizan"}, headers=h)
        assert dupe.status_code == 409
        items = (await c.get("/account/branding-profiles", headers=h)).json()["items"]
        assert [p["id"] for p in items] == [pid]
        assert items[0]["palette"] == "grape" and items[0]["fonts"]["body"] == "Cairo"


async def test_apply_recolors_own_workspace_independently():
    owner, tenant, user = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        pid = (await c.post("/account/branding-profiles",
                            json={"name": "زيتي", "theme": "tangerine", "palette": "grape",
                                  "fonts": {"body": "Cairo", "display": "Almarai"}}, headers=h)).json()["id"]
        r = await c.post(f"/account/branding-profiles/{pid}/apply/{tenant.id}", headers=h)
        assert r.status_code == 200, r.text
        theme = r.json()["theme"]
        # Independent recolor: still the tangerine theme, grape's colors, picked fonts.
        assert theme["id"] == "tangerine"
        assert theme["palette"] == "grape"
        assert theme["colors"]["light"]["primary"] == "#be4bdb"
        assert theme["fonts"]["body"] == "Cairo"
        from app.db.base import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            row = (await db.execute(text("SELECT palette FROM tenants WHERE id = :t"), {"t": tenant.id})).first()
            assert row[0]["name"] == "tangerine" and row[0]["palette"] == "grape"


async def test_other_owner_cannot_see_apply_or_delete():
    owner_a, tenant_a, _ = await make_owner()
    owner_b, tenant_b, _ = await make_owner()
    async with client() as c:
        ha = await login(c, owner_a)
        hb = await login(c, owner_b)
        pid = (await c.post("/account/branding-profiles", json={"name": "سرية", "theme": "mizan"}, headers=ha)).json()["id"]
        # B's list stays empty; A's profile is invisible to B.
        assert (await c.get("/account/branding-profiles", headers=hb)).json()["items"] == []
        # B cannot apply A's profile anywhere, and A cannot apply to B's workspace.
        assert (await c.post(f"/account/branding-profiles/{pid}/apply/{tenant_b.id}", headers=hb)).status_code == 404
        assert (await c.post(f"/account/branding-profiles/{pid}/apply/{tenant_b.id}", headers=ha)).status_code == 404
        assert (await c.delete(f"/account/branding-profiles/{pid}", headers=hb)).status_code == 404
        # A's own apply works and B's workspace keeps its default palette.
        assert (await c.post(f"/account/branding-profiles/{pid}/apply/{tenant_a.id}", headers=ha)).status_code == 200
        assert (await c.delete(f"/account/branding-profiles/{pid}", headers=ha)).status_code == 204


async def test_theme_edit_syncs_private_auto_profile():
    """The owner's rule: editing the theme pack automatically keeps a branding profile
    with the modifications - one per workspace, updated in place, private to the owner,
    reusable in his other workspaces from Settings > Themes; the pack is untouched."""
    import uuid as _uuid

    from fastapi import HTTPException
    from sqlalchemy import text as sql_text

    from app.db.base import AsyncSessionLocal
    from app.platform.tenancy.models import Tenant
    from app.platform.themes import service as themes

    owner, tenant, user = await make_owner()

    async def edit(theme_id, **kw):
        async with AsyncSessionLocal() as db:
            await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
            t = await db.get(Tenant, tenant.id)
            return await themes.choose(db, t, theme_id, **kw)

    async with client() as c:
        h = await login(c, owner)
        # No edits yet: no automatic profile exists.
        assert (await c.get("/account/branding-profiles", headers=h)).json()["items"] == []

        await edit("tangerine", palette_id="grape", fonts={"body": "Cairo", "display": "Almarai"})
        items = (await c.get("/account/branding-profiles", headers=h)).json()["items"]
        assert len(items) == 1
        auto = items[0]
        assert auto["name"] == f"{tenant.name} — هوية مخصصة"
        assert auto["theme"] == "tangerine" and auto["palette"] == "grape"
        assert auto["fonts"] == {"body": "Cairo", "display": "Almarai"}

        # A further edit updates the same profile in place (no duplicate rows).
        await edit("tangerine", palette_id="olive")
        items = (await c.get("/account/branding-profiles", headers=h)).json()["items"]
        assert len(items) == 1 and items[0]["id"] == auto["id"] and items[0]["palette"] == "olive"

        # A no-op choice changes nothing and creates nothing.
        await edit("tangerine", palette_id="olive")
        assert len((await c.get("/account/branding-profiles", headers=h)).json()["items"]) == 1

        # The original theme pack is untouched by the override.
        assert themes.file_themes()["tangerine"]["colors"]["light"]["primary"] == "#e8590c"

        # The same owner's second workspace can apply the profile (Settings > Themes path);
        # applying there starts that workspace's own automatic profile too.
        async with AsyncSessionLocal() as db:
            await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
            t2 = Tenant(id=_uuid.uuid4(), name=f"Second WS {tenant.id.hex[:4]}",
                        slug=f"second-{tenant.id.hex[:8]}", plan="trial", owner_account_id=owner.id)
            db.add(t2)
            await db.flush()
            out = await themes.apply_owner_profile(db, t2, _uuid.UUID(auto["id"]))
            assert out["palette"] == "olive"
            await db.commit()
        items = (await c.get("/account/branding-profiles", headers=h)).json()["items"]
        assert len(items) == 2
        assert {p["name"] for p in items} == {auto["name"], f"{t2.name} — هوية مخصصة"}

        # Another owner's profile does not exist from this workspace (404), and the
        # other owner never sees these profiles.
        other, tenant_b, _ = await make_owner()
        async with AsyncSessionLocal() as db:
            await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
            t3 = await db.get(Tenant, tenant_b.id)
            with __import__("pytest").raises(HTTPException) as ei:
                await themes.apply_owner_profile(db, t3, _uuid.UUID(auto["id"]))
            assert ei.value.status_code == 404
        hb = await login(c, other)
        assert (await c.get("/account/branding-profiles", headers=hb)).json()["items"] == []
