"""A developer's activity running in a workspace (ADR-012, #107 part 2): published and approved in
the marketplace, chosen in an activity change, followed by its updates."""
import json
import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.base import AsyncSessionLocal
from app.framework import package as mzm
from app.framework import package_activities, screens, variants
from app.platform.tenancy import activity_change as changes
from app.platform.tenancy.context import unbind_tenant
from app.platform.tenancy.models import Tenant
from tests.test_activity_changes import ask, client, pharmacy_workspace
from tests.test_owners import admin_headers

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sdk/python"))


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


def developer(handle: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return raw, mzm.certify(handle, f"{handle}-k1", pub)


def activity_files(activity_id: str, version: str, extra_module: bool = False) -> dict[str, bytes]:
    from mizan_sdk.cli import activity_starter

    files = activity_starter(activity_id)
    files["manifest.json"]["version"] = version
    if extra_module:  # an update with a second module of its own
        dev, name = activity_id.split(".")
        mid = f"{dev}.{name}_notes"
        files["manifest.json"]["modules"].append(mid)
        files[f"modules/{mid}/manifest.json"] = {"id": mid, "name": "ملاحظات", "name_en": "Notes", "version": "0.1.0",
                                                 "kind": "community", "entities": ["note"],
                                                 "menu": [{"entity": "note", "label": "الملاحظات"}]}
        files[f"modules/{mid}/entities/note.json"] = {"id": "note", "name": "ملاحظة", "name_en": "Note", "title": "text",
                                                      "fields": [{"key": "text", "type": "text", "label": "النص", "required": True}]}
    return {k: json.dumps(v, ensure_ascii=False).encode() for k, v in files.items()}


async def submit(team, data: bytes) -> uuid.UUID:
    from app.platform.marketplace import listings

    async with AsyncSessionLocal() as db:
        v = await listings.submit(db, team, None, data)
        await db.commit()
        return v.id


async def test_a_developers_activity_runs_in_a_workspace():
    from app.platform.developers.models import DeveloperTeam

    handle = f"a{uuid.uuid4().hex[:7]}"
    aid = f"{handle}.laundry"
    orders, notes, theme = f"{handle}.laundry_orders", f"{handle}.laundry_notes", f"{handle}.laundry_fresh"
    key, cert = developer(handle)
    async with AsyncSessionLocal() as db:
        team = DeveloperTeam(handle=handle, name="Laundry devs")
        db.add(team)
        await db.commit()
        await db.refresh(team)
    owner, tenant = await pharmacy_workspace()
    other_owner, other = await pharmacy_workspace()
    h = await admin_headers()
    try:
        # Published and approved: reviewed like a module, then it can be chosen.
        v1 = await submit(team, mzm.build(activity_files(aid, "0.1.0"), key, cert))
        async with client() as c:
            detail = (await c.get(f"/admoon/marketplace/submissions/{v1}", headers=h)).json()
            a = detail["activity"]
            assert a["family"] == "services" and {m["id"] for m in a["own_modules"]} == {orders}
            assert {m["id"] for m in a["modules"]} >= {"pos", "inventory"} and a["themes"][0]["id"] == theme
            assert detail["workspaces"] == 0
            r = await c.post(f"/admoon/marketplace/submissions/{v1}/approve", headers=h, json={})
            assert r.status_code == 200, r.text
        d = package_activities.get(aid)
        assert d and d.listed and d.version == "0.1.0"
        # Not in the store's install list: activities are switched to.
        from app.platform.marketplace import listings

        async with AsyncSessionLocal() as db:
            assert all(i["id"] != aid for i in await listings.store(db))

        # The owner asks; the preview shows its own modules and what they may access.
        async with AsyncSessionLocal() as db:
            t = await db.get(Tenant, tenant.id)
            p = await changes.preview(db, t, aid)
            await db.rollback()
            await unbind_tenant(db)  # as the owner API does after a preview
        assert p["to"]["name"] == "نشاطي" and p["package"]["developer"] == handle
        assert p["own_joining"][0]["id"] == orders and p["own_joining"][0]["scopes"][0]["id"] == "customers:read"
        assert "pharmacy" in {m["id"] for m in p["leaving"]}
        change_id = await ask(tenant.id, owner.id, aid)
        async with client() as c:
            r = await c.post(f"/admoon/activity-changes/{change_id}/approve", headers=h, json={})
            assert r.status_code == 200, r.text
            assert r.json()["result"]["own_added"] == [orders]

        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            t = await db.get(Tenant, tenant.id)
            assert t.sector == aid and "pharmacy" not in t.active_modules and "pos" in t.active_modules
            mods = dict((await db.execute(text("SELECT module_id, status FROM community_modules WHERE tenant_id = :t"),
                                          {"t": tenant.id})).all())
            assert mods == {orders: "active"}
            themes = (await db.execute(text("SELECT theme_id FROM workspace_themes WHERE tenant_id = :t"), {"t": tenant.id})).scalars().all()
            assert themes == [theme]

        # What the workspace runs is read from the package: variants, terms, menus, positions.
        assert variants.variant_of("pos", aid) == aid and variants.terms_for(aid)["item"] == "قطعة"
        from app.framework.fields import variant_fields

        assert any(f["key"] == "pickup_date" for f in variant_fields("sale", aid))
        own_screen = {f"{orders}/order": {"id": f"{orders}.order", "path": f"/x/{orders}/order", "label": "طلبات العملاء",
                                          "icon": None, "module": orders}}
        menu = screens.resolve(None, aid, None, frozenset({"pos.sell", "sales.view"}), t.active_modules, own_screen)["menu"]
        assert any(i["path"] == f"/x/{orders}/order" for g in menu for i in g["items"])
        from app.platform.permissions.positions import activity_of, declared_positions

        assert activity_of(aid) == aid and declared_positions()[aid][0]["code"] == "counter_clerk"

        # An update reaches the workspace: its new module joins, nothing leaves.
        v2 = await submit(team, mzm.build(activity_files(aid, "0.2.0", extra_module=True), key, cert))
        async with client() as c:
            detail = (await c.get(f"/admoon/marketplace/submissions/{v2}", headers=h)).json()
            assert detail["workspaces"] == 1
            r = await c.post(f"/admoon/marketplace/submissions/{v2}/approve", headers=h, json={})
            assert r.json()["workspaces_updated"] == 1
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            mods = set((await db.execute(text("SELECT module_id FROM community_modules WHERE tenant_id = :t AND status = 'active'"),
                                         {"t": tenant.id})).scalars())
            assert mods == {orders, notes}

        # Delisted: no new switches; the workspace on it keeps running it.
        async with client() as c:
            assert (await c.post(f"/admoon/marketplace/items/{aid}/delist", headers=h, json={"note": "test"})).status_code == 200
        async with AsyncSessionLocal() as db:
            with pytest.raises(Exception):
                changes.check_target(await db.get(Tenant, other.id), aid)
        assert package_activities.get(aid) is not None and variants.variant_of("pos", aid) == aid

        # Switching away removes its own modules; their records stay hidden.
        back = await ask(tenant.id, owner.id, "pharmacy")
        async with client() as c:
            assert (await c.post(f"/admoon/activity-changes/{back}/approve", headers=h, json={})).status_code == 200
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            assert set((await db.execute(text("SELECT status FROM community_modules WHERE tenant_id = :t"),
                                         {"t": tenant.id})).scalars()) == {"removed"}
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            for t in (tenant, other):
                await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": t.id})
            await db.execute(text("DELETE FROM owner_accounts WHERE id IN (:a, :b)"), {"a": owner.id, "b": other_owner.id})
            await db.execute(text("DELETE FROM org_positions WHERE activity = :a"), {"a": aid})
            await db.execute(text("DELETE FROM marketplace_items WHERE id = :i"), {"i": aid})
            await db.execute(text("DELETE FROM marketplace_versions WHERE item_id = :i"), {"i": aid})
            await db.execute(text("DELETE FROM developer_teams WHERE handle = :h"), {"h": handle})
            await db.commit()
        await package_activities.refresh(force=True)
