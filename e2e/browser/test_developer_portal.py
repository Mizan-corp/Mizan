"""The developer portal (ADR-007 step 7), on the website app under /dev (dev.allmizan.live in
production): sign up, create a team, register a signing key and get its certificate, make a CLI
token, sign out. One sign-up per run (rate-limited to 5 an hour)."""
import base64
import re
import uuid

import pytest
from conftest import WEBSITE
from playwright.sync_api import Page, expect

from helpers import DB


@pytest.fixture()
def developer_tag(db: DB):
    tag = uuid.uuid4().hex[:8]
    yield tag
    db.q("DELETE FROM developer_teams WHERE handle = %s", (f"e2e{tag}",))
    db.q("DELETE FROM developer_users WHERE email = %s", (f"e2e-{tag}@example.com",))


def public_key() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    raw = Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_portal_signup_team_key_and_cli_token(page: Page, developer_tag):
    tag, handle = developer_tag, f"e2e{developer_tag}"
    page.goto(f"{WEBSITE}/dev")
    expect(page.get_by_role("heading", level=1)).to_have_text("Build on Mizan")  # English by default
    assert page.evaluate("() => document.documentElement.dir") == "ltr"
    page.get_by_role("link", name=re.compile("Create a developer account")).first.click()
    page.locator("#dev-name").fill("Browser test developer")
    page.locator("#dev-email").fill(f"e2e-{tag}@example.com")
    page.locator("#dev-password").fill("Browser-e2e-9!")
    page.get_by_role("button", name="Create account").click()
    page.wait_for_url(re.compile(r"/dev/portal$"))
    expect(page.get_by_text("No teams yet")).to_be_visible()

    # A team; its handle is the namespace of its modules.
    page.get_by_role("button", name=re.compile("New team")).click()
    page.locator("#team-handle").fill(handle)
    page.locator("#team-name").fill("Browser team")
    page.get_by_role("dialog").get_by_role("button", name="Create team").click()
    page.get_by_role("link", name=re.compile("Browser team")).click()
    page.wait_for_url(re.compile(rf"/dev/portal/teams/{handle}$"))

    # A key, certified by Mizan.
    page.get_by_role("button", name="Key", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.locator("#key-public").fill(public_key())
    dialog.locator("#key-name").fill("laptop")
    dialog.get_by_role("button", name="Register and certify").click()
    expect(dialog.locator("code").first).to_contain_text("MZD1.")
    dialog.get_by_role("button", name="Done").click()
    expect(page.get_by_text(re.compile(rf"{handle}-[0-9a-f]{{8}}")).first).to_be_visible()

    # A CLI token, shown once.
    page.get_by_role("link", name="CLI tokens").click()
    page.get_by_role("button", name=re.compile("New token")).first.click()
    page.locator("#token-name").fill("laptop")
    page.get_by_role("dialog").get_by_role("button", name="Create", exact=True).click()
    expect(page.get_by_role("dialog").locator("code").first).to_contain_text("mzd_")
    page.get_by_role("dialog").get_by_role("button", name="Done").click()
    expect(page.get_by_text(re.compile("not used yet"))).to_be_visible()

    # Arabic on request (right to left), remembered for the developer platform only.
    page.get_by_role("button", name="العربية").click()
    expect(page.get_by_role("heading", level=1)).to_have_text("رموز سطر الأوامر")
    assert page.evaluate("() => document.documentElement.dir") == "rtl"
    page.get_by_role("button", name="English").click()

    # Signing out ends the portal session.
    page.get_by_role("button", name="Sign out").first.click()
    page.goto(f"{WEBSITE}/dev/portal")
    page.wait_for_url(re.compile(r"/dev/login"))
