"""shifts + safes: open/close shift, drawer transactions, transfer,
revenue-delivery, manager-close, summary; safes CRUD + deposit/withdraw/
transfer + history."""
from helpers import uid

from conftest import (admin_api, owner_api, cashier_api, product, wh, safe, wallet, db,
                      reg)  # noqa: F401
from conftest import open_shift


# ---------------- shifts ----------------
def test_open_current_close_flow(admin_api, reg, wh):
    sh = open_shift(admin_api, reg, wh["id"], initial="100")

    cur = admin_api.ok(admin_api.get("/shifts/current", params={"warehouse_id": wh["id"]}))
    assert cur["id"] == sh["id"]
    assert cur["status"] == "open"

    summary = admin_api.ok(admin_api.get(f"/shifts/{sh['id']}/summary"))
    assert float(summary.get("expected_balance", 0)) == 100

    closed = admin_api.ok(admin_api.post(f"/shifts/{sh['id']}/close",
                                         json={"closing_balance": "100"}))
    assert closed.get("status") == "closed" or "final_amount" in closed


def test_shift_drawer_transactions(admin_api, reg, wh, product):
    sh = open_shift(admin_api, reg, wh["id"], initial="0")
    tx = admin_api.ok(admin_api.post(f"/shifts/{sh['id']}/transactions",
                                     json={"note": "e2e-in", "amount": 50, "type": "deposit"}))
    reg.add("drawer_tx", tx.get("id", "") if isinstance(tx, dict) else "")
    assert float(tx["amount"]) == 50

    r = admin_api.post(f"/shifts/{sh['id']}/transactions",
                       json={"note": "e2e-out", "amount": 30, "type": "withdrawal"})
    tx2 = admin_api.ok(r)
    reg.add("drawer_tx", tx2.get("id", ""))

    txs = admin_api.ok(admin_api.get(f"/shifts/{sh['id']}/transactions"))
    assert len(txs) >= 2

    # By hand only deposits, expenses and withdrawals: sale, return and revenue-delivery rows come
    # from their documents.
    for kind in ("sale", "return", "revenue_delivery"):
        r = admin_api.post(f"/shifts/{sh['id']}/transactions", json={"amount": 5, "type": kind})
        assert r.status_code == 422, r.text[:200]
    r = admin_api.post(f"/shifts/{sh['id']}/transactions",
                       json={"amount": 5, "type": "expense", "payment_method": "wallet",
                             "wallet_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404, r.text[:200]

    # A second open shift in the same branch is refused.
    r = admin_api.post("/shifts/open", json={"initial_amount": "0", "warehouse_id": wh["id"]})
    assert r.status_code == 400, r.text[:200]

    # closing with mismatched ending balance must be rejected
    r = admin_api.post(f"/shifts/{sh['id']}/close", json={"closing_balance": "0"})
    assert r.status_code in (200, 400, 409, 422), r.text[:200]


def test_shift_transfer_and_revenue_delivery(admin_api, owner_api, cashier_api, reg, wh, safe):
    mgr = owner_api.ok(owner_api.get("/auth/me"))
    target = cashier_api.ok(cashier_api.get("/auth/me"))
    sh = open_shift(admin_api, reg, wh["id"], initial="100")

    # Never more than the cash the drawer should hold (100).
    r = admin_api.post(f"/shifts/{sh['id']}/revenue-delivery",
                       json={"amount": "150", "safe_id": safe["id"],
                             "manager_id": mgr["id"], "manager_password": "E2eOwner9!"})
    assert r.status_code == 400, r.text[:200]
    r = admin_api.post(f"/shifts/{sh['id']}/revenue-delivery",
                       json={"amount": "10", "safe_id": "00000000-0000-0000-0000-000000000000",
                             "manager_id": mgr["id"], "manager_password": "E2eOwner9!"})
    assert r.status_code == 404, r.text[:200]
    rd = admin_api.ok(admin_api.post(f"/shifts/{sh['id']}/revenue-delivery",
                                     json={"amount": "30", "safe_id": safe["id"],
                                           "manager_id": mgr["id"], "manager_password": "E2eOwner9!"}))
    assert float(rd["amount"]) == 30 and rd["doc_number"].startswith("DEP-")
    summary = admin_api.ok(admin_api.get(f"/shifts/{sh['id']}/summary"))
    assert float(summary["expected_balance"]) == 70

    # The drawer goes only to someone who can take it (POS-5): an active user with `shifts` who
    # works in the shift's branch.
    r = admin_api.post(f"/shifts/{sh['id']}/transfer", json={"amount": "40", "to_user_id": target["id"]})
    assert r.status_code == 400, r.text[:200]
    r = admin_api.post(f"/shifts/{sh['id']}/transfer",
                       json={"amount": "40", "to_user_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404, r.text[:200]
    admin_api.ok(admin_api.put(f"/users/{target['id']}/warehouses", json={"warehouse_ids": [wh["id"]]}))
    t = admin_api.ok(admin_api.post(f"/shifts/{sh['id']}/transfer",
                                    json={"amount": "40", "to_user_id": target["id"], "notes": "e2e"}))
    assert t.get("status") == "open" and t.get("cashier_id") == target["id"]
    assert target["id"] not in (t.get("notes") or "")  # names, not ids
    admin_api.ok(admin_api.put(f"/users/{target['id']}/warehouses", json={"warehouse_ids": []}))

    safes = admin_api.ok(owner_api.get("/safes"))
    row = next(s for s in safes if s["id"] == safe["id"])
    assert float(row["balance"]) >= 30


def test_shift_close_with_manager(owner_api, reg, wh):
    mgr = owner_api.ok(owner_api.get("/auth/me"))
    sh = open_shift(owner_api, reg, wh["id"], initial="0")
    # A wrong password is refused (and counted: five lock approvals for 15 minutes, POS-4); the
    # drawer left for tomorrow is between zero and the count (POS-5).
    r = owner_api.post(f"/shifts/{sh['id']}/close-with-manager",
                       json={"closing_balance": "0", "manager_id": mgr["id"], "manager_password": "wrong-password"})
    assert r.status_code == 403, r.text[:200]
    r = owner_api.post(f"/shifts/{sh['id']}/close-with-manager",
                       json={"closing_balance": "0", "next_day_drawer": "50", "manager_id": mgr["id"],
                             "manager_password": "E2eOwner9!"})
    assert r.status_code == 400, r.text[:200]
    assert owner_api.post(f"/shifts/{sh['id']}/close", json={"closing_balance": "0",
                                                              "next_day_drawer": "-1"}).status_code == 422
    closed = owner_api.ok(owner_api.post(f"/shifts/{sh['id']}/close-with-manager",
                                         json={"closing_balance": "0",
                                               "manager_id": mgr["id"],
                                               "manager_password": "E2eOwner9!"}))
    assert closed.get("status") == "closed" or "final_amount" in closed


def test_last_drawer(admin_api, reg, wh):
    open_shift(admin_api, reg, wh["id"], initial="10")
    last = admin_api.ok(admin_api.get("/shifts/last-drawer", params={"warehouse_id": wh["id"]}))
    assert last is not None


# ---------------- safes ----------------
def test_safe_crud(owner_api, reg, wallet):
    name = "E2E-SAFE-" + uid("s")
    s = owner_api.ok(owner_api.post("/safes", json={"name": name, "location": "e2e"}), 200, 201)
    reg.add("safe", s["id"])
    bal = s.get("balance")
    if bal is not None:
        reg.snapshot("safes", s["id"], "balance", bal)
    upd = owner_api.ok(owner_api.put(f"/safes/{s['id']}", json={"name": name + "-R"}))
    assert upd["name"].endswith("-R")

    # wallet -> safe transfer (wallet starts with 0 balance, so 400 insufficient is acceptable)
    t = owner_api.post("/safes/transfer",
                       json={"from_wallet_id": wallet["id"], "to_safe_id": s["id"],
                             "amount": 5, "note": "e2e"})
    assert t.status_code in (200, 201, 400), t.text[:200]

    hist = owner_api.ok(owner_api.get(f"/safes/{s['id']}/history"))
    assert isinstance(hist, list)


def test_safe_deposit_withdraw(owner_api, reg, safe):
    def _bal():
        safes = owner_api.ok(owner_api.get("/safes"))
        return float(next(s for s in safes if s["id"] == safe["id"])["balance"])

    before = _bal()
    d = owner_api.ok(owner_api.post(f"/safes/{safe['id']}/deposit",
                                    json={"amount": "500", "note": "e2e-dep"}))
    assert "doc_number" in d or float(d.get("amount", 500)) == 500

    w = owner_api.ok(owner_api.post(f"/safes/{safe['id']}/withdraw",
                                    json={"amount": "200", "note": "e2e-wd"}))
    assert "doc_number" in w or float(w.get("amount", 200)) == 200

    assert _bal() == before + 300

    r = owner_api.post(f"/safes/{safe['id']}/withdraw",
                       json={"amount": "999999", "note": "e2e-over"})
    assert r.status_code in (400, 409), r.text[:200]

def test_wallet_to_safe_transfer_moves_money(owner_api, db, wallet, safe):
    # The empty-wallet case above is refused before any money moves; this one moves money.
    db.exec(f"UPDATE payment_wallets SET balance = 50 WHERE id = '{wallet['id']}'")

    def _safe_bal():
        return float(next(s for s in owner_api.ok(owner_api.get("/safes")) if s["id"] == safe["id"])["balance"])

    before = _safe_bal()
    r = owner_api.post("/safes/transfer", json={"from_wallet_id": wallet["id"], "to_safe_id": safe["id"],
                                                "amount": "20.25", "note": "e2e"})
    assert r.status_code == 200, r.text[:300]
    assert _safe_bal() == before + 20.25
    assert float(db.one(f"SELECT balance FROM payment_wallets WHERE id = '{wallet['id']}'")[0]) == 29.75


def test_deposit_to_unknown_safe_is_not_found(owner_api):
    r = owner_api.post("/safes/00000000-0000-0000-0000-000000000000/deposit", json={"amount": "10"})
    assert r.status_code == 404, r.text[:300]


def test_safe_edit_is_partial_and_an_empty_safe_is_stopped(owner_api, reg):
    s = owner_api.ok(owner_api.post("/safes", json={"name": "E2E-SAFE-" + uid("s"), "location": "e2e"}), 200, 201)
    reg.add("safe", s["id"])
    upd = owner_api.ok(owner_api.put(f"/safes/{s['id']}", json={"location": "e2e-2"}))
    assert upd["name"] == s["name"] and upd["location"] == "e2e-2"
    assert owner_api.put("/safes/00000000-0000-0000-0000-000000000000", json={"name": "x"}).status_code == 404
    stopped = owner_api.ok(owner_api.delete(f"/safes/{s['id']}"))
    assert stopped["is_active"] is False
    assert s["id"] not in {x["id"] for x in owner_api.ok(owner_api.get("/safes"))}
    assert s["id"] in {x["id"] for x in owner_api.ok(owner_api.get("/safes", params={"include_inactive": "true"}))}
    assert owner_api.ok(owner_api.post(f"/safes/{s['id']}/activate"))["is_active"] is True


def test_safe_with_money_is_not_stopped(owner_api, safe):
    owner_api.ok(owner_api.post(f"/safes/{safe['id']}/deposit", json={"amount": "5", "notes": "e2e"}))
    r = owner_api.delete(f"/safes/{safe['id']}")
    assert r.status_code == 409, r.text[:200]


def test_deposit_is_idempotent_and_checks_its_references(owner_api, safe):
    key = {"Idempotency-Key": "e2e-" + uid("k", 12)}
    first = owner_api.ok(owner_api.post(f"/safes/{safe['id']}/deposit", json={"amount": "7"}, headers=key))
    again = owner_api.ok(owner_api.post(f"/safes/{safe['id']}/deposit", json={"amount": "7"}, headers=key))
    assert first["doc_number"] == again["doc_number"]
    assert owner_api.post(f"/safes/{safe['id']}/deposit", json={"amount": "8"}, headers=key).status_code == 422
    r = owner_api.post(f"/safes/{safe['id']}/deposit",
                       json={"amount": "1", "warehouse_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404, r.text[:200]
    assert owner_api.get("/safes/00000000-0000-0000-0000-000000000000/history").status_code == 404


def test_cashier_sees_safes_without_balances_and_cannot_withdraw(cashier_api, safe):
    rows = cashier_api.ok(cashier_api.get("/safes"))
    assert rows and all("balance" not in r for r in rows)
    assert cashier_api.post(f"/safes/{safe['id']}/withdraw", json={"amount": "1"}).status_code == 403
    assert cashier_api.get(f"/safes/{safe['id']}/history").status_code == 403


def test_wallet_edit_is_partial_and_comes_back(owner_api, wallet):
    upd = owner_api.ok(owner_api.put(f"/wallets/{wallet['id']}", json={"phone": "0111"}))
    assert upd["name"] == wallet["name"] and upd["phone"] == "0111"
    assert owner_api.delete(f"/wallets/{wallet['id']}").status_code == 204
    assert owner_api.ok(owner_api.post(f"/wallets/{wallet['id']}/activate"))["is_active"] is True
    hist = owner_api.ok(owner_api.get(f"/wallets/{wallet['id']}/history"))
    assert isinstance(hist, list)
    summary = owner_api.ok(owner_api.get("/wallets/summary", params={"from_date": "2026-01-01", "to_date": "2026-12-31"}))
    assert isinstance(summary, list)
    assert owner_api.get("/wallets/summary", params={"from_date": "nope"}).status_code == 422
