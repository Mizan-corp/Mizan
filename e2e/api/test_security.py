"""security / permission matrix: role gating per module and auth requirements."""
import uuid

import httpx

from helpers import BASE, Api

from conftest import admin_api, owner_api, cashier_api, db, reg  # noqa: F401


def test_unauthenticated_is_rejected():
    with httpx.Client(base_url=BASE, timeout=30) as c:
        for path in ("/sales", "/users", "/products", "/admin/overview"):
            r = c.get(path)
            assert r.status_code in (401, 403), f"{path}: {r.status_code}"


def test_invalid_token_rejected():
    a = Api(token="not-a-real-token")
    r = a.get("/auth/me")
    assert r.status_code in (401, 403), r.text[:200]


def test_cashier_allowed_and_denied(cashier_api, wh, product):
    # allowed: sales (list) + customers
    assert cashier_api.get("/sales").status_code == 200
    assert cashier_api.get("/customers").status_code in (200,)

    # denied: inventory writes, user management, settings, finance, payroll
    cases = [
        ("post", "/products", {"subcategory_id": None, "name": "x",
                               "retail_price": "1", "cost_price": "1"}),
        ("post", "/stock/warehouses", {"code": "x", "name": "x"}),
        ("get", "/users", None),
        ("post", "/wallets", {"name": "x", "type": "y"}),
        ("post", "/hr/employees", {"name": "x", "position": "x"}),
        ("post", "/financial-categories", {"name": "x", "type": "expense"}),
    ]
    for method, path, body in cases:
        r = getattr(cashier_api, method)(path, json=body) if body is not None \
            else getattr(cashier_api, method)(path)
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}: {r.text[:150]}"


def test_staff_without_finance_cannot_create_wallets(cashier_api):
    r = cashier_api.post("/wallets", json={"name": "x", "type": "y"})
    assert r.status_code == 403, r.text[:200]


def test_workspace_admin_manages_wallets_and_duplicates_are_409(admin_api, db):
    # Workspace admins have every permission (require_perm); a taken name is a 409, not a 500.
    name = f"e2e wallet {uuid.uuid4().hex[:6]}"
    r = admin_api.post("/wallets", json={"name": name, "type": "vodafone"})
    assert r.status_code == 201, r.text[:200]
    wallet = r.json()
    try:
        assert wallet["tenant_id"], "the wallet belongs to the admin's workspace"
        again = admin_api.post("/wallets", json={"name": name, "type": "vodafone"})
        assert again.status_code == 409, again.text[:200]
        # Deleting only deactivates; adding the same name again brings it back.
        assert admin_api.delete(f"/wallets/{wallet['id']}").status_code == 204
        revived = admin_api.post("/wallets", json={"name": name, "type": "orange"})
        assert revived.status_code == 201 and revived.json()["id"] == wallet["id"], revived.text[:200]
    finally:
        db.exec(f"DELETE FROM payment_wallets WHERE id='{uuid.UUID(wallet['id'])}'")


def test_owner_with_finance_is_allowed(owner_api):
    r = owner_api.get("/wallets")
    assert r.status_code == 200


def test_self_delete_forbidden(owner_api, reg):
    me = owner_api.ok(owner_api.get("/auth/me"))
    r = owner_api.delete(f"/users/{me['id']}")
    assert r.status_code in (400, 403), r.text[:200]