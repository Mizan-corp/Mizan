"""accounting (ACC-2, ACC-3): the chart of accounts, category mapping, manual journal entries (draft →
post → reverse), the entries, the reports, the VAT report and the periods, through the live API. The
accounting module is switched on in the e2e workspace for each test and restored after; everything
the tests post is removed by the session's clean-up (acc_* rows are dated and the workspace's)."""
import json
import uuid

import pytest
from helpers import uid

from conftest import admin_api, cashier_api, customer, db, owner_api, reg  # noqa: F401


@pytest.fixture
def accounting(owner_api, db):
    """The e2e workspace with the accounting module on during the test, as it was after."""
    tid = owner_api.ok(owner_api.get("/auth/me"))["tenant_id"]
    started = db.one("SELECT now()")[0]
    before = db.one("SELECT active_modules FROM tenants WHERE id = %s", (tid,))[0]
    modules = before if isinstance(before, list) else json.loads(before or "[]")
    if "accounting" not in modules:
        db.q("UPDATE tenants SET active_modules = %s::jsonb WHERE id = %s", (json.dumps([*modules, "accounting"]), tid))
    try:
        yield tid
    finally:
        db.q("UPDATE tenants SET active_modules = %s::jsonb WHERE id = %s",
             (None if before is None else json.dumps(modules), tid))
        # Posted entries can't be updated (a trigger), so the session's sweep can't clear a reversal's
        # link to its original: the test's drafts and entries go here, reversals first.
        for sql in ("DELETE FROM acc_drafts WHERE tenant_id = %s AND created_at >= %s",
                    "DELETE FROM acc_entries WHERE tenant_id = %s AND created_at >= %s AND reverses_id IS NOT NULL",
                    "DELETE FROM acc_entries WHERE tenant_id = %s AND created_at >= %s"):
            db.q(sql, (tid, started))


def _flat(nodes):
    for n in nodes:
        yield n
        yield from _flat(n["children"])


def _chart(api) -> list[dict]:
    return list(_flat(api.ok(api.get("/accounting/accounts"))))


def _role(chart: list[dict], role: str) -> dict:
    return next(a for a in chart if a["role"] == role)


def _today(db) -> str:
    return db.one("SELECT (now() AT TIME ZONE 'Africa/Cairo')::date")[0].isoformat()


def _line(account, debit=0, credit=0) -> dict:
    return {"account_id": account["id"], "debit": str(debit), "credit": str(credit)}


def test_party_search(owner_api, cashier_api, customer, accounting):
    found = owner_api.ok(owner_api.get("/accounting/parties", params={"type": "customer", "q": customer["name"], "limit": 5}))
    assert [p["id"] for p in found] == [customer["id"]]
    chosen = owner_api.ok(owner_api.get("/accounting/parties", params={"type": "supplier", "limit": 1, "id": customer["id"]}))
    assert len(chosen) <= 1  # a customer's id is no supplier: nothing added
    assert owner_api.get("/accounting/parties", params={"type": "robot"}).status_code == 422
    assert owner_api.get("/accounting/parties", params={"type": "customer", "limit": 51}).status_code == 422
    assert cashier_api.get("/accounting/parties", params={"type": "customer"}).status_code == 403


def test_the_module_answers_only_while_it_is_on(owner_api, db):
    tid = owner_api.ok(owner_api.get("/auth/me"))["tenant_id"]
    modules = db.one("SELECT active_modules FROM tenants WHERE id = %s", (tid,))[0] or []
    if "accounting" in modules:
        pytest.skip("accounting is on in this workspace")
    r = owner_api.get("/accounting/accounts")
    assert r.status_code == 403 and "غير مفعلة" in r.text


def test_accounts_are_added_renamed_stopped_and_categories_mapped(owner_api, cashier_api, reg, accounting):
    chart = _chart(owner_api)
    assert cashier_api.get("/accounting/accounts").status_code == 403
    group = next(a for a in chart if a["code"] == "52" and a["is_group"])  # operating expenses
    code = "E2E-" + uuid.uuid4().hex[:6]
    acc = owner_api.ok(owner_api.post("/accounting/accounts", json={"parent_id": group["id"], "name": "E2E-ACC " + uid("a"),
                                                                     "code": code}), 201)
    assert acc["type"] == "expense" and acc["parent_id"] == group["id"] and acc["is_group"] is False
    assert any(a["id"] == acc["id"] for a in _chart(owner_api))
    # The same number twice, an unknown parent, a non-group parent, bad input; no permission.
    assert owner_api.post("/accounting/accounts", json={"parent_id": group["id"], "name": "x", "code": code}).status_code == 409
    assert owner_api.post("/accounting/accounts", json={"parent_id": str(uuid.uuid4()), "name": "x"}).status_code == 404
    assert owner_api.post("/accounting/accounts", json={"parent_id": acc["id"], "name": "x"}).status_code == 400
    assert owner_api.post("/accounting/accounts", json={"parent_id": group["id"], "name": ""}).status_code == 422
    assert cashier_api.post("/accounting/accounts", json={"parent_id": group["id"], "name": "x"}).status_code == 403

    renamed = owner_api.ok(owner_api.put(f"/accounting/accounts/{acc['id']}", json={"name": "E2E-ACC renamed"}))
    assert renamed["name"] == "E2E-ACC renamed"
    assert owner_api.ok(owner_api.put(f"/accounting/accounts/{acc['id']}", json={"active": False}))["active"] is False
    assert owner_api.ok(owner_api.put(f"/accounting/accounts/{acc['id']}", json={"active": True}))["active"] is True
    # The automatic entries rely on the sales account: it can't be stopped.
    assert owner_api.put(f"/accounting/accounts/{_role(chart, 'sales')['id']}", json={"active": False}).status_code == 400
    assert owner_api.put(f"/accounting/accounts/{uuid.uuid4()}", json={"name": "x"}).status_code == 404

    cat = owner_api.ok(owner_api.post("/financial-categories", json={"name": "E2E-FCAT " + uid("f"), "type": "expense"}))
    reg.add("financial_category", cat["id"])
    mapped = owner_api.ok(owner_api.put(f"/accounting/categories/{cat['id']}/account", json={"account_id": acc["id"]}))
    assert mapped["account_id"] == acc["id"]
    assert owner_api.put(f"/accounting/categories/{cat['id']}/account",
                         json={"account_id": _role(chart, "other_income")["id"]}).status_code == 400  # income account
    assert owner_api.put(f"/accounting/categories/{cat['id']}/account", json={"account_id": group["id"]}).status_code == 400
    assert owner_api.put(f"/accounting/categories/{uuid.uuid4()}/account", json={"account_id": acc["id"]}).status_code == 404
    assert cashier_api.put(f"/accounting/categories/{cat['id']}/account", json={"account_id": None}).status_code == 403
    assert owner_api.ok(owner_api.put(f"/accounting/categories/{cat['id']}/account", json={"account_id": None}))["account_id"] is None


def test_a_manual_entry_is_drafted_posted_listed_reported_and_reversed(owner_api, cashier_api, db, accounting):
    chart = _chart(owner_api)
    expense, income = _role(chart, "other_expenses"), _role(chart, "other_income")
    today, memo = _today(db), "E2E قيد " + uid("j")

    draft = owner_api.ok(owner_api.post("/accounting/drafts", json={
        "date": today, "memo": memo, "lines": [_line(expense, debit=100), _line(income, credit=60)]}), 201)
    assert draft["status"] == "draft" and draft["balanced"] is False and draft["problems"]
    assert owner_api.post(f"/accounting/drafts/{draft['id']}/post").status_code == 400  # unbalanced
    draft = owner_api.ok(owner_api.put(f"/accounting/drafts/{draft['id']}", json={
        "date": today, "memo": memo, "lines": [_line(expense, debit=100), _line(income, credit=100)]}))
    assert draft["balanced"] and draft["problems"] == []
    assert draft["id"] in [d["id"] for d in owner_api.ok(owner_api.get("/accounting/drafts"))["items"]]
    assert owner_api.ok(owner_api.get(f"/accounting/drafts/{draft['id']}"))["memo"] == memo
    assert cashier_api.get("/accounting/drafts").status_code == 403
    assert cashier_api.post(f"/accounting/drafts/{draft['id']}/post").status_code == 403

    posted = owner_api.ok(owner_api.post(f"/accounting/drafts/{draft['id']}/post"))
    entry = posted["entry"]
    assert posted["already"] is False
    again = owner_api.ok(owner_api.post(f"/accounting/drafts/{draft['id']}/post"))
    assert again["already"] is True and again["entry"]["id"] == entry["id"]  # posting twice: the same entry
    assert owner_api.put(f"/accounting/drafts/{draft['id']}", json={"date": today, "lines": []}).status_code == 400
    assert owner_api.delete(f"/accounting/drafts/{draft['id']}").status_code == 400

    listed = owner_api.ok(owner_api.get("/accounting/entries", params={"account_id": expense["id"], "from": today, "to": today}))
    assert entry["id"] in [e["id"] for e in listed["items"]] and listed["total"] >= 1
    detail = owner_api.ok(owner_api.get(f"/accounting/entries/{entry['id']}"))
    assert detail["memo"] == memo and detail["reversed_by"] is None
    assert sorted((ln["debit"], ln["credit"]) for ln in detail["lines"]) == [(0, 100), (100, 0)]
    assert owner_api.get(f"/accounting/entries/{uuid.uuid4()}").status_code == 404
    assert owner_api.get("/accounting/entries", params={"from": "yesterday"}).status_code == 422
    assert cashier_api.get(f"/accounting/entries/{entry['id']}").status_code == 403

    ledger = owner_api.ok(owner_api.get(f"/accounting/general-ledger/{expense['id']}", params={"from": today, "to": today}))
    assert entry["id"] in [ln["entry_id"] for ln in ledger["lines"]]
    tb = owner_api.ok(owner_api.get("/accounting/trial-balance", params={"from": today, "to": today}))
    assert tb["balanced"] and tb["totals"]["debit"] == tb["totals"]["credit"]
    assert owner_api.ok(owner_api.get("/accounting/balance-sheet"))["balanced"]
    assert isinstance(owner_api.ok(owner_api.get("/accounting/income-statement", params={"from": today, "to": today})), dict)
    assert "items" in owner_api.ok(owner_api.get("/accounting/reconciliation"))
    for path in ("/accounting/trial-balance", "/accounting/income-statement", "/accounting/balance-sheet",
                 "/accounting/reconciliation", f"/accounting/general-ledger/{expense['id']}"):
        assert cashier_api.get(path).status_code == 403, path

    # A cashier can't reverse; the owner reverses once, and the reversal links both ways.
    assert cashier_api.post(f"/accounting/entries/{entry['id']}/reverse", json={}).status_code == 403
    rev = owner_api.ok(owner_api.post(f"/accounting/entries/{entry['id']}/reverse", json={"memo": "E2E عكس"}))
    assert rev["already"] is False
    assert owner_api.ok(owner_api.post(f"/accounting/entries/{entry['id']}/reverse", json={}))["already"] is True
    assert owner_api.ok(owner_api.get(f"/accounting/entries/{entry['id']}"))["reversed_by"] == rev["entry"]["id"]
    reversal = owner_api.ok(owner_api.get(f"/accounting/entries/{rev['entry']['id']}"))
    assert reversal["reverses_entry"]["id"] == entry["id"]
    assert owner_api.post(f"/accounting/entries/{rev['entry']['id']}/reverse", json={}).status_code == 400  # not twice
    assert owner_api.post(f"/accounting/entries/{uuid.uuid4()}/reverse", json={}).status_code == 404
    ledger = owner_api.ok(owner_api.get(f"/accounting/general-ledger/{expense['id']}", params={"from": today, "to": today}))
    ours = [ln for ln in ledger["lines"] if ln["entry_id"] in (entry["id"], rev["entry"]["id"])]
    assert sum(ln["debit"] - ln["credit"] for ln in ours) == 0  # reversed: nets to zero


def test_vat_report_settings_and_periods(owner_api, cashier_api, db, accounting):
    today = _today(db)
    vat = owner_api.ok(owner_api.get("/accounting/vat-report", params={"from": today[:8] + "01", "to": today}))
    assert {"output", "input", "net_payable", "by_month", "by_code"} <= set(vat)
    assert round(vat["net_payable"], 2) == round(vat["output"]["total"] - vat["input"]["total"], 2)
    assert owner_api.get("/accounting/vat-report", params={"from": "2026-13-01"}).status_code == 422
    assert cashier_api.get("/accounting/vat-report").status_code == 403

    settings = owner_api.ok(owner_api.get("/accounting/settings"))
    assert 1 <= settings["fiscal_year_start"] <= 12
    assert owner_api.put("/accounting/settings", json={"fiscal_year_start": 13}).status_code == 422
    assert cashier_api.put("/accounting/settings", json={"fiscal_year_start": 1}).status_code == 403

    periods = owner_api.ok(owner_api.get("/accounting/periods"))
    assert periods["current_month"] == today[:7]
    assert today[:7] in [m["month"] for m in periods["months"]]
    assert periods["years"] and all({"year", "from", "to", "open_months"} <= set(y) for y in periods["years"])
    assert cashier_api.get("/accounting/periods").status_code == 403
