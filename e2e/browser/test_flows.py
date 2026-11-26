"""Flows that span the website, the owner panel, the ERP and the admin panel (#80).

The checkout → Paymob → paid flow is left for the Paymob work (on hold).
"""
import re
import uuid

import httpx
from conftest import ADMIN, API, OWNER, WEBSITE, erp_login, owner_sign_in, retry_after, skip_tour, workspace_url
from playwright.sync_api import Page, expect


def test_signup_lands_in_the_owner_panel_and_opens_the_workspace(page: Page, created):
    page.goto(f"{WEBSITE}/signup")
    tag = uuid.uuid4().hex[:8]
    page.locator("#reg-fullname").fill("مالك اختبار المتصفح")
    page.locator("#reg-username").fill(f"e2e_br_{tag}")
    page.locator("#reg-email").fill(f"e2e-br-{tag}@example.com")
    page.locator("#reg-phone").fill("01001234567")
    page.locator("#reg-password").fill("Browser-e2e-9!")
    page.locator("button[type=submit]").click()

    # The setup wizard: activity, name and size, look and modules.
    page.get_by_role("button", name=re.compile("Retail-POS")).first.click()
    page.get_by_role("button", name="التالي ←").click()
    page.get_by_placeholder(re.compile("مجمع الوادي التجاري")).fill(f"سوبرماركت {tag}")
    page.get_by_role("button", name=re.compile("فرع واحد")).click()
    page.get_by_role("button", name="التالي ←").click()
    # The visual-identity step: recommendations preselect a palette, continue with it.
    page.get_by_role("button", name="التالي ←").click()
    page.get_by_role("button", name=re.compile("أنشئ مساحة عملي الآن")).click()

    # The owner panel, signed in, with the welcome tour.
    page.wait_for_url(f"{OWNER}/**", timeout=90_000)
    page.get_by_role("button", name="تخطَّ الجولة").click()
    expect(page.get_by_text(f"سوبرماركت {tag}").first).to_be_visible()

    # Opening the workspace hands the session over to the ERP.
    page.get_by_role("button", name="افتح النظام").first.click()
    page.wait_for_url(re.compile(r"/c/[a-z0-9-]+"), timeout=60_000)
    expect(page.locator("aside").first).to_contain_text(f"سوبرماركت {tag}")
    assert page.evaluate("() => !!localStorage.getItem('mizan.session')")


def test_signed_out_owners_sign_in_and_return_to_the_page(page: Page, workspace):
    page.goto(f"{OWNER}/invoices")
    page.wait_for_url(re.compile(r"/login\?next=%2Finvoices"))
    owner_sign_in(page, workspace["login"], workspace["password"])
    page.wait_for_url(re.compile(r"/invoices$"), timeout=60_000)  # via the website's /session
    expect(page.get_by_role("heading", name=re.compile("الفواتير"))).to_be_visible()


def test_unsafe_next_is_ignored(page: Page, workspace):
    page.goto(f"{OWNER}/login?next=" + "/%5Cevil.example")
    owner_sign_in(page, workspace["login"], workspace["password"])
    page.wait_for_url(re.compile(rf"^{re.escape(OWNER)}/?$"), timeout=60_000)


def test_employees_are_pointed_to_their_workspace_sign_in(page: Page, workspace):
    erp = erp_login(workspace["slug"], workspace["login"], workspace["password"])
    erp.raise_for_status()
    clerk = f"e2e-clerk-{uuid.uuid4().hex[:6]}"
    r = httpx.post(f"{API}/users", headers={"Authorization": f"Bearer {erp.json()['access_token']}"}, timeout=30,
                   json={"username": clerk, "full_name": "موظف اختبار", "role": "cashier", "password": "Clerk-e2e-9!"})
    assert r.status_code == 200, r.text

    page.goto(f"{OWNER}/login")
    owner_sign_in(page, clerk, "Clerk-e2e-9!")
    link = page.locator(f"a[href*='{workspace['slug']}']").first
    expect(link).to_be_visible()
    assert link.get_attribute("href").endswith("/login")


def test_the_website_follows_the_owners_session_and_sign_out_clears_both(page: Page, workspace):
    page.goto(f"{OWNER}/login")
    owner_sign_in(page, workspace["login"], workspace["password"])
    page.wait_for_url(re.compile(rf"^{re.escape(OWNER)}/?$"), timeout=60_000)

    page.goto(WEBSITE)
    expect(page.get_by_text("العودة إلى لوحتك").first).to_be_visible()

    # Sign out on the website: the panel is signed out too.
    page.get_by_role("button", name="تسجيل الخروج").first.click()
    page.wait_for_timeout(2000)
    page.goto(f"{OWNER}/")
    page.wait_for_url(re.compile(r"/login"))

    # Sign in again, sign out in the panel: the website shows "sign in" again.
    owner_sign_in(page, workspace["login"], workspace["password"])
    page.wait_for_url(re.compile(rf"^{re.escape(OWNER)}/?$"), timeout=60_000)
    skip_tour(page)
    page.locator('[aria-label="تسجيل الخروج"]').first.click()
    page.wait_for_url(re.compile(r"/login"), timeout=60_000)
    page.goto(WEBSITE)
    expect(page.get_by_text("تسجيل الدخول").first).to_be_visible()
    expect(page.get_by_text("العودة إلى لوحتك")).to_have_count(0)


def test_a_suspended_workspace_cannot_sign_in_until_reactivated(page: Page, workspace, platform_admin):
    def status() -> int:
        return erp_login(workspace["slug"], workspace["login"], workspace["password"]).status_code

    assert status() == 200
    page.goto(f"{ADMIN}/")
    page.locator("input").nth(0).fill(platform_admin["login"])
    page.locator("input[type=password]").fill(platform_admin["password"])
    page.locator("button[type=submit]").click()
    expect(page.get_by_text("Overview").first).to_be_visible(timeout=30_000)

    page.goto(f"{ADMIN}/workspaces/{workspace['id']}")
    root = page.locator("#root")  # the page itself, not the confirmation dialog
    root.get_by_role("button", name="Suspend", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Suspend workspace").click()
    expect(root.get_by_role("button", name="Reactivate", exact=True)).to_be_visible()
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert status() in (401, 403)

    # The workspace's own sign-in page refuses too (refused, not rate-limited: see erp_login).
    staff = page.context.new_page()
    staff.goto(workspace_url(workspace["slug"], "/login"))
    staff.locator("input").nth(0).fill(workspace["login"])
    staff.locator("input[type=password]").fill(workspace["password"])
    for _ in range(3):
        with staff.expect_response(lambda r: r.url.endswith("/auth/login")) as answer:
            staff.locator("button[type=submit]").click()
        if answer.value.status != 429:
            break
        staff.wait_for_timeout(retry_after(answer.value) * 1000)
    assert answer.value.status in (401, 403)
    staff.wait_for_timeout(1000)
    assert "/login" in staff.url
    staff.close()

    root.get_by_role("button", name="Reactivate", exact=True).click()
    page.get_by_role("dialog").get_by_role("button", name="Reactivate", exact=True).click()
    expect(root.get_by_role("button", name="Suspend", exact=True)).to_be_visible()
    assert status() == 200
