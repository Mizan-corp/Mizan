"""Owners' email (#71, #72): verifying the address, forgot password, receipts and reminders."""
import os
import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.db.base import AsyncSessionLocal
from app.platform.auth.models.owner import OwnerAccount
from app.platform.auth.models.user import User
from app.platform.auth.security import verify_password
from app.platform.notifications import service as mail
from app.platform.tenancy.models import Tenant
from tests.test_owner_api import client, login, make_owner

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


@pytest.fixture
def inbox(monkeypatch):
    """Mail is on, and every message lands here instead of leaving."""
    sent: list[dict] = []

    async def fake_send(to_email, subject, html_content, attachments=None, text=None, reply_to=None):
        sent.append({"to": to_email, "subject": subject, "html": html_content, "text": text, "attachments": attachments or []})
        return {"ok": True, "provider": "test"}

    monkeypatch.setattr(mail, "send_email", fake_send)
    monkeypatch.setattr(mail, "email_enabled", lambda: True)
    return sent


def code_in(message: dict) -> str:
    return re.search(r"\b(\d{6})\b", message["text"]).group(1)


def public_client():
    """The system API's owner sign-in router, with the forgot-password routes, unthrottled."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.platform.auth.routes import owner_login

    app = FastAPI()
    app.include_router(owner_login.router)
    app.dependency_overrides[owner_login.login_limiter] = lambda: None
    app.dependency_overrides[owner_login.reset_limiter] = lambda: None
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def forget_codes(owner_id):
    """Let the next code go out at once (one a minute, three an hour, per purpose)."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE owner_codes SET created_at = created_at - interval '2 hours' WHERE owner_id = :o"), {"o": owner_id})
        await db.commit()


async def test_verifying_the_email(inbox):
    owner, _, _ = await make_owner()
    async with client() as c:
        h = await login(c, owner)
        me = (await c.get("/account/me", headers=h)).json()
        assert me["email_verified"] is False and me["email_service"] is True
        assert (await c.post("/account/email/send-code", headers=h)).status_code == 422  # no address yet

        mail_a = f"owner-{uuid.uuid4().hex[:8]}@example.com"
        await c.patch("/account/me", headers=h, json={"email": mail_a.upper()})
        r = await c.post("/account/email/send-code", headers=h)
        assert r.status_code == 200 and r.json()["to"].endswith("@example.com")
        assert inbox[-1]["to"] == mail_a and "تأكيد" in inbox[-1]["subject"]
        assert (await c.post("/account/email/send-code", headers=h)).status_code == 429  # one a minute
        code = code_in(inbox[-1])

        wrong = "000000" if code != "000000" else "111111"
        assert (await c.post("/account/email/verify", headers=h, json={"code": wrong})).status_code == 400
        r = await c.post("/account/email/verify", headers=h, json={"code": code})
        assert r.status_code == 200 and r.json()["email_verified"] is True
        assert (await c.post("/account/email/verify", headers=h, json={"code": code})).status_code == 400  # used once

        # A new address needs proving again.
        await c.patch("/account/me", headers=h, json={"email": f"other-{mail_a}"})
        assert (await c.get("/account/me", headers=h)).json()["email_verified"] is False

    # The same address can't be verified on a second account.
    other, _, _ = await make_owner()
    async with client() as c:
        h2 = await login(c, other)
        await c.patch("/account/me", headers=h2, json={"email": f"other-{mail_a}"})
        async with AsyncSessionLocal() as db:
            await db.execute(text("UPDATE owner_accounts SET email_verified_at = now() WHERE id = :o"), {"o": owner.id})
            await db.commit()
        await c.post("/account/email/send-code", headers=h2)
        r = await c.post("/account/email/verify", headers=h2, json={"code": code_in(inbox[-1])})
        assert r.status_code == 409


async def test_forgot_password_resets_owner_and_workspace_logins(inbox):
    owner, _, user = await make_owner()
    address = f"reset-{uuid.uuid4().hex[:8]}@example.com"
    async with public_client() as pub:
        # No verified address: the same answer, and nothing is sent.
        r = await pub.post("/account/password/forgot", json={"login": owner.login})
        assert r.status_code == 200 and not inbox

        async with AsyncSessionLocal() as db:
            await db.execute(text("UPDATE owner_accounts SET email = :e, email_verified_at = now() WHERE id = :o"),
                             {"e": address, "o": owner.id})
            await db.commit()
        # By username or by the verified address; unknown accounts get the same answer.
        assert (await pub.post("/account/password/forgot", json={"login": "nobody-here"})).json()["ok"] is True
        await pub.post("/account/password/forgot", json={"login": address.upper()})
        assert len(inbox) == 1 and inbox[0]["to"] == address and "استعادة" in inbox[0]["subject"]
        first = code_in(inbox[0])
        await forget_codes(owner.id)
        await pub.post("/account/password/forgot", json={"login": owner.login})
        second = code_in(inbox[1])

        bad = {"login": owner.login, "code": first, "new_password": "brand-new-pass"}
        if first != second:  # asking again replaces the earlier code
            assert (await pub.post("/account/password/reset", json=bad)).status_code == 400
        assert (await pub.post("/account/password/reset", json={**bad, "new_password": "short"})).status_code == 422
        r = await pub.post("/account/password/reset", json={**bad, "code": second})
        assert r.status_code == 200 and r.json()["access_token"]
        assert (await pub.post("/account/password/reset", json={**bad, "code": second})).status_code == 400  # used

        # The owner and the workspace login both take the new password; the old one is gone.
        assert (await pub.post("/account/login", json={"login": owner.login, "password": "brand-new-pass"})).status_code == 200
        assert (await pub.post("/account/login", json={"login": owner.login, "password": "secret123"})).status_code == 401
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        u = await db.get(User, user.id)
        assert verify_password("brand-new-pass", u.password_hash)


async def test_codes_lock_after_five_wrong_tries(inbox):
    owner, _, _ = await make_owner()
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE owner_accounts SET email = :e, email_verified_at = now() WHERE id = :o"),
                         {"e": f"lock-{uuid.uuid4().hex[:8]}@example.com", "o": owner.id})
        await db.commit()
    async with public_client() as pub:
        await pub.post("/account/password/forgot", json={"login": owner.login})
        code = code_in(inbox[-1])
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            assert (await pub.post("/account/password/reset", json={"login": owner.login, "code": wrong,
                                                                     "new_password": "brand-new-pass"})).status_code == 400
        r = await pub.post("/account/password/reset", json={"login": owner.login, "code": code, "new_password": "brand-new-pass"})
        assert r.status_code == 400  # spent after five wrong tries


async def test_forgot_password_needs_the_mail_service(monkeypatch):
    monkeypatch.setattr(mail, "email_enabled", lambda: False)
    async with public_client() as pub:
        assert (await pub.post("/account/password/forgot", json={"login": "anyone"})).status_code == 503


async def test_receipts_and_reminders_go_once_to_verified_addresses(inbox):
    from app.platform.auth.services.owner_mail import OwnerEmailLog
    from app.platform.billing.owner_emails import billing_reminders, email_receipt
    from app.platform.billing.services.subscriptions import activate_invoice, new_invoice

    owner, tenant, _ = await make_owner()
    address = f"bill-{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        o = await db.get(OwnerAccount, owner.id)
        o.email = address
        t = await db.get(Tenant, tenant.id)
        t.trial_ends_at = datetime.now(UTC) + timedelta(days=2)
        await db.commit()

        # Not verified yet: no reminder.
        await billing_reminders(db)
        assert not [m for m in inbox if m["to"] == address]
        await db.execute(text("UPDATE owner_accounts SET email_verified_at = now() WHERE id = :o"), {"o": owner.id})
        await db.commit()
        await billing_reminders(db)
        await billing_reminders(db)  # once per end date
        mine = [m for m in inbox if m["to"] == address]
        assert len(mine) == 1 and "التجربة" in mine[0]["subject"]

        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        inv = await new_invoice(db, await db.get(Tenant, tenant.id), plan="starter", cycle="monthly", method="card")
        await activate_invoice(db, inv, reference="test")
        await db.commit()
        assert await email_receipt(db, inv) is True
        assert await email_receipt(db, inv) is False  # once
        receipt = [m for m in inbox if m["to"] == address][-1]
        assert inv.invoice_ref in receipt["subject"] and receipt["attachments"][0]["filename"].startswith("Mizan-")
        rows = (await db.execute(select(OwnerEmailLog.kind).where(OwnerEmailLog.owner_id == owner.id))).scalars().all()
        assert sorted(rows) == ["receipt", "trial_ending"]
