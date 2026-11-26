"""The marketplace store in a workspace's module centre (#105): browse, details, install."""
import os
import uuid

import pytest

import main  # noqa: F401
from app.framework import package as mzm
import json

from tests.test_community_packages import MANIFEST, VISIT, developer, files

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


async def test_browse_and_install_a_listed_module():
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text

    from app.db.base import AsyncSessionLocal
    from app.platform.auth.models.user import User
    from app.platform.auth.security import create_access_token, hash_password
    from app.platform.developers.models import DeveloperTeam
    from app.platform.marketplace import listings
    from app.platform.permissions.access import set_access
    from app.platform.tenancy.context import bind_tenant, current_tenant_id
    from app.platform.tenancy.models import Tenant

    handle = f"s{uuid.uuid4().hex[:8]}"
    item_id = f"{handle}.visits"
    key, cert = developer(handle)
    rename = lambda d: json.loads(json.dumps(d).replace("acme.", f"{handle}."))  # noqa: E731
    data = mzm.build(files(rename(MANIFEST), rename(VISIT)), key, cert)
    async with AsyncSessionLocal() as db:
        team = DeveloperTeam(handle=handle, name="فريق")
        db.add(team)
        await db.flush()
        v = await listings.submit(db, team, None, data)
        await listings.approve(db, v, uuid.uuid4())
        await db.commit()

    tid = uuid.uuid4()
    tokens = {}
    async with AsyncSessionLocal() as db:
        db.add(Tenant(id=tid, name=f"Store {tid.hex[:6]}", slug=f"store-{tid.hex[:8]}", status="active"))
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
                tokens[role] = create_access_token({"sub": str(u.id), "tid": str(tid)})
            await db.commit()
        current_tenant_id.set(None)

        admin = {"Authorization": f"Bearer {tokens['admin']}"}
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            assert (await c.get("/modules/store", headers={"Authorization": f"Bearer {tokens['cashier']}"})).status_code == 403
            items = (await c.get("/modules/store", headers=admin, params={"kind": "community"})).json()["items"]
            mine = next(i for i in items if i["id"] == item_id)
            assert mine["developer"] == handle and mine["installed_version"] is None and mine["version"] == "1.0.0"

            detail = (await c.get(f"/modules/store/{item_id}", headers=admin)).json()
            scopes = [s["id"] for s in detail["detail"]["scopes"]]
            assert scopes and detail["item"]["id"] == item_id

            r = await c.post(f"/modules/store/{item_id}/install", headers=admin, json={"approved_scopes": scopes})
            assert r.status_code == 200, r.text
            after = (await c.get("/modules/store", headers=admin)).json()["items"]
            assert next(i for i in after if i["id"] == item_id)["installed_version"] == "1.0.0"
            assert (await c.post("/modules/store/nobody.nothing/install", headers=admin, json={})).status_code == 404

        async with AsyncSessionLocal() as db:
            assert await db.scalar(text("SELECT installs FROM marketplace_items WHERE id = :i"), {"i": item_id}) == 1
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
            await db.execute(text("DELETE FROM marketplace_items WHERE id = :i"), {"i": item_id})
            await db.execute(text("DELETE FROM marketplace_versions WHERE item_id = :i"), {"i": item_id})
            await db.execute(text("DELETE FROM developer_teams WHERE handle = :h"), {"h": handle})
            await db.commit()
