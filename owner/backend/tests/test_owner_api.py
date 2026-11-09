"""Owner API: sign-in, isolation between owners, checkout and the Paymob callback."""
import hashlib
import hmac
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import AsyncSessionLocal
from app.models.owner import OwnerAccount
from app.models.tenant import Tenant
from app.models.user import User
from app.services import paymob
from main import app

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

HMAC_SECRET = "test-hmac-secret"


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
def paymob_keys(monkeypatch):
    monkeypatch.setattr(settings, "PAYMOB_SECRET_KEY", "sk_test")
    monkeypatch.setattr(settings, "PAYMOB_PUBLIC_KEY", "pk_test")
    monkeypatch.setattr(settings, "PAYMOB_HMAC_SECRET", HMAC_SECRET)
    monkeypatch.setattr(settings, "PAYMOB_INTEGRATION_IDS", "111")

    async def fake_checkout(invoice, tenant, owner):
        return {"checkout_url": f"https://paymob.test/checkout/{invoice.invoice_ref}", "intention_id": "pi_x", "order_id": 42}

    monkeypatch.setattr(paymob, "create_checkout", fake_checkout)


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def erp_login_client() -> AsyncClient:
    """Owners sign in on the app's /login; that endpoint lives in the shared kernel."""
    from fastapi import FastAPI

    from app.api.routers import owner_login

    erp = FastAPI()
    erp.include_router(owner_login.router)
    erp.dependency_overrides[owner_login.login_limiter] = lambda: None  # tests sign in many times
    return AsyncClient(transport=ASGITransport(app=erp), base_url="http://test")


async def make_owner(password: str = "secret123") -> tuple[OwnerAccount, Tenant, User]:
    """An owner with one trial workspace and its admin user."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        tag = uuid.uuid4().hex[:8]
        owner = OwnerAccount(id=uuid.uuid4(), login=f"own-{tag}", full_name="Test Owner", password_hash=hash_password(password))
        db.add(owner)
        await db.flush()
        tenant = Tenant(id=uuid.uuid4(), name=f"Owner WS {tag}", slug=f"owner-ws-{tag}", plan="trial", owner_account_id=owner.id)
        db.add(tenant)
        await db.flush()
        user = User(id=uuid.uuid4(), tenant_id=tenant.id, username=f"own-{tag}", full_name="Test Owner", role="admin",
                    permissions=["*"], password_hash=owner.password_hash, owner_account_id=owner.id)
        db.add(user)
        await db.commit()
        return owner, tenant, user


def sign(obj: dict, secret: str = HMAC_SECRET) -> str:
    def get(o, k):
        for part in k.split("."):
            o = o.get(part) if isinstance(o, dict) else None
        return o

    def txt(v):
        return ("true" if v else "false") if isinstance(v, bool) else ("" if v is None else str(v))

    msg = "".join(txt(get(obj, f)) for f in paymob.HMAC_FIELDS)
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha512).hexdigest()


def txn(ref: str, cents: int, txn_id: int, **kw) -> dict:
    obj = {
        "id": txn_id, "amount_cents": cents, "created_at": "2026-11-09T10:00:00", "currency": "EGP",
        "error_occured": False, "has_parent_transaction": False, "integration_id": 111, "is_3d_secure": True,
        "is_auth": False, "is_capture": False, "is_refunded": False, "is_standalone_payment": True, "is_voided": False,
        "order": {"id": 42, "merchant_order_id": ref}, "owner": 1, "pending": False,
        "source_data": {"pan": "2346", "sub_type": "MasterCard", "type": "card"}, "success": True,
    }
    obj.update(kw)
    return obj


async def login(c: AsyncClient, owner: OwnerAccount, password: str = "secret123") -> dict:
    async with erp_login_client() as erp:
        r = await erp.post("/account/login", json={"login": owner.login.upper(), "password": password})
    assert r.status_code == 200 and "access_token" in r.json(), r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_hmac_matches_paymob_field_order(monkeypatch):
    monkeypatch.setattr(settings, "PAYMOB_HMAC_SECRET", HMAC_SECRET)
    obj = txn("INV-1", 45000, 1)
    assert paymob.verify_hmac(obj, sign(obj))
    assert paymob.verify_hmac(obj, sign(obj).upper())
    assert not paymob.verify_hmac(obj, sign(obj, "other"))
    assert not paymob.verify_hmac({**obj, "amount_cents": 1}, sign(obj))
    assert not paymob.verify_hmac(obj, None)


async def test_sign_in_and_token_scopes():
    owner, tenant, user = await make_owner()
    async with erp_login_client() as erp:
        assert (await erp.post("/account/login", json={"login": owner.login, "password": "nope"})).status_code == 401
    async with client() as c:
        assert (await c.post("/account/login", json={"login": owner.login, "password": "secret123"})).status_code in (404, 405)
        h = await login(c, owner)
        assert (await c.get("/account/me", headers=h)).json()["login"] == owner.login
        # An ERP token isn't an owner session.
        erp = create_access_token({"sub": str(user.id), "tid": str(tenant.id)})
        assert (await c.get("/account/me", headers={"Authorization": f"Bearer {erp}"})).status_code == 401


async def test_employees_are_sent_to_their_workspace_login():
    _, tenant, _ = await make_owner()
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        name = f"cashier-{uuid.uuid4().hex[:8]}"
        db.add(User(id=uuid.uuid4(), tenant_id=tenant.id, username=name, full_name="Cashier", role="cashier",
                    password_hash=hash_password("cashier123")))
        await db.commit()
    async with erp_login_client() as erp:
        r = await erp.post("/account/login", json={"login": name, "password": "cashier123"})
        assert r.json() == {"employee_workspace": tenant.slug}
        # A wrong password reveals nothing.
        assert (await erp.post("/account/login", json={"login": name, "password": "nope"})).status_code == 401


async def test_owner_token_is_refused_by_the_erp():
    from app.dependencies import get_current_user
    from fastapi import HTTPException
    from starlette.requests import Request

    owner, _, _ = await make_owner()
    token = create_access_token({"sub": str(owner.id), "scope": "owner"})
    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as e:
            await get_current_user(Request({"type": "http", "headers": []}), token, db)
        assert e.value.status_code == 401


async def test_owners_only_see_their_own_workspaces():
    a, ta, _ = await make_owner()
    b, tb, _ = await make_owner()
    async with client() as c:
        ha = await login(c, a)
        ids = [w["id"] for w in (await c.get("/account/workspaces", headers=ha)).json()["items"]]
        assert ids == [str(ta.id)]
        for path in (f"/account/workspaces/{tb.id}", ):
            assert (await c.get(path, headers=ha)).status_code == 404
        assert (await c.post(f"/account/workspaces/{tb.id}/open", headers=ha)).status_code == 404
        assert (await c.post(f"/account/workspaces/{tb.id}/checkout", headers=ha, json={"plan": "pro"})).status_code == 404


async def test_open_hands_over_an_erp_session_for_the_owners_user():
    owner, tenant, user = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        r = await c.post(f"/account/workspaces/{tenant.id}/open", headers=h)
        assert r.status_code == 200
        from app.core.security import decode_token

        claims = decode_token(r.json()["access_token"])
        assert claims["sub"] == str(user.id) and claims["tid"] == str(tenant.id) and "scope" not in claims


async def test_checkout_and_callback():
    owner, tenant, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        r = await c.post(f"/account/workspaces/{tenant.id}/checkout", headers=h, json={"plan": "pro", "cycle": "monthly"})
        assert r.status_code == 200, r.text
        ref = r.json()["invoice"]["ref"]
        assert r.json()["checkout_url"].endswith(ref)
        cents = round(r.json()["invoice"]["amount_egp"] * 100)

        async def callback(obj, sig=None):
            return await c.post(f"/account/paymob/callback?hmac={sig or sign(obj)}", json={"type": "TRANSACTION", "obj": obj})

        base = uuid.uuid4().int % 10**9  # Paymob transaction ids are unique forever
        # Forged or tampered callbacks change nothing.
        good = txn(ref, cents, base + 1)
        assert (await callback(good, sign(good, "attacker"))).status_code == 403
        assert (await callback({**good, "amount_cents": 1}, sign(good))).status_code == 403
        # A declined attempt and a wrong amount don't activate the plan.
        assert (await callback(txn(ref, cents, base, success=False))).json()["state"] == "failed"
        assert (await callback(txn(ref, 100, base + 2))).status_code == 200
        assert (await c.get(f"/account/invoices/{ref}", headers=h)).json()["status"] == "pending"
        # The real payment activates it, once.
        assert (await callback(good)).json() == {"ok": True, "state": "paid"}
        assert (await callback(good)).json()["duplicate"] is True
        inv = (await c.get(f"/account/invoices/{ref}", headers=h)).json()
        assert inv["status"] == "paid"
        ws = (await c.get(f"/account/workspaces/{tenant.id}", headers=h)).json()["workspace"]
        assert ws["plan"] == "pro" and ws["trial_ends_at"] is None and ws["paid_until"] == inv["period_end"]

        # Renewing early starts where the paid period ends; the earlier open checkout is abandoned.
        first = (await c.post(f"/account/workspaces/{tenant.id}/checkout", headers=h, json={"plan": "pro", "cycle": "annual"})).json()
        second = (await c.post(f"/account/workspaces/{tenant.id}/checkout", headers=h, json={"plan": "pro", "cycle": "annual"})).json()
        assert second["invoice"]["period_start"] == inv["period_end"]
        refs = {i["ref"]: i["status"] for i in (await c.get("/account/invoices", headers=h)).json()["items"]}
        assert first["invoice"]["ref"] not in refs and refs[second["invoice"]["ref"]] == "pending"


async def test_checkout_is_refused_without_paymob(monkeypatch):
    monkeypatch.setattr(settings, "PAYMOB_SECRET_KEY", "")
    owner, tenant, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        r = await c.post(f"/account/workspaces/{tenant.id}/checkout", headers=h, json={"plan": "pro"})
        assert r.status_code == 503
        assert (await c.get("/account/plans")).json()["online_payment"] is False


async def test_password_change_updates_workspace_logins():
    owner, tenant, user = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        r = await c.post("/account/password", headers=h, json={"current_password": "secret123", "new_password": "newpass123"})
        assert r.json()["workspace_logins_updated"] == 1
        await login(c, owner, "newpass123")
    from app.services.auth_service import authenticate

    async with AsyncSessionLocal() as db:
        assert (await authenticate(db, user.username, "newpass123", tenant_slug=tenant.slug)).id == user.id
