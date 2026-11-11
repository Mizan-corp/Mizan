"""Public shop (/storefront/<workspace>/…): only a workspace that uses the storefront
module and hasn't closed its shop is public; the old slug-less /store/* is gone (#95)."""
import httpx
import pytest

from helpers import BASE

from conftest import product  # noqa: F401
from conftest import admin_api, cashier_api, reg  # noqa: F401


def _public(path: str) -> httpx.Response:
    with httpx.Client(base_url=BASE, timeout=30) as c:
        return c.get(path)


def _set_open(api, is_open: bool) -> httpx.Response:
    cfg = api.ok(api.get("/modules/storefront/config"))["config"]
    return api.put("/modules/storefront/config", json={**cfg, "is_active": is_open})


@pytest.fixture()
def shop(admin_api):  # noqa: F811
    """The admin's workspace with the storefront module on and the shop open; restored after."""
    slug = admin_api.ok(admin_api.get("/auth/me"))["tenant"]["slug"]
    was_on = "storefront" in admin_api.ok(admin_api.get("/modules"))["active_modules"]
    if not was_on:
        admin_api.ok(admin_api.post("/modules/storefront/toggle", json={"enabled": True}))
    was_open = admin_api.ok(admin_api.get("/modules/storefront/config"))["config"]["is_active"]
    if not was_open:
        admin_api.ok(_set_open(admin_api, True))
    yield slug
    if not was_open:
        _set_open(admin_api, False)
    if not was_on:
        admin_api.post("/modules/storefront/toggle", json={"enabled": False})


def test_old_slugless_store_is_gone():
    for path in ("/store/products", "/store/categories", "/storefront"):
        assert _public(path).status_code == 404, path


def test_unknown_shop_is_not_found():
    assert _public("/storefront/no-such-workspace-e2e/products").status_code == 404


def test_open_shop_lists_products_and_categories(shop, product):  # noqa: F811
    assert _public(f"/storefront/{shop}/config").status_code == 200
    r = _public(f"/storefront/{shop}/products")
    assert r.status_code == 200, r.text[:200]
    r = _public(f"/storefront/{shop}/products?search={product['name']}")
    assert [p["id"] for p in r.json()["items"]] == [product["id"]]
    assert isinstance(_public(f"/storefront/{shop}/categories").json(), list)


def test_closed_or_disabled_shop_is_private(admin_api, shop):  # noqa: F811
    admin_api.ok(_set_open(admin_api, False))
    try:
        assert _public(f"/storefront/{shop}/products").status_code == 404
        assert _public(f"/storefront/{shop}/config").status_code == 404
    finally:
        admin_api.ok(_set_open(admin_api, True))

    # Removing a module goes through the uninstall flow (ADR-006 D2); its data is kept.
    admin_api.ok(admin_api.post("/modules/storefront/uninstall", json={"confirm": "delete", "data": "keep"}))
    try:
        assert _public(f"/storefront/{shop}/products").status_code == 404
    finally:
        admin_api.ok(admin_api.post("/modules/storefront/toggle", json={"enabled": True}))


def test_cashier_can_see_orders_but_not_change_the_shop(cashier_api, shop):  # noqa: F811
    assert cashier_api.get("/modules/storefront/orders").status_code == 200
    assert cashier_api.put("/modules/storefront/config", json={"store_title": "x", "is_active": False}).status_code == 403
    r = cashier_api.post("/modules/storefront/coupons", json={
        "code": "E2E-NOPE", "discount_percent": 50,
    })
    assert r.status_code == 403
