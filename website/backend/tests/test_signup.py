"""Signup collects the owner's email and phone and sends the code to verify the email (#72)."""
import os
import re
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from main import app

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


@pytest.fixture
def inbox(monkeypatch):
    from app.platform.notifications import service as mail
    from website_api.routers import signup

    sent = []

    async def fake_send(to_email, subject, html_content, attachments=None, text=None, reply_to=None):
        sent.append({"to": to_email, "subject": subject, "text": text})
        return {"ok": True}

    monkeypatch.setattr(mail, "send_email", fake_send)
    monkeypatch.setattr(mail, "email_enabled", lambda: True)
    app.dependency_overrides[signup.signup_limiter] = lambda: None
    yield sent
    app.dependency_overrides.clear()


async def test_signup_takes_email_and_phone_and_sends_a_code(inbox):
    from app.db.base import AsyncSessionLocal

    tag = uuid.uuid4().hex[:8]
    mail_addr = f"Signup-{tag}@Example.com"
    base = {"company_name": f"متجر {tag}", "sector": "retail", "scale": "small", "owner_username": f"su_{tag}",
            "owner_password": "longpass1", "owner_full_name": "مالك الاختبار"}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            assert (await c.post("/platform/signup", json=base)).status_code == 422  # email and phone are required
            assert (await c.post("/platform/signup", json={**base, "owner_email": "not-an-email", "owner_phone": "01001234567"})).status_code == 422
            r = await c.post("/platform/signup", json={**base, "owner_email": mail_addr, "owner_phone": "+20 100 123 4567"})
            assert r.status_code == 200, r.text
        assert len(inbox) == 1 and inbox[0]["to"] == mail_addr.lower() and re.search(r"\b\d{6}\b", inbox[0]["text"])
        async with AsyncSessionLocal() as db:
            row = (await db.execute(text("SELECT email, phone, email_verified_at FROM owner_accounts WHERE login = :l"),
                                    {"l": f"su_{tag}"})).one()
            assert row.email == mail_addr.lower() and row.phone == "+20 100 123 4567" and row.email_verified_at is None

            # Once verified, the address can't open a second account.
            await db.execute(text("UPDATE owner_accounts SET email_verified_at = now() WHERE login = :l"), {"l": f"su_{tag}"})
            await db.commit()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/platform/signup", json={**base, "owner_username": f"su2_{tag}", "owner_email": mail_addr,
                                                       "owner_phone": "01001234567"})
            assert r.status_code == 409
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
            await db.execute(text("DELETE FROM tenants WHERE owner_account_id IN (SELECT id FROM owner_accounts WHERE login LIKE :l)"),
                             {"l": f"su%_{tag}"})
            await db.execute(text("DELETE FROM owner_accounts WHERE login LIKE :l"), {"l": f"su%_{tag}"})
            await db.commit()
