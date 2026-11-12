"""Browser end-to-end tests across the four apps (#80): website, owner panel, ERP, admin panel.

Run with the stack and the four dev servers up:
    E2E_BROWSER=1 python -m pytest -q browser      (from e2e/)
App URLs default to the local dev servers (E2E_WEBSITE_URL, E2E_OWNER_URL, E2E_APP_URL,
E2E_ADMIN_URL; API: E2E_API_BASE, E2E_ADMIN_API). Each test gets a fresh browser context.

Owners and workspaces are made through the admin API by a temporary platform admin (signup is
rate-limited to 5 an hour, so only the signup test signs up); everything the run creates is
removed at the end.
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest

if not os.environ.get("E2E_BROWSER"):
    pytest.skip("browser tests: set E2E_BROWSER=1 (needs the dev servers)", allow_module_level=True)

from playwright.sync_api import Browser, Page, sync_playwright  # noqa: E402

from helpers import DB  # noqa: E402

WEBSITE = os.environ.get("E2E_WEBSITE_URL", "http://localhost:5174").rstrip("/")
OWNER = os.environ.get("E2E_OWNER_URL", "http://localhost:5176").rstrip("/")
APP = os.environ.get("E2E_APP_URL", "http://localhost:5173").rstrip("/")
ADMIN = os.environ.get("E2E_ADMIN_URL", "http://localhost:5175").rstrip("/")
API = os.environ.get("E2E_API_BASE", "http://localhost:8000").rstrip("/")
ADMIN_API = os.environ.get("E2E_ADMIN_API", "http://localhost:8002").rstrip("/")
PASSWORD = "Browser-e2e-9!"


def workspace_url(slug: str, path: str = "/") -> str:
    """The dev servers serve workspaces by path (/c/<slug>); production by subdomain."""
    return f"{APP}/c/{slug}{path if path != '/' else ''}"


@pytest.fixture(scope="session")
def created(db: DB):
    """Remove the workspaces, owners and platform users this run creates."""
    tenants = {r[0] for r in db.q("SELECT id FROM tenants")}
    owners = {r[0] for r in db.q("SELECT id FROM owner_accounts")}
    yield
    new_tenants = [str(r[0]) for r in db.q("SELECT id FROM tenants") if r[0] not in tenants]
    new_owners = [str(r[0]) for r in db.q("SELECT id FROM owner_accounts") if r[0] not in owners]
    if new_tenants:
        db.q("DELETE FROM tenants WHERE id = ANY(%s::uuid[])", (new_tenants,))
    if new_owners:
        db.q("DELETE FROM owner_accounts WHERE id = ANY(%s::uuid[])", (new_owners,))


@pytest.fixture(scope="session")
def platform_admin(db: DB, created) -> dict:
    """A platform admin (in a throwaway workspace of its own): login, password and an API token."""
    import bcrypt

    tag = uuid.uuid4().hex[:8]
    home = uuid.uuid4()
    login = f"e2e-plat-{tag}"
    db.q("INSERT INTO tenants (id, name, slug, status) VALUES (%s, %s, %s, 'active')", (str(home), f"E2E platform {tag}", f"e2e-plat-{tag}"))
    db.q(
        "INSERT INTO users (id, tenant_id, username, full_name, role, is_superadmin, is_active, password_hash) "
        "VALUES (%s, %s, %s, 'E2E Platform', 'superadmin', true, true, %s)",
        (str(uuid.uuid4()), str(home), login, bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()),
    )
    r = httpx.post(f"{ADMIN_API}/auth/login", json={"username": login, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    return {"login": login, "password": PASSWORD, "token": r.json()["access_token"]}


@pytest.fixture()
def workspace(platform_admin) -> dict:
    """A fresh trial workspace and its owner (owner login = the workspace admin's username)."""
    tag = uuid.uuid4().hex[:8]
    login = f"e2e-own-{tag}"
    r = httpx.post(f"{ADMIN_API}/admoon/tenants", timeout=60,
                   headers={"Authorization": f"Bearer {platform_admin['token']}"},
                   json={"company_name": f"متجر المتصفح {tag}", "sector": "retail", "owner_full_name": "مالك اختبار",
                         "owner_username": login, "owner_password": PASSWORD})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"id": body["id"], "slug": body["slug"], "name": f"متجر المتصفح {tag}", "login": login, "password": PASSWORD}


@pytest.fixture(scope="session")
def browser() -> Browser:
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser: Browser) -> Page:
    context = browser.new_context(viewport={"width": 1366, "height": 900}, locale="ar-EG")
    context.set_default_timeout(30_000)
    pg = context.new_page()
    yield pg
    context.close()


def owner_sign_in(page: Page, login: str, password: str) -> None:
    page.get_by_label("اسم المستخدم").fill(login)
    page.get_by_label("كلمة المرور", exact=True).fill(password)
    page.get_by_role("button", name="دخول", exact=True).click()


def skip_tour(page: Page) -> None:
    """New owners get a welcome tour over the panel; skip it if it's showing."""
    button = page.get_by_role("button", name="تخطَّ الجولة")
    try:
        button.wait_for(state="visible", timeout=5000)
    except Exception:
        return
    button.click()
    button.wait_for(state="hidden")
