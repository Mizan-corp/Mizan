"""The first storefront is out of service (ADR-015 step S0, docs/PRODUCTION_READINESS.md STO-0): its
public order tracking exposed customers' names and addresses and its orders never reached stock, cash
or the ledger. Until the website builder replaces it, none of its routes answer and no workspace can
switch it on."""
import httpx

from helpers import BASE

from conftest import admin_api  # noqa: F401


def test_the_public_storefront_routes_do_not_answer(admin_api):  # noqa: F811
    slug = admin_api.ok(admin_api.get("/auth/me"))["tenant"]["slug"]
    with httpx.Client(base_url=BASE, timeout=30) as c:
        for path in (f"/storefront/{slug}/config", f"/storefront/{slug}/products",
                     f"/storefront/{slug}/orders/ORD-202611-1234"):
            assert c.get(path).status_code == 404, path
        r = c.post(f"/storefront/{slug}/checkout", json={"customer_name": "x", "customer_phone": "01000000000", "items": []})
        assert r.status_code in (403, 404, 405), r.status_code


def test_the_storefront_can_not_be_switched_on(admin_api):  # noqa: F811
    # Not mounted (a workspace that had it before keeps the id in its list, harmlessly) and not offered.
    assert admin_api.get("/modules/storefront/config").status_code == 404
    r = admin_api.post("/modules/storefront/toggle", json={"enabled": True})
    assert r.status_code in (400, 403, 404), r.text
