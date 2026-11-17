"""Store settings never cross workspaces, and need a sign-in.

Without a sign-in no workspace is bound and the login role bypasses RLS, so `GET /settings` used to
return every workspace's settings merged, and the API's PWA manifest whichever workspace's name came
first. The settings now need a sign-in and the manifest serves Mizan's own branding.
"""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app
from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from app.platform.tenancy.models import Tenant

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _workspace(name: str) -> dict:
    tid, uid = uuid.uuid4(), uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=tid, name=name, slug=f"set-{tid.hex[:10]}", status="active"))
        await s.flush()
        s.add(User(id=uid, tenant_id=tid, username=f"set_{tid.hex[:8]}", full_name="مالك", role="admin",
                   password_hash=hash_password("Pass123!"), permissions=["settings"], is_active=True))
        await s.commit()
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, tid)
        await s.execute(text("INSERT INTO store_settings (id, tenant_id, key, value) VALUES (:i, :t, 'store_name', :n)"),
                        {"i": uuid.uuid4(), "t": tid, "n": name})
        await s.commit()
    current_tenant_id.set(None)
    token = create_access_token({"sub": str(uid), "role": "admin", "username": f"set_{tid.hex[:8]}", "tid": str(tid)})
    return {"id": tid, "name": name, "headers": {"Authorization": f"Bearer {token}"}}


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_settings_need_a_sign_in_and_show_only_the_own_workspace():
    a = await _workspace(f"متجر أ {uuid.uuid4().hex[:6]}")
    b = await _workspace(f"متجر ب {uuid.uuid4().hex[:6]}")
    async with _client() as c:
        anonymous = await c.get("/settings")
        assert anonymous.status_code == 401
        assert a["name"] not in anonymous.text and b["name"] not in anonymous.text

        mine = await c.get("/settings", headers=a["headers"])
        assert mine.status_code == 200 and mine.json()["store_name"] == a["name"]
        assert b["name"] not in mine.text
        theirs = await c.get("/settings", headers=b["headers"])
        assert theirs.json()["store_name"] == b["name"] and a["name"] not in theirs.text


async def test_the_api_manifest_shows_no_workspace_without_a_sign_in():
    a = await _workspace(f"متجر ج {uuid.uuid4().hex[:6]}")
    async with _client() as c:
        r = await c.get("/settings/manifest.json")
    assert r.status_code == 200 and r.json()["name"] == "ميزان"
    assert a["name"] not in r.text
