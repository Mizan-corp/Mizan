"""Forgot password (#71) through the real system API: signed-out pages call it without a CSRF
token, like /account/login (the owner panel's login page found this missing)."""
import os

import pytest
from httpx import ASGITransport, AsyncClient

import main

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs the database")


@pytest.fixture(autouse=True)
async def fresh_engine():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


async def test_forgot_and_reset_need_no_csrf_token(monkeypatch):
    from app.platform.auth.routes import owner_login
    from app.platform.notifications import service as mail

    monkeypatch.setattr(mail, "email_enabled", lambda: True)
    main.app.dependency_overrides[owner_login.reset_limiter] = lambda: None
    try:
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="https://test") as c:
            r = await c.post("/account/password/forgot", json={"login": "nobody-at-all"})
            assert r.status_code == 200, r.text
            r = await c.post("/account/password/reset", json={"login": "nobody-at-all", "code": "123456", "new_password": "longenough1"})
            assert r.status_code == 400, r.text  # the code check answers, not the CSRF guard (403)
    finally:
        main.app.dependency_overrides.clear()
