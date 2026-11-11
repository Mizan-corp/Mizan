"""One permission system, acting as one role at a time (ADR-006 phase 3, #94)."""
from helpers import Api, uid

from conftest import admin_api, reg, db  # noqa: F401


def _roles(api) -> dict:
    return {r["code"]: r for r in api.ok(api.get("/authz/access/roles"))}


def _user(admin_api, reg, role="cashier"):
    name = f"e2e_{role}_{uid('r')[-6:]}"
    u = admin_api.ok(admin_api.post("/users", json={"username": name, "full_name": "E2E " + role, "role": role,
                                                     "password": "E2eRole9!"}), 200, 201)
    reg.add("user", u["id"])
    api = Api()
    api.login(name, "E2eRole9!")
    return u, api


def test_nobody_holds_star(admin_api):
    me = admin_api.ok(admin_api.get("/auth/me"))
    assert "*" not in me["permissions"]
    assert me["acting_role"]["code"] == "admin" and "finance" in me["permissions"]


def test_admin_acting_as_cashier_cannot_reach_finance_or_clinical(admin_api, reg, db):
    roles = _roles(admin_api)
    u, api = _user(admin_api, reg, "admin")
    admin_api.ok(admin_api.put(f"/authz/access/users/{u['id']}/roles",
                               json={"role_ids": [roles["admin"]["id"], roles["cashier"]["id"]]}))
    safe = {"name": "E2E-SAFE-" + uid("s"), "location": "e2e"}

    switched = api.ok(api.post("/auth/me/acting-role", json={"role_id": roles["cashier"]["id"]}))
    assert switched["acting_role"]["code"] == "cashier"
    assert api.post("/safes", json=safe).status_code == 403      # finance
    assert api.get("/users").status_code == 403                 # user management
    assert api.get("/clinic/patients").status_code in (403, 404)  # clinical records (403 if the module is on)
    assert api.get("/sales").status_code == 200                  # what a cashier does

    api.ok(api.post("/auth/me/acting-role", json={"role_id": roles["admin"]["id"]}))
    created = api.ok(api.post("/safes", json=safe), 200, 201)
    reg.add("safe", created["id"])
    logged = db.one("SELECT count(*) FROM audit_log WHERE entity_id = %s AND action = 'switch_role'", (u["id"],))
    assert logged[0] == 2


def test_cannot_act_as_an_unassigned_role(admin_api, reg):
    roles = _roles(admin_api)
    _, api = _user(admin_api, reg, "cashier")
    r = api.post("/auth/me/acting-role", json={"role_id": roles["admin"]["id"]})
    assert r.status_code == 403, r.text[:200]


def test_no_privilege_escalation(admin_api, reg):
    roles = _roles(admin_api)
    clerk_role = admin_api.ok(admin_api.post("/authz/access/roles", json={"name": "E2E user clerk " + uid("q"), "grants": ["users"]}), 201)
    u, api = _user(admin_api, reg, "cashier")
    admin_api.ok(admin_api.put(f"/authz/access/users/{u['id']}/roles", json={"role_ids": [clerk_role["id"]]}))
    api.ok(api.post("/auth/me/acting-role", json={"role_id": clerk_role["id"]}))

    assert api.post("/authz/access/roles", json={"name": "E2E grab", "grants": ["finance"]}).status_code == 403
    r = api.put(f"/authz/access/users/{u['id']}/roles", json={"role_ids": [roles["admin"]["id"]]})
    assert r.status_code == 403, r.text[:200]
    assert api.put(f"/authz/access/roles/{roles['admin']['id']}", json={"grants": ["users"]}).status_code == 403

    admin_api.ok(admin_api.put(f"/authz/access/users/{u['id']}/roles", json={"role_ids": [roles["cashier"]["id"]]}))
    assert admin_api.delete(f"/authz/access/roles/{clerk_role['id']}").status_code == 204


def test_custom_permission_list_becomes_a_personal_role(admin_api, reg):
    u, api = _user(admin_api, reg, "cashier")
    admin_api.ok(admin_api.put(f"/permissions/{u['id']}", json={"permissions": ["pos", "reports"], "is_manager": False}))
    assert admin_api.ok(admin_api.get(f"/permissions/{u['id']}"))["permissions"] == ["pos", "reports"]
    me = api.ok(api.get("/auth/me"))
    assert me["permissions"] == ["pos", "reports"] and me["acting_role"]["code"].startswith("cashier-")
