"""Workspace branding profiles: tenant-scoped auto-sync, named saves, apply and delete.

Profiles live inside the workspace itself (not an owner-account library), so the same
behavior holds on cloud, desktop and LAN installs. The Settings > Themes routes
(/themes/profiles) are thin wrappers over this service.
"""
import os
import uuid as _uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text as sql_text

from app.db.base import AsyncSessionLocal
from app.platform.tenancy.models import Tenant
from app.platform.themes import service as themes
from tests.test_owner_api import fresh_engine, make_owner  # noqa: F401 - autouse engine fixture + factory

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


async def _tenant(tenant_id):
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
        return await db.get(Tenant, tenant_id)


async def _edit(tenant_id, theme_id, **kw):
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
        t = await db.get(Tenant, tenant_id)
        return await themes.choose(db, t, theme_id, **kw)


async def _profiles(tenant_id):
    t = await _tenant(tenant_id)
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
        db.add(t)
        return await themes.profiles(db, t)


async def test_theme_edit_syncs_workspace_auto_profile():
    """The owner's rule: editing the theme pack automatically keeps a branding profile
    with the modifications - one per workspace, updated in place, saved inside the
    workspace itself; the pack is untouched."""
    owner, tenant, user = await make_owner()

    # No edits yet: no automatic profile exists.
    assert await _profiles(tenant.id) == []

    await _edit(tenant.id, "tangerine", palette_id="grape", fonts={"body": "Cairo", "display": "Almarai"})
    items = await _profiles(tenant.id)
    assert len(items) == 1
    auto = items[0]
    assert auto["name"] == f"{tenant.name} — هوية مخصصة"
    assert auto["theme"] == "tangerine" and auto["palette"] == "grape"
    assert auto["fonts"] == {"body": "Cairo", "display": "Almarai"}

    # A further edit updates the same profile in place (no duplicate rows).
    await _edit(tenant.id, "tangerine", palette_id="olive")
    items = await _profiles(tenant.id)
    assert len(items) == 1 and items[0]["id"] == auto["id"] and items[0]["palette"] == "olive"

    # A no-op choice changes nothing and creates nothing.
    await _edit(tenant.id, "tangerine", palette_id="olive")
    assert len(await _profiles(tenant.id)) == 1

    # The original theme pack is untouched by the override.
    assert themes.file_themes()["tangerine"]["colors"]["light"]["primary"] == "#e8590c"


async def test_named_save_apply_and_delete_are_workspace_scoped():
    owner, tenant, user = await make_owner()
    owner_b, tenant_b, _ = await make_owner()

    await _edit(tenant.id, "tangerine", palette_id="grape", fonts={"body": "Cairo", "display": "Almarai"})

    # Save the workspace's current branding under a name; a duplicate name is refused.
    t = await _tenant(tenant.id)
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
        db.add(t)
        saved = await themes.save_profile(db, t, "هوية المتجر")
        assert saved["theme"] == "tangerine" and saved["palette"] == "grape"
        assert saved["fonts"] == {"body": "Cairo", "display": "Almarai"}
        with pytest.raises(HTTPException) as ei:
            await themes.save_profile(db, t, "هوية المتجر")
        assert ei.value.status_code == 409

    names = {p["name"] for p in await _profiles(tenant.id)}
    assert names == {f"{tenant.name} — هوية مخصصة", "هوية المتجر"}

    # Applying a profile recolors the workspace independently.
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
        db.add(t)
        out = await themes.apply_profile(db, t, _uuid.UUID(saved["id"]))
        assert out["id"] == "tangerine" and out["palette"] == "grape"
        assert out["colors"]["light"]["primary"] == "#be4bdb"
        assert out["fonts"]["body"] == "Cairo"
        await db.commit()

    # Another workspace's profile does not exist from here: apply, delete and list.
    tb = await _tenant(tenant_b.id)
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
        db.add(tb)
        with pytest.raises(HTTPException) as ei:
            await themes.apply_profile(db, tb, _uuid.UUID(saved["id"]))
        assert ei.value.status_code == 404
        with pytest.raises(HTTPException) as ei:
            await themes.delete_profile(db, tb, _uuid.UUID(saved["id"]))
        assert ei.value.status_code == 404
        assert await themes.profiles(db, tb) == []

    # Deleting works in the owning workspace and is then gone.
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
        db.add(t)
        await themes.delete_profile(db, t, _uuid.UUID(saved["id"]))
    assert [p["name"] for p in await _profiles(tenant.id)] == [f"{tenant.name} — هوية مخصصة"]

    # An unknown id is the same 404 as another workspace's.
    async with AsyncSessionLocal() as db:
        await db.execute(sql_text("SELECT set_config('app.bypass', 'on', true)"))
        db.add(t)
        with pytest.raises(HTTPException) as ei:
            await themes.apply_profile(db, t, _uuid.uuid4())
        assert ei.value.status_code == 404
