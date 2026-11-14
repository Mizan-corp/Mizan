"""expenses module: financial categories, expense vendors, expense CRUD,
approval flow, summary."""
from helpers import uid

from conftest import (admin_api, owner_api, safe, wallet,
                      reg)  # noqa: F401


def test_financial_category_crud(owner_api, reg):
    name = "E2E-FCAT-" + uid("f")
    c = owner_api.ok(owner_api.post("/financial-categories",
                                    json={"name": name, "type": "expense"}))
    reg.add("financial_category", c["id"])
    assert c["name"] == name

    upd = owner_api.ok(owner_api.put(f"/financial-categories/{c['id']}",
                                     json={"name": name + "-R"}))
    assert upd.get("name", "").endswith("-R") or upd.get("detail") == "updated"

    # cannot delete a category in use later; plain delete works on empty one
    owner_api.ok(owner_api.delete(f"/financial-categories/{c['id']}"), 200, 204)


def test_expense_vendor_crud(owner_api, reg):
    name = "E2E-VEND-" + uid("v")
    v = owner_api.ok(owner_api.post("/expense-vendors",
                                    json={"name": name, "phone": "010"}), 200, 201)
    reg.add("expense_vendor", v["id"])
    upd = owner_api.ok(owner_api.put(f"/expense-vendors/{v['id']}",
                                     json={"name": name + "-R"}))
    assert upd["name"].endswith("-R")


def test_expense_create_approve(owner_api, reg, safe, wallet):
    cat = owner_api.ok(owner_api.post("/financial-categories",
                                      json={"name": "E2E-EXP-" + uid("x"), "type": "expense"}))
    reg.add("financial_category", cat["id"])
    v = owner_api.ok(owner_api.post("/expense-vendors",
                                    json={"name": "E2E-VEND-" + uid("v")}), 200, 201)
    reg.add("expense_vendor", v["id"])

    payload = {
        "vendor_id": v["id"],
        "amount": "150",
        "category_id": cat["id"],
        "payment_method": "safe",
        "safe_id": safe["id"],
        "description": "e2e expense",
    }
    e = owner_api.ok(owner_api.post("/expenses", json=payload), 200, 201)
    reg.add("expense", e["id"])
    assert "id" in e

    lst = owner_api.ok(owner_api.get("/expenses"))
    rows = lst if isinstance(lst, list) else lst.get("data", [])
    assert any(x["id"] == e["id"] for x in rows)

    upd = owner_api.ok(owner_api.put(f"/expenses/{e['id']}",
                                     json={"description": "e2e updated"}))
    assert upd["description"].startswith("e2e up")

    appr = owner_api.ok(owner_api.post(f"/expenses/{e['id']}/approve", json={}))
    assert appr is not None

    summ = owner_api.ok(owner_api.get("/expenses/summary"))
    assert "items" in summ or isinstance(summ, dict)

    # an approved expense is cancelled (its money goes back), never deleted (ADR-014 D4)
    r = owner_api.delete(f"/expenses/{e['id']}")
    assert r.status_code == 409, r.text[:200]
    cancelled = owner_api.ok(owner_api.post(f"/expenses/{e['id']}/cancel", json={"reason": "e2e"}))
    assert cancelled["status"] == "cancelled"


def test_expense_wallet_payment(owner_api, reg, wallet):
    c = owner_api.ok(owner_api.post("/financial-categories",
                                    json={"name": "E2E-WX-" + uid("y"), "type": "expense"}))
    reg.add("financial_category", c["id"])
    v = owner_api.ok(owner_api.post("/expense-vendors",
                                    json={"name": "E2E-VEND-" + uid("v")}), 200, 201)
    reg.add("expense_vendor", v["id"])
    before = float(wallet["balance"])

    e = owner_api.ok(owner_api.post("/expenses", json={
        "vendor_id": v["id"], "amount": "40", "category_id": c["id"],
        "payment_method": "wallet", "wallet_id": wallet["id"], "description": "e2e"}), 200, 201)
    reg.add("expense", e["id"])

    # wallet starts with 0 balance -> approving must be rejected, balance untouched
    appr = owner_api.post(f"/expenses/{e['id']}/approve", json={"approved": True})
    assert appr.status_code in (400, 409), appr.text[:200]
    lst = owner_api.ok(owner_api.get("/wallets"))
    row = next(w for w in lst if w["id"] == wallet["id"])
    assert float(row["balance"]) == before
    # ...and the expense is not left approved-but-unpaid.
    lst = owner_api.ok(owner_api.get("/expenses"))
    exp = next(x for x in (lst if isinstance(lst, list) else lst.get("data", [])) if x["id"] == e["id"])
    assert exp["status"] == "draft", exp["status"]

def test_approved_expense_is_paid_once(owner_api, reg, safe):
    v = owner_api.ok(owner_api.post("/expense-vendors", json={"name": "E2E-VEND-" + uid("v")}), 200, 201)
    reg.add("expense_vendor", v["id"])
    e = owner_api.ok(owner_api.post("/expenses", json={
        "vendor_id": v["id"], "amount": "30", "payment_method": "safe", "safe_id": safe["id"],
        "description": "e2e once"}), 200, 201)
    reg.add("expense", e["id"])

    def _bal():
        return float(next(s for s in owner_api.ok(owner_api.get("/safes")) if s["id"] == safe["id"])["balance"])

    before = _bal()
    owner_api.ok(owner_api.post(f"/expenses/{e['id']}/approve", json={"approved": True}))
    again = owner_api.post(f"/expenses/{e['id']}/approve", json={"approved": True})
    assert again.status_code == 409, again.text[:200]
    assert _bal() == before - 30
