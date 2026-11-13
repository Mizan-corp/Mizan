"""Owner API: sign-in, isolation between owners, checkout and the Paymob callback."""
import hashlib
import hmac
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.platform.auth.security import create_access_token, hash_password
from app.db.base import AsyncSessionLocal
from app.platform.auth.models.owner import OwnerAccount
from app.platform.tenancy.models import Tenant
from app.platform.auth.models.user import User
from app.integrations.paymob import service as paymob
from main import app

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

HMAC_SECRET = "test-hmac-secret"
REAL_CREATE_CHECKOUT = paymob.create_checkout  # the autouse fixture replaces it


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

    monkeypatch.setattr(settings, "PAYMOB_FLOW", "intention")
    monkeypatch.setattr(settings, "PAYMOB_TEST_OWNERS", "")

    async def fake_checkout(invoice, tenant, owner, **kw):
        return {"checkout_url": f"https://paymob.test/checkout/{invoice.invoice_ref}", "intention_id": "pi_x", "order_id": 42}

    monkeypatch.setattr(paymob, "create_checkout", fake_checkout)


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def erp_login_client() -> AsyncClient:
    """Owners sign in on the app's /login; that endpoint lives in the shared kernel."""
    from fastapi import FastAPI

    from app.platform.auth.routes import owner_login as owner_login

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


async def test_platform_staff_are_sent_to_the_admin_panel():
    _, tenant, _ = await make_owner()
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        name = f"staff-{uuid.uuid4().hex[:8]}"
        db.add(User(id=uuid.uuid4(), tenant_id=tenant.id, username=name, full_name="Staff", role="admin",
                    is_superadmin=True, password_hash=hash_password("staff12345")))
        await db.commit()
    async with erp_login_client() as erp:
        r = await erp.post("/account/login", json={"login": name, "password": "staff12345"})
        assert r.json() == {"admin_panel": True}
        assert "access_token" not in r.json()


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
        from app.platform.auth.security import decode_token

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


async def test_plan_changes_mid_period():
    """#68: upgrades start now with the unused paid time as extra days; downgrades start when the
    paid time ends; the owner sees both before paying."""
    from datetime import datetime, timedelta

    from sqlalchemy import select, text

    from app.platform.billing.models import BillingInvoice
    from app.platform.billing.services.subscriptions import apply_due_plan_changes, monthly_price

    owner, tenant, _ = await make_owner()
    base = uuid.uuid4().int % 10**9

    def day(iso: str):
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))

    async with client() as c:
        h = await login(c, owner)

        async def buy(plan: str, n: int) -> dict:
            r = await c.post(f"/account/workspaces/{tenant.id}/checkout", headers=h, json={"plan": plan, "cycle": "monthly"})
            inv = r.json()["invoice"]
            obj = txn(inv["ref"], round(inv["amount_egp"] * 100), base + n)
            ok = await c.post(f"/account/paymob/callback?hmac={sign(obj)}", json={"type": "TRANSACTION", "obj": obj})
            assert ok.json()["state"] == "paid", ok.text
            return (await c.get(f"/account/invoices/{inv['ref']}", headers=h)).json()

        async def quote(plan: str) -> dict:
            r = await c.get(f"/account/workspaces/{tenant.id}/checkout/quote", headers=h, params={"plan": plan, "cycle": "monthly"})
            assert r.status_code == 200, r.text
            return r.json()

        async def workspace() -> dict:
            return (await c.get(f"/account/workspaces/{tenant.id}", headers=h)).json()["workspace"]

        # From the trial: a new subscription, starting now.
        q = await quote("starter")
        assert q["kind"] == "new" and q["credit_days"] == 0
        starter = await buy("starter", 1)
        assert (await workspace())["plan"] == "starter"

        # Upgrade: starts now, full price, the unused starter time as extra days.
        q = await quote("pro")
        assert q["kind"] == "upgrade" and q["amount_egp"] == monthly_price("pro")
        assert q["credit_egp"] > monthly_price("starter") * 0.95  # almost all of it is unused
        assert q["credit_days"] == int(q["credit_egp"] // (monthly_price("pro") / 30)) > 0
        pro = await buy("pro", 2)
        assert (day(pro["period_end"]) - day(pro["period_start"])).days == 30 + q["credit_days"]
        ws = await workspace()
        assert ws["plan"] == "pro" and ws["paid_until"] == pro["period_end"]
        # The credited starter period ended when the upgrade was paid.
        assert day((await c.get(f"/account/invoices/{starter['ref']}", headers=h)).json()["period_end"]) <= day(pro["period_start"]) + timedelta(minutes=5)

        # Downgrade: paid now, starts when the pro time ends; the workspace keeps pro until then.
        q = await quote("starter")
        assert q["kind"] == "downgrade" and q["period_start"] == pro["period_end"]
        down = await buy("starter", 3)
        assert down["period_start"] == pro["period_end"]
        ws = await workspace()
        assert ws["plan"] == "pro" and ws["paid_until"] == down["period_end"]
        assert (await quote("starter"))["kind"] == "downgrade" and (await quote("pro"))["kind"] == "renewal"

    # Time passes: the pro period is over; the subscriptions job moves the workspace to starter.
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        rows = (await db.execute(select(BillingInvoice).where(BillingInvoice.tenant_id == tenant.id, BillingInvoice.status == "paid"))).scalars().all()
        shift = day(down["period_start"]) - datetime.now(day(down["period_start"]).tzinfo) + timedelta(hours=1)
        for inv in rows:
            inv.period_start -= shift
            inv.period_end -= shift
        await db.flush()
        assert await apply_due_plan_changes(db) >= 1
        t = await db.get(Tenant, tenant.id)
        assert t.plan == "starter" and t.status == "active"
        await db.rollback()


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
    from app.platform.auth.services.auth import authenticate

    async with AsyncSessionLocal() as db:
        assert (await authenticate(db, user.username, "newpass123", tenant_slug=tenant.slug)).id == user.id


async def test_sign_out_and_password_change_end_sessions():
    """#77: sign-out revokes the token; a password change ends every other session, and the
    response carries a fresh token for this one."""
    owner, _, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        assert (await c.post("/account/logout", headers=h)).status_code == 204
        assert (await c.get("/account/me", headers=h)).status_code == 401

        mine, other = await login(c, owner), await login(c, owner)
        r = await c.post("/account/password", headers=mine, json={"current_password": "secret123", "new_password": "newpass123"})
        assert (await c.get("/account/me", headers=other)).status_code == 401
        assert (await c.get("/account/me", headers=mine)).status_code == 401
        fresh = {"Authorization": f"Bearer {r.json()['access_token']}"}
        assert (await c.get("/account/me", headers=fresh)).status_code == 200


async def test_only_test_owners_can_pay_while_set(monkeypatch):
    owner, tenant, _ = await make_owner()
    other, other_tenant, _ = await make_owner()
    monkeypatch.setattr(settings, "PAYMOB_TEST_OWNERS", f" {owner.login.upper()} , someone.else")
    async with client() as c:
        h = await login(c, owner)
        plans = (await c.get("/account/plans", headers=h)).json()
        assert plans["online_payment"] is True and plans["test_mode"] is True
        r = await c.post(f"/account/workspaces/{tenant.id}/checkout", headers=h, json={"plan": "pro"})
        assert r.status_code == 200, r.text

        h2 = await login(c, other)
        assert (await c.get("/account/plans", headers=h2)).json()["online_payment"] is False
        assert (await c.get("/account/plans")).json()["online_payment"] is False  # signed out
        r = await c.post(f"/account/workspaces/{other_tenant.id}/checkout", headers=h2, json={"plan": "pro"})
        assert r.status_code == 503


async def test_accept_flow_asks_for_a_method_and_a_wallet_number(monkeypatch):
    monkeypatch.setattr(settings, "PAYMOB_FLOW", "accept")
    monkeypatch.setattr(settings, "PAYMOB_API_KEY", "api-key")
    monkeypatch.setattr(settings, "PAYMOB_CARD_INTEGRATION_ID", "6052809")
    monkeypatch.setattr(settings, "PAYMOB_WALLET_INTEGRATION_ID", "6052808")
    monkeypatch.setattr(settings, "PAYMOB_IFRAME_ID", "")  # no card page yet: wallet only
    seen = {}

    async def fake_checkout(invoice, tenant, owner, **kw):
        seen.update(kw)
        return {"checkout_url": "https://paymob.test/wallet", "intention_id": None, "order_id": 7}

    monkeypatch.setattr(paymob, "create_checkout", fake_checkout)
    owner, tenant, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        assert (await c.get("/account/plans", headers=h)).json()["payment_methods"] == ["wallet"]
        url = f"/account/workspaces/{tenant.id}/checkout"
        assert (await c.post(url, headers=h, json={"plan": "pro"})).status_code == 422
        assert (await c.post(url, headers=h, json={"plan": "pro", "method": "card"})).status_code == 422
        assert (await c.post(url, headers=h, json={"plan": "pro", "method": "wallet", "wallet_number": "0123"})).status_code == 422
        r = await c.post(url, headers=h, json={"plan": "pro", "method": "wallet", "wallet_number": "+20 101 010 1010"})
        assert r.status_code == 200, r.text
        assert seen == {"method": "wallet", "wallet_number": "+20 101 010 1010"}

        monkeypatch.setattr(settings, "PAYMOB_IFRAME_ID", "901")
        assert (await c.get("/account/plans", headers=h)).json()["payment_methods"] == ["card", "wallet"]


def test_wallet_numbers():
    ok = {"01010101010": "01010101010", "+20 101 010 1010": "01010101010", "0020 1010101010": "01010101010",
          "01510101010": "01510101010"}
    for given, expected in ok.items():
        assert paymob.normalize_wallet(given) == expected
    for bad in ("", "0101010101", "02123456789", "01310101010", "abc"):
        assert paymob.normalize_wallet(bad) is None


async def test_accept_checkout_calls(monkeypatch):
    """The accept flow's calls to Paymob, with Paymob mocked."""
    import types

    monkeypatch.setattr(settings, "PAYMOB_FLOW", "accept")
    monkeypatch.setattr(settings, "PAYMOB_API_KEY", "api-key")
    monkeypatch.setattr(settings, "PAYMOB_CARD_INTEGRATION_ID", "6052809")
    monkeypatch.setattr(settings, "PAYMOB_WALLET_INTEGRATION_ID", "6052808")
    monkeypatch.setattr(settings, "PAYMOB_IFRAME_ID", "901")
    calls = []

    def fake_post(url, body, headers):
        path = url.split("accept.paymob.com", 1)[1]
        calls.append((path, body))
        return {
            "/api/auth/tokens": {"token": "auth"},
            "/api/ecommerce/orders": {"id": 555},
            "/api/acceptance/payment_keys": {"token": "PK"},
            "/api/acceptance/payments/pay": {"redirect_url": "https://accept.paymob.com/wallet?token=W"},
        }[path]

    monkeypatch.setattr(paymob, "_post_json", fake_post)
    invoice = types.SimpleNamespace(amount_egp=850.0, invoice_ref="INV-1", plan="pro", billing_cycle="monthly")
    tenant = types.SimpleNamespace(name="صيدلية الأمل")
    owner = types.SimpleNamespace(full_name="Nour Hassan", email=None, login="nour", phone=None)

    card = await REAL_CREATE_CHECKOUT(invoice, tenant, owner, method="card")
    assert card["checkout_url"] == "https://accept.paymob.com/api/acceptance/iframes/901?payment_token=PK"
    assert card["order_id"] == 555
    order = dict(calls)["/api/ecommerce/orders"]
    assert order["merchant_order_id"] == "INV-1" and order["amount_cents"] == 85000
    key = dict(calls)["/api/acceptance/payment_keys"]
    assert key["integration_id"] == 6052809 and key["extra"]["description"] == "باقة الاحترافية · شهري · صيدلية الأمل"

    calls.clear()
    wallet = await REAL_CREATE_CHECKOUT(invoice, tenant, owner, method="wallet", wallet_number="01010101010")
    assert wallet["checkout_url"].endswith("token=W")
    paths = [c[0] for c in calls]
    assert paths[-1] == "/api/acceptance/payments/pay"
    assert dict(calls)["/api/acceptance/payment_keys"]["integration_id"] == 6052808
    assert dict(calls)["/api/acceptance/payments/pay"]["source"] == {"identifier": "01010101010", "subtype": "WALLET"}

    with pytest.raises(paymob.PaymobError):
        await REAL_CREATE_CHECKOUT(invoice, tenant, owner, method="wallet", wallet_number="123")


async def test_paid_invoices_have_a_pdf_receipt():
    """#69: a receipt for paid invoices only, for their owner only."""
    owner, tenant, _ = await make_owner()
    other, _, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        inv = (await c.post(f"/account/workspaces/{tenant.id}/checkout", headers=h, json={"plan": "pro", "cycle": "monthly"})).json()["invoice"]
        ref, cents = inv["ref"], round(inv["amount_egp"] * 100)
        assert (await c.get(f"/account/invoices/{ref}/receipt.pdf", headers=h)).status_code == 409  # not paid yet

        paid = txn(ref, cents, uuid.uuid4().int % 10**9)
        assert (await c.post(f"/account/paymob/callback?hmac={sign(paid)}", json={"type": "TRANSACTION", "obj": paid})).json()["state"] == "paid"

        r = await c.get(f"/account/invoices/{ref}/receipt.pdf", headers=h)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
        assert f"Mizan-receipt-{ref}.pdf" in r.headers["content-disposition"]
        assert (await c.get(f"/account/invoices/{ref}/receipt.pdf", headers=await login(c, other))).status_code == 404


async def test_owners_rename_and_readdress_their_workspaces():
    """#74: name and URL name (the workspace's address), with the sign-up rules."""
    owner, tenant, _ = await make_owner()
    _, other_ws, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        new_slug = f"renamed-{uuid.uuid4().hex[:6]}"
        r = await c.patch(f"/account/workspaces/{tenant.id}", headers=h, json={"name": "اسم جديد", "slug": new_slug})
        assert r.status_code == 200, r.text
        assert r.json()["workspace"]["name"] == "اسم جديد" and r.json()["workspace"]["slug"] == new_slug
        for slug, code in (("admin", 422), ("-bad-", 422), ("ab", 422), (other_ws.slug, 409)):
            r = await c.patch(f"/account/workspaces/{tenant.id}", headers=h, json={"slug": slug})
            assert r.status_code == code, (slug, r.text)
        # Someone else's workspace isn't found.
        assert (await c.patch(f"/account/workspaces/{other_ws.id}", headers=h, json={"name": "x" * 3})).status_code == 404


async def test_owners_delete_only_unpaid_trials():
    owner, tenant, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        assert (await c.delete(f"/account/workspaces/{tenant.id}", headers=h, params={"confirm": "wrong"})).status_code == 400

        # A workspace with a paid invoice goes through support.
        inv = (await c.post(f"/account/workspaces/{tenant.id}/checkout", headers=h, json={"plan": "pro", "cycle": "monthly"})).json()["invoice"]
        paid = txn(inv["ref"], round(inv["amount_egp"] * 100), uuid.uuid4().int % 10**9)
        await c.post(f"/account/paymob/callback?hmac={sign(paid)}", json={"type": "TRANSACTION", "obj": paid})
        assert (await c.delete(f"/account/workspaces/{tenant.id}", headers=h, params={"confirm": tenant.name})).status_code == 409

    owner2, trial, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner2)
        assert (await c.delete(f"/account/workspaces/{trial.id}", headers=h, params={"confirm": trial.name})).status_code == 204
        assert (await c.get(f"/account/workspaces/{trial.id}", headers=h)).status_code == 404


async def test_pending_invoices_are_checked_with_paymob(monkeypatch):
    """#67: a payment whose callback never came is found through Paymob's inquiry API and applied
    once, as the callback would have."""
    from sqlalchemy import select, text

    from app.integrations.paymob import reconcile
    from app.platform.billing.models import BillingInvoice

    owner, tenant, _ = await make_owner()
    async with client() as c:
        inv = (await c.post(f"/account/workspaces/{tenant.id}/checkout", headers=await login(c, owner),
                            json={"plan": "pro", "cycle": "monthly"})).json()["invoice"]
    paid = txn(inv["ref"], round(inv["amount_egp"] * 100), uuid.uuid4().int % 10**9)
    asked = []
    monkeypatch.setattr(reconcile, "_order_transactions", lambda order_id: asked.append(order_id) or [paid])

    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', false)"))
        invoice = await db.scalar(select(BillingInvoice).where(BillingInvoice.invoice_ref == inv["ref"]))
        monkeypatch.setattr(settings, "PAYMOB_API_KEY", "")
        assert (await reconcile.reconcile_invoice(db, invoice))["checked"] is False
        monkeypatch.setattr(settings, "PAYMOB_API_KEY", "api_key_test")
        first = await reconcile.reconcile_invoice(db, invoice)
        again = await reconcile.reconcile_invoice(db, invoice)
        await db.execute(text("SELECT set_config('app.bypass', '', false)"))
    assert asked == ["42"]
    assert first == {"checked": True, "transactions": 1, "applied": 1, "status": "paid"}
    assert again["checked"] is False  # paid now: nothing to ask

    # The callback arriving late is a duplicate, not a second payment.
    async with client() as c:
        late = await c.post(f"/account/paymob/callback?hmac={sign(paid)}", json={"type": "TRANSACTION", "obj": paid})
        assert late.json().get("duplicate") is True


async def test_the_scheduler_needs_the_cron_secret(monkeypatch):
    monkeypatch.setattr(settings, "PAYMOB_API_KEY", "")
    async with client() as c:
        monkeypatch.setattr(settings, "CRON_SECRET", "")
        assert (await c.post("/account/cron/paymob-reconcile", headers={"X-Cron-Secret": ""})).status_code == 403
        monkeypatch.setattr(settings, "CRON_SECRET", "s3cret")
        assert (await c.post("/account/cron/paymob-reconcile", headers={"X-Cron-Secret": "wrong"})).status_code == 403
        r = await c.post("/account/cron/paymob-reconcile", headers={"X-Cron-Secret": "s3cret"})
        assert r.status_code == 200 and r.json()["items_processed"] == 0
