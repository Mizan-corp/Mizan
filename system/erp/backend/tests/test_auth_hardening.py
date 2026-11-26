"""Sign-in and error handling that every module relies on.

- Only ERP sessions open the ERP: a print, owner or developer token is refused by normal routes.
- A token without a workspace no longer leaves the RLS bypass on: the user's own workspace is bound,
  and raw SQL sees only it.
- A token whose workspace isn't the user's own is refused.
- A 500 never carries the exception's text (database errors carry the SQL and its values).
- PUT /permissions/{id}: no privilege escalation, every declared permission can be granted.
"""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from starlette.requests import Request

from main import app
from app.db.base import AsyncSessionLocal
from app.dependencies import get_current_user
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password
from app.platform.permissions.roles import standard_permissions
from app.platform.tenancy.context import current_tenant_id
from app.platform.tenancy.models import Tenant
from tests.conftest import give_roles

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _workspace(roles=("admin",)) -> dict:
    tid = uuid.uuid4()
    current_tenant_id.set(None)
    users = {}
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=tid, name=f"Auth {tid.hex[:6]}", slug=f"auth-{tid.hex[:10]}", status="active"))
        await s.flush()
        for role in roles:
            u = User(id=uuid.uuid4(), tenant_id=tid, username=f"{role}_{tid.hex[:8]}", full_name=role, role=role,
                     password_hash=hash_password("Pass12345!"), permissions=standard_permissions(role), is_active=True)
            s.add(u)
            users[role] = u
        await give_roles(s)
        await s.commit()
    return {"id": tid, "users": users}


def _token(user: User, **extra) -> str:
    claims = {"sub": str(user.id), "role": user.role, "username": user.username, "tid": str(user.tenant_id)}
    claims.update(extra)
    return create_access_token({k: v for k, v in claims.items() if v is not ...})


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/x", "headers": [], "query_string": b""})


async def test_scoped_tokens_are_refused_by_normal_routes():
    ws = await _workspace()
    admin = ws["users"]["admin"]
    async with _client() as c:
        assert (await c.get("/auth/me", headers={"Authorization": f"Bearer {_token(admin)}"})).status_code == 200
        for scope in ("print", "owner", "developer"):
            r = await c.get("/auth/me", headers={"Authorization": f"Bearer {_token(admin, scope=scope)}"})
            assert r.status_code == 401, scope


async def test_a_token_without_a_workspace_binds_the_users_own_and_drops_the_bypass():
    a, b = await _workspace(), await _workspace()
    user = a["users"]["admin"]
    async with AsyncSessionLocal() as db:
        got = await get_current_user(_request(), _token(user, tid=...), db)
        assert got.id == user.id
        bypass = await db.scalar(text("SELECT current_setting('app.bypass', true)"))
        seen = set((await db.execute(text("SELECT DISTINCT tenant_id FROM users"))).scalars().all())
    assert bypass in (None, "", "off")
    assert seen == {a["id"]} and b["id"] not in seen


async def test_a_token_for_another_workspace_is_refused():
    a, b = await _workspace(), await _workspace()
    user = a["users"]["admin"]
    async with AsyncSessionLocal() as db:
        with pytest.raises(Exception) as e:
            await get_current_user(_request(), _token(user, tid=str(b["id"])), db)
    assert getattr(e.value, "status_code", None) == 401


async def test_a_server_error_carries_no_exception_text():
    secret = "postgresql://mizan:hunter2@db/secret-table"

    async def boom():
        raise RuntimeError(secret)

    path = f"/__boom_{uuid.uuid4().hex[:8]}"
    app.add_api_route(path, boom, methods=["GET"])
    try:
        async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as c:
            r = await c.get(path)
    finally:
        app.router.routes = [rt for rt in app.router.routes if getattr(rt, "path", None) != path]
    assert r.status_code == 500
    assert secret not in r.text and "hunter2" not in r.text and "RuntimeError" not in r.text


async def test_permissions_can_not_be_escalated():
    ws = await _workspace(roles=("admin", "manager", "cashier"))
    admin, manager, cashier = (ws["users"][r] for r in ("admin", "manager", "cashier"))
    # A user who may manage users but holds only a few permissions.
    async with _client() as c:
        h_admin = {"Authorization": f"Bearer {_token(admin)}"}
        r = await c.put(f"/permissions/{manager.id}", headers=h_admin, json={"permissions": ["users", "pos", "sales"], "is_manager": False})
        assert r.status_code == 200, r.text
        h_mgr = {"Authorization": f"Bearer {_token(manager)}"}
        # The standard cashier role holds permissions the manager now lacks (customers, shifts…), so the
        # manager can't change it until the admin narrows it to what the manager holds.
        r = await c.put(f"/permissions/{cashier.id}", headers=h_mgr, json={"permissions": ["pos"], "is_manager": False})
        assert r.status_code == 403
        r = await c.put(f"/permissions/{cashier.id}", headers=h_admin, json={"permissions": ["pos"], "is_manager": False})
        assert r.status_code == 200, r.text

        # Granting what they don't hold, to someone else or to themselves: refused.
        for target, perms in ((cashier, ["admin"]), (cashier, ["finance"]), (manager, ["admin", "users"])):
            r = await c.put(f"/permissions/{target.id}", headers=h_mgr, json={"permissions": perms, "is_manager": False})
            assert r.status_code == 403, (target.role, perms, r.text)
        # Changing the access of someone above them (the admin): refused.
        r = await c.put(f"/permissions/{admin.id}", headers=h_mgr, json={"permissions": ["pos"], "is_manager": False})
        assert r.status_code == 403
        # Setting the manager flag without being a manager or admin: refused.
        r = await c.put(f"/permissions/{cashier.id}", headers=h_mgr, json={"permissions": ["pos"], "is_manager": True})
        assert r.status_code == 403
        # Within their own permissions: allowed.
        r = await c.put(f"/permissions/{cashier.id}", headers=h_mgr, json={"permissions": ["pos", "sales"], "is_manager": False})
        assert r.status_code == 200, r.text
        got = (await c.get(f"/permissions/{cashier.id}", headers=h_admin)).json()
        assert got["permissions"] == ["pos", "sales"] and got["is_manager"] is False

        # The admin can grant any declared permission (accounting:view used to be refused with 422)...
        r = await c.put(f"/permissions/{cashier.id}", headers=h_admin,
                        json={"permissions": ["pos", "accounting:view", "purchases"], "is_manager": True})
        assert r.status_code == 200, r.text
        # ...but not an unknown one.
        r = await c.put(f"/permissions/{cashier.id}", headers=h_admin, json={"permissions": ["god_mode"], "is_manager": False})
        assert r.status_code == 400
