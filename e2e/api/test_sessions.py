"""Server-side sign-out and ending sessions (#77); the owner's password is changed in one place
(#75); payroll reports need a print token with the payroll permission."""
from helpers import Api, uid

from conftest import admin_api, reg, db  # noqa: F401

PASSWORD = "E2eSess9!"


def _user(admin_api, reg, role="cashier"):
    name = f"e2e_sess_{uid('s')[-6:]}"
    u = admin_api.ok(admin_api.post("/users", json={"username": name, "full_name": "E2E session", "role": role,
                                                     "password": PASSWORD}), 200, 201)
    reg.add("user", u["id"])
    return u, name


def _session(name, password=PASSWORD) -> Api:
    a = Api()
    a.login(name, password)
    return a


def test_sign_out_ends_the_token_on_the_server(admin_api, reg):
    _, name = _user(admin_api, reg)
    one, two = _session(name), _session(name)
    token = one.token
    assert one.post("/auth/logout").status_code == 204

    reused = Api(token=token)  # a copy of the signed-out token, without the cookie
    assert reused.get("/auth/me").status_code == 401
    assert two.get("/auth/me").status_code == 200  # other sessions continue


def test_password_change_ends_other_sessions_and_keeps_this_one(admin_api, reg):
    _, name = _user(admin_api, reg)
    mine, other = _session(name), _session(name)
    r = mine.put("/auth/me/password", json={"current_password": PASSWORD, "new_password": "E2eSess9!new"})
    body = mine.ok(r)
    assert other.get("/auth/me").status_code == 401

    fresh = Api(token=body["access_token"])
    assert fresh.get("/auth/me").status_code == 200
    _session(name, "E2eSess9!new")


def test_reset_by_an_admin_ends_the_users_sessions(admin_api, reg):
    u, name = _user(admin_api, reg)
    before = _session(name)
    # The users screen sends new_password (it used to fail validation).
    r = admin_api.post(f"/users/{u['id']}/reset-password", json={"new_password": "E2eReset9!x"})
    assert r.status_code == 204, r.text[:200]
    assert before.get("/auth/me").status_code == 401
    _session(name, "E2eReset9!x")


def test_owner_logins_change_their_password_in_the_owner_panel(admin_api, reg, db):
    u, name = _user(admin_api, reg)
    owner = db.one("SELECT id FROM owner_accounts ORDER BY created_at LIMIT 1")
    if not owner:
        return
    db.q("UPDATE users SET owner_account_id = %s WHERE id = %s", (owner[0], u["id"]))
    try:
        r = admin_api.post(f"/users/{u['id']}/reset-password", json={"new_password": "E2eReset9!y"})
        assert r.status_code == 409, r.text[:200]
        mine = _session(name)
        r = mine.put("/auth/me/password", json={"current_password": PASSWORD, "new_password": "E2eSess9!zz"})
        assert r.status_code == 409, r.text[:200]
    finally:
        db.q("UPDATE users SET owner_account_id = NULL WHERE id = %s", (u["id"],))


def test_payroll_report_needs_a_print_token_with_payroll(admin_api, reg):
    month = "2026-01"
    path = "/hr/payroll/report/monthly"
    assert Api().get(path, params={"month": month}).status_code == 401

    session_token = admin_api.token  # a session token is not a print token
    assert Api().get(path, params={"month": month, "token": session_token}).status_code == 403

    _, name = _user(admin_api, reg, "cashier")
    cashier = _session(name)
    cashier_print = cashier.ok(cashier.post("/auth/print-token", json={}))["token"]
    assert Api().get(path, params={"month": month, "token": cashier_print}).status_code == 403

    admin_print = admin_api.ok(admin_api.post("/auth/print-token", json={}))["token"]
    assert Api().get(path, params={"month": month, "token": admin_print}).status_code == 200
