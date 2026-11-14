"""Owner accounts in the admin panel (#73): list, reset, disable, move, merge, delete."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db.base import AsyncSessionLocal
from app.platform.auth.models.owner import OwnerAccount
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password, verify_password
from app.platform.tenancy.models import Tenant
from main import app

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


async def _session():
    db = AsyncSessionLocal()
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    return db


async def make_owner(workspaces: int = 1) -> tuple[OwnerAccount, list[Tenant]]:
    db = await _session()
    try:
        tag = uuid.uuid4().hex[:8]
        owner = OwnerAccount(id=uuid.uuid4(), login=f"own-{tag}", full_name=f"Owner {tag}", password_hash=hash_password("secret123"))
        db.add(owner)
        await db.flush()
        tenants = []
        for i in range(workspaces):
            t = Tenant(id=uuid.uuid4(), name=f"WS {tag}-{i}", slug=f"ws-{tag}-{i}", plan="trial", owner_account_id=owner.id)
            db.add(t)
            await db.flush()
            db.add(User(id=uuid.uuid4(), tenant_id=t.id, username=f"own-{tag}-{i}", full_name="Owner", role="admin",
                        password_hash=owner.password_hash, owner_account_id=owner.id))
            tenants.append(t)
        await db.commit()
        return owner, tenants
    finally:
        await db.close()


async def admin_headers() -> dict:
    db = await _session()
    try:
        tag = uuid.uuid4().hex[:8]
        home = Tenant(id=uuid.uuid4(), name=f"Platform test {tag}", slug=f"plat-{tag}")
        db.add(home)
        await db.flush()
        user = User(id=uuid.uuid4(), tenant_id=home.id, username=f"plat-{tag}", full_name="Platform test", role="superadmin",
                    is_superadmin=True, password_hash=hash_password("x"))
        db.add(user)
        await db.commit()
        return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}
    finally:
        await db.close()


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_owners_are_listed_with_their_workspaces():
    owner, tenants = await make_owner(2)
    h = await admin_headers()
    async with client() as c:
        items = (await c.get("/admoon/owners", headers=h, params={"q": owner.login})).json()["items"]
        assert [(i["login"], i["workspace_count"]) for i in items] == [(owner.login, 2)]
        detail = (await c.get(f"/admoon/owners/{owner.id}", headers=h)).json()
        assert {w["id"] for w in detail["workspaces"]} == {str(t.id) for t in tenants}
        ws = (await c.get(f"/admoon/tenants/{tenants[0].id}", headers=h)).json()
        assert ws["owner_account"]["login"] == owner.login


async def test_reset_password_and_disable():
    owner, _ = await make_owner()
    h = await admin_headers()
    async with client() as c:
        r = (await c.post(f"/admoon/owners/{owner.id}/reset-password", headers=h)).json()
        password = r["password"]
        assert r["workspace_logins_updated"] == 1
        assert (await c.post(f"/admoon/owners/{owner.id}/active", headers=h, json={"active": False})).json()["is_active"] is False
    db = await _session()
    try:
        o = await db.get(OwnerAccount, owner.id)
        assert verify_password(password, o.password_hash) and not o.is_active and o.tokens_valid_after is not None
        # The workspace login takes the same password, as when the owner changes it (#71).
        u = await db.scalar(select(User).where(User.owner_account_id == owner.id))
        assert verify_password(password, u.password_hash)
    finally:
        await db.close()


async def test_send_reset_code_needs_a_verified_email(monkeypatch):
    from app.platform.notifications import service as mail

    sent = []

    async def fake_send(to_email, subject, html_content, attachments=None, text=None, reply_to=None):
        sent.append(to_email)
        return {"ok": True}

    monkeypatch.setattr(mail, "send_email", fake_send)
    monkeypatch.setattr(mail, "email_enabled", lambda: True)
    owner, _ = await make_owner()
    h = await admin_headers()
    async with client() as c:
        assert (await c.post(f"/admoon/owners/{owner.id}/send-reset-code", headers=h)).status_code == 409
        db = await _session()
        try:
            await db.execute(text("UPDATE owner_accounts SET email = 'adm-reset@example.com', email_verified_at = now() WHERE id = :o"),
                             {"o": owner.id})
            await db.commit()
        finally:
            await db.close()
        r = await c.post(f"/admoon/owners/{owner.id}/send-reset-code", headers=h)
        assert r.status_code == 200 and r.json()["sent_to"] == "a********@example.com" and sent == ["adm-reset@example.com"]
        detail = (await c.get(f"/admoon/owners/{owner.id}", headers=h)).json()
        assert detail["email_verified"] is True


async def test_move_merge_and_delete():
    a, a_ws = await make_owner(2)
    b, _ = await make_owner(1)
    h = await admin_headers()
    async with client() as c:
        # Move one of A's workspaces to B: A's link to its user there is removed.
        r = await c.post(f"/admoon/owners/{b.id}/workspaces", headers=h, json={"tenant_id": str(a_ws[0].id)})
        assert r.status_code == 200 and r.json()["workspace_count"] == 2
        # A still has a workspace: it can't be deleted, but it can be merged into B.
        assert (await c.delete(f"/admoon/owners/{a.id}", headers=h)).status_code == 409
        merged = (await c.post(f"/admoon/owners/{a.id}/merge", headers=h, json={"into": str(b.id)})).json()
        assert merged["workspace_count"] == 3
        assert (await c.get(f"/admoon/owners/{a.id}", headers=h)).status_code == 404
    db = await _session()
    try:
        moved_user = await db.scalar(text("SELECT owner_account_id FROM users WHERE tenant_id = :t"), {"t": a_ws[0].id})
        kept_user = await db.scalar(text("SELECT owner_account_id FROM users WHERE tenant_id = :t"), {"t": a_ws[1].id})
        assert moved_user is None and kept_user == b.id
    finally:
        await db.close()
    # An owner left without workspaces can be deleted.
    lonely, lonely_ws = await make_owner(1)
    db = await _session()
    try:
        await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": lonely_ws[0].id})
        await db.commit()
    finally:
        await db.close()
    async with client() as c:
        listed = (await c.get("/admoon/owners", headers=h, params={"without_workspaces": "true", "q": lonely.login})).json()["items"]
        assert [i["login"] for i in listed] == [lonely.login]
        assert (await c.delete(f"/admoon/owners/{lonely.id}", headers=h)).status_code == 204


async def test_only_platform_staff():
    async with client() as c:
        assert (await c.get("/admoon/owners")).status_code in (401, 403)
