"""Manual journal entries, reversals and the nightly reconciliation (ADR-014 D1, D8, D9; step 5 of D12).

- A draft is saved, edited and deleted freely, and lists what stops it from being posted.
- Posting checks every rule: balanced, no group or stopped account, a customer on receivables and a
  supplier on payables, no inventory or cashier drawer, not into a closed month or the future.
- A posted entry moves the operational balances with it (customer, supplier, safe), so the
  reconciliation keeps agreeing; reversing it undoes both, once.
- Only manual and opening entries are reversed by hand; the year end and documents have their own way.
- The nightly check notifies the accounting readers of differences, once a day.
- Permissions (journal / settings) and tenant isolation hold.
"""
import os
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.activities.general.modules.accounting.services import chart, journal, nightly, posting, reports
from app.activities.general.modules.contacts.models.party import Supplier
from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.auth.security import create_access_token, hash_password
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from tests.conftest import give_roles
from tests.test_accounting_ledger import _env
from tests.test_accounting_reports import _books, _client, _headers, _sql

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

D = Decimal
TODAY = posting.today()


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _acc(env, role: str) -> str:
    async with AsyncSessionLocal() as s:
        acc = (await chart.account_by_role(s, env["tenant_id"], role)).id
        await s.commit()
    return str(acc)


def _line(account_id, debit=0, credit=0, **kw) -> dict:
    return {"account_id": str(account_id), "debit": str(debit), "credit": str(credit), **kw}


async def _journal_only_headers(env) -> dict:
    """A user who may write journal entries (and read) but not change the chart or the opening."""
    t = env["tenant_id"]
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        u = User(id=uuid.uuid4(), tenant_id=t, username=f"journal_{t.hex[:8]}", full_name="كاتب قيود", role="accountant",
                 password_hash=hash_password("Pass12345!"), permissions=["accounting:view", "accounting:journal"], is_active=True)
        s.add(u)
        await give_roles(s)
        await s.commit()
    current_tenant_id.set(t)
    return {"Authorization": "Bearer " + create_access_token({"sub": str(u.id), "role": u.role, "username": u.username,
                                                               "tid": str(t)})}


async def test_a_draft_is_saved_edited_and_deleted_and_lists_what_stops_it():
    env = await _books()
    h = await _headers(env)
    capital, misc = await _acc(env, "capital"), await _acc(env, "other_income")
    async with _client() as c:
        r = await c.post("/accounting/drafts", headers=h["accountant"], json={
            "date": TODAY.isoformat(), "memo": "تسوية", "lines": [_line(capital, debit=100), _line(misc, credit=60),
                                                                 _line(misc)]})
        assert r.status_code == 201, r.text
        d = r.json()
        assert d["status"] == "draft" and len(d["lines"]) == 2  # the empty line is dropped
        assert d["balanced"] is False and d["difference"] == 40.0
        assert any("غير متوازن" in p for p in d["problems"])
        r = await c.put(f"/accounting/drafts/{d['id']}", headers=h["accountant"], json={
            "date": TODAY.isoformat(), "memo": "تسوية", "lines": [_line(capital, debit=60), _line(misc, credit=60)]})
        assert r.status_code == 200 and r.json()["balanced"] and r.json()["problems"] == []
        listed = (await c.get("/accounting/drafts", headers=h["accountant"])).json()
        assert [i["id"] for i in listed["items"]] == [d["id"]] and listed["items"][0]["balanced"]
        # Both sides on one line is refused outright; an unknown account too.
        bad = await c.post("/accounting/drafts", headers=h["accountant"], json={
            "date": TODAY.isoformat(), "lines": [_line(capital, debit=5, credit=5)]})
        assert bad.status_code == 400
        bad = await c.post("/accounting/drafts", headers=h["accountant"], json={
            "date": TODAY.isoformat(), "lines": [_line(uuid.uuid4(), debit=5)]})
        assert bad.status_code == 400
        assert (await c.delete(f"/accounting/drafts/{d['id']}", headers=h["accountant"])).status_code == 204
        assert (await c.get(f"/accounting/drafts/{d['id']}", headers=h["accountant"])).status_code == 404
        # A manager (view only) and a cashier can't touch drafts.
        for who in ("manager", "cashier"):
            assert (await c.get("/accounting/drafts", headers=h[who])).status_code == 403
            assert (await c.post("/accounting/drafts", headers=h[who], json={"date": TODAY.isoformat(), "lines": []})).status_code == 403


async def test_posting_refuses_what_would_break_the_sub_ledgers():
    env = await _books()
    h = await _headers(env)
    t = env["tenant_id"]
    roles = {r: await _acc(env, r) for r in ("receivables", "payables", "inventory", "other_income", "other_expenses",
                                             "cash_group", "capital")}
    async with AsyncSessionLocal() as s:
        drawer = str(await chart.money_account(s, t, "drawer", env["warehouse_id"]))
        await s.commit()
    cases = [
        ([_line(roles["receivables"], debit=10), _line(roles["other_income"], credit=10)], "حدد العميل"),
        ([_line(roles["payables"], debit=10, party_type="customer", party_id=str(env["customer_id"])),
          _line(roles["other_income"], credit=10)], "حدد المورد"),
        ([_line(roles["inventory"], debit=10), _line(roles["capital"], credit=10)], "المخزون"),
        ([_line(roles["cash_group"], debit=10), _line(roles["capital"], credit=10)], "تجميعي"),
        ([_line(drawer, debit=10), _line(roles["capital"], credit=10)], "درج الكاشير"),
        ([_line(roles["other_expenses"], debit=10, party_type="customer", party_id=str(env["customer_id"])),
          _line(roles["capital"], credit=10)], "لا يُذكر العميل"),
    ]
    async with _client() as c:
        for lines, expected in cases:
            d = (await c.post("/accounting/drafts", headers=h["accountant"], json={"date": TODAY.isoformat(), "lines": lines})).json()
            assert any(expected in p for p in d["problems"]), (expected, d["problems"])
            r = await c.post(f"/accounting/drafts/{d['id']}/post", headers=h["accountant"])
            assert r.status_code == 400 and expected in r.json()["detail"], (expected, r.text)
        # The future, and a closed month.
        ok_lines = [_line(roles["other_expenses"], debit=10), _line(roles["capital"], credit=10)]
        d = (await c.post("/accounting/drafts", headers=h["accountant"], json={
            "date": (TODAY + timedelta(days=3)).isoformat(), "lines": ok_lines})).json()
        assert (await c.post(f"/accounting/drafts/{d['id']}/post", headers=h["accountant"])).status_code == 400
        last_month = (TODAY.replace(day=1) - timedelta(days=1))
        d = (await c.post("/accounting/drafts", headers=h["accountant"], json={
            "date": last_month.isoformat(), "lines": ok_lines})).json()
    await _sql(env, "INSERT INTO accounting_periods (id, tenant_id, month, status) VALUES (:id, :t, :m, 'closed')",
               id=uuid.uuid4(), t=t, m=last_month.strftime("%Y-%m"))
    async with _client() as c:
        r = await c.post(f"/accounting/drafts/{d['id']}/post", headers=h["accountant"])
        assert r.status_code == 400 and "مغلقة" in r.json()["detail"]
    async with AsyncSessionLocal() as s:
        assert await s.scalar(text("SELECT COUNT(*) FROM acc_entries WHERE source_type = 'manual' AND event = 'post'")) == 0


async def test_a_posted_entry_moves_the_balances_with_it_and_its_reversal_undoes_them_once():
    env = await _books()
    h = await _headers(env)
    t = env["tenant_id"]
    sup_id = uuid.uuid4()
    async with AsyncSessionLocal() as s:
        s.add(Supplier(id=sup_id, tenant_id=t, name="مورد", balance=D("0")))
        safe_acc = str(await chart.money_account(s, t, "safe", env["safe_id"]))
        await s.commit()
    rec, pay = await _acc(env, "receivables"), await _acc(env, "payables")
    capital, misc = await _acc(env, "capital"), await _acc(env, "other_income")
    before = await _sql(env, "SELECT (SELECT balance FROM customers WHERE id = :c), (SELECT balance FROM safes WHERE id = :s)",
                        c=env["customer_id"], s=env["safe_id"])
    cust0, safe0 = before[0]
    lines = [
        _line(rec, debit=30, party_type="customer", party_id=str(env["customer_id"])),     # the customer owes 30 more
        _line(safe_acc, debit=500),                                                     # capital paid into the safe
        _line(pay, credit=20, party_type="supplier", party_id=str(sup_id)),               # we owe the supplier 20
        _line(misc, credit=10),
        _line(capital, credit=500),
    ]
    async with _client() as c:
        d = (await c.post("/accounting/drafts", headers=h["accountant"], json={
            "date": TODAY.isoformat(), "memo": "إثبات رأس المال وتسويات", "lines": lines})).json()
        assert d["problems"] == [], d["problems"]
        r = await c.post(f"/accounting/drafts/{d['id']}/post", headers=h["accountant"])
        assert r.status_code == 200, r.text
        entry = r.json()["entry"]
        again = (await c.post(f"/accounting/drafts/{d['id']}/post", headers=h["accountant"])).json()
        assert again["entry"]["id"] == entry["id"] and again["already"] is True
        # A posted draft is read-only.
        assert (await c.put(f"/accounting/drafts/{d['id']}", headers=h["accountant"], json={
            "date": TODAY.isoformat(), "lines": lines})).status_code == 400
        assert (await c.delete(f"/accounting/drafts/{d['id']}", headers=h["accountant"])).status_code == 400
        detail = (await c.get(f"/accounting/entries/{entry['id']}", headers=h["manager"])).json()
        assert detail["source_type"] == "manual" and detail["source_id"] == d["id"]
        assert detail["source_ref"] == "إثبات رأس المال وتسويات"
    after = await _sql(env, "SELECT (SELECT balance FROM customers WHERE id = :c), (SELECT balance FROM safes WHERE id = :s), "
                            "(SELECT balance FROM suppliers WHERE id = :p)", c=env["customer_id"], s=env["safe_id"], p=sup_id)
    assert after[0] == (cust0 + 30, safe0 + 500, D("20"))
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        assert (await reports.reconciliation(s, t))["ok"] is True
        assert await s.scalar(text("SELECT COUNT(*) FROM customer_adjustments WHERE customer_id = :c"), {"c": env["customer_id"]}) == 1
        assert await s.scalar(text("SELECT type FROM supplier_transactions WHERE supplier_id = :p"), {"p": sup_id}) == "debit"

    async with _client() as c:
        r = await c.post(f"/accounting/entries/{entry['id']}/reverse", headers=h["accountant"], json={"memo": "خطأ"})
        assert r.status_code == 200, r.text
        rev = r.json()
        assert rev["already"] is False and rev["entry"]["date"] == TODAY.isoformat()
        again = (await c.post(f"/accounting/entries/{entry['id']}/reverse", headers=h["accountant"])).json()
        assert again["already"] is True and again["entry"]["id"] == rev["entry"]["id"]
        detail = (await c.get(f"/accounting/entries/{rev['entry']['id']}", headers=h["manager"])).json()
        assert detail["reverses_id"] == entry["id"] and detail["reverses_entry"]["number"] == entry["number"]
        original = (await c.get(f"/accounting/entries/{entry['id']}", headers=h["manager"])).json()
        assert original["reversed_by"] == rev["entry"]["id"]
        # A reversal isn't reversed again; a manager can't reverse.
        assert (await c.post(f"/accounting/entries/{rev['entry']['id']}/reverse", headers=h["accountant"])).status_code == 400
        assert (await c.post(f"/accounting/entries/{entry['id']}/reverse", headers=h["manager"])).status_code == 403
    final = await _sql(env, "SELECT (SELECT balance FROM customers WHERE id = :c), (SELECT balance FROM safes WHERE id = :s), "
                            "(SELECT balance FROM suppliers WHERE id = :p)", c=env["customer_id"], s=env["safe_id"], p=sup_id)
    assert final[0] == (cust0, safe0, D("0"))
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        assert (await reports.reconciliation(s, t))["ok"] is True


async def test_only_manual_and_opening_entries_are_reversed_by_hand():
    env = await _books()
    h = await _headers(env)
    journal_only = await _journal_only_headers(env)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        sale_entry = await s.scalar(text("SELECT id FROM acc_entries WHERE source_type = 'sale' AND event = 'confirm' LIMIT 1"))
        opening_entry = await s.scalar(text("SELECT id FROM acc_entries WHERE source_type = 'opening'"))
    async with _client() as c:
        r = await c.post(f"/accounting/entries/{sale_entry}/reverse", headers=h["accountant"])
        assert r.status_code == 400 and "إلغاء المستند" in r.json()["detail"]
        # The opening entry needs accounting:settings, not just the journal.
        assert (await c.post(f"/accounting/entries/{opening_entry}/reverse", headers=journal_only)).status_code == 403
        settings = (await c.get("/accounting/settings", headers=h["manager"])).json()
        assert settings["opening_entry"]["id"] == str(opening_entry)
        assert settings["first_entry_date"] == (TODAY - timedelta(days=60)).isoformat()
        # A later entry exists, so its date can't be before the opening; reversing it on its own date works.
        r = await c.post(f"/accounting/entries/{opening_entry}/reverse", headers=h["accountant"])
        assert r.status_code == 200, r.text
        assert r.json()["entry"]["date"] == (TODAY - timedelta(days=60)).isoformat()
        assert (await c.get("/accounting/settings", headers=h["manager"])).json()["opening_entry"] is None
        assert (await c.post(f"/accounting/entries/{uuid.uuid4()}/reverse", headers=h["accountant"])).status_code == 404


async def test_year_end_entries_are_reversed_only_through_the_year_end_route():
    env = await _env()
    t = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        a, b = (await chart.account_by_role(s, t, "retained_earnings")).id, (await chart.account_by_role(s, t, "other_income")).id
        entry = await posting.post(s, t, "year_end", uuid.uuid4(), "close", TODAY, [posting.dr(b, 5), posting.cr(a, 5)])
        await s.commit()
        with pytest.raises(Exception) as e:
            journal.reversal_kind(entry)
    assert "إقفال السنة" in e.value.detail


async def test_drafts_are_isolated_per_workspace():
    env = await _books()
    h = await _headers(env)
    capital, misc = await _acc(env, "capital"), await _acc(env, "other_income")
    async with _client() as c:
        d = (await c.post("/accounting/drafts", headers=h["accountant"], json={
            "date": TODAY.isoformat(), "lines": [_line(capital, debit=1), _line(misc, credit=1)]})).json()
    other = await _env()
    ho = await _headers(other)
    async with _client() as c:
        assert (await c.get(f"/accounting/drafts/{d['id']}", headers=ho["accountant"])).status_code == 404
        assert (await c.post(f"/accounting/drafts/{d['id']}/post", headers=ho["accountant"])).status_code == 404
        assert (await c.get("/accounting/drafts", headers=ho["accountant"])).json()["items"] == []
        # The first workspace's accounts are unknown in the other one.
        r = await c.post("/accounting/drafts", headers=ho["accountant"], json={
            "date": TODAY.isoformat(), "lines": [_line(capital, debit=1), _line(misc, credit=1)]})
        assert r.status_code == 400


async def test_nightly_reconciliation_notifies_the_accounting_readers_once():
    env = await _books()
    t = env["tenant_id"]
    await _headers(env)  # an accountant, a manager (both read accounting) and a cashier (doesn't)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        assert await nightly.check_workspace(s, t) is None  # the books agree: nothing to say
        await s.commit()
    await _sql(env, "UPDATE customers SET balance = balance + 25 WHERE id = :c", c=env["customer_id"])
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        found = await nightly.check_workspace(s, t)
        await s.commit()
    assert found is not None and found["differences"][0]["key"] == "receivables"
    rows = await _sql(env, "SELECT u.role, n.link, n.body FROM notifications n JOIN users u ON u.id = n.user_id "
                           "WHERE n.type = 'accounting_reconciliation' ORDER BY u.role")
    roles = [r.role for r in rows]
    assert "accountant" in roles and "manager" in roles and "cashier" not in roles
    assert rows[0].link == nightly.LINK and "25.00" in rows[0].body
    # The next run the same day adds nothing.
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t)
        await nightly.check_workspace(s, t)
        await s.commit()
    assert len(await _sql(env, "SELECT 1 FROM notifications WHERE type = 'accounting_reconciliation'")) == len(rows)


async def test_the_nightly_job_runs_over_every_workspace_with_accounting():
    from app.platform.automation_worker.runner import JOB_REGISTRY, run_job

    env = await _books()
    await _headers(env)
    await _sql(env, "UPDATE customers SET balance = balance + 5 WHERE id = :c", c=env["customer_id"])
    without = await _env(accounting=False)
    assert "accounting_reconciliation" in JOB_REGISTRY
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        out = await run_job("accounting_reconciliation", s)
    assert out["status"] == "success", out
    assert out["items_processed"] >= 1
    current_tenant_id.set(without["tenant_id"])
    sql = "SELECT 1 FROM notifications WHERE tenant_id = :t AND type = 'accounting_reconciliation'"
    assert await _sql(without, sql, t=without["tenant_id"]) == []
    current_tenant_id.set(env["tenant_id"])
    assert await _sql(env, sql, t=env["tenant_id"]) != []


async def test_the_periods_list_runs_from_the_first_entry_and_says_what_can_be_closed():
    env = await _books()
    h = await _headers(env)
    first = (TODAY - timedelta(days=60)).strftime("%Y-%m")
    async with _client() as c:
        r = await c.get("/accounting/periods", headers=h["manager"])
        assert r.status_code == 200, r.text
        out = r.json()
        months = [m["month"] for m in out["months"]]
        assert months[0] == TODAY.strftime("%Y-%m") and months[-1] == first and out["months"][0]["current"]
        # Only the earliest open month can be closed (in order); nothing is closed yet.
        assert [m["month"] for m in out["months"] if m["can_close"]] == [first]
        assert not any(m["can_reopen"] for m in out["months"])
        assert out["years"][0]["year"] == TODAY.year and out["years"][0]["over"] is False
        assert (await c.post(f"/periods/{first}/close", headers=h["accountant"])).status_code == 200
        out = (await c.get("/accounting/periods", headers=h["accountant"])).json()
        closed = next(m for m in out["months"] if m["month"] == first)
        assert closed["status"] == "closed" and closed["can_reopen"] and closed["closed_by_name"] == "accountant"
        assert (await c.get("/accounting/periods", headers=h["cashier"])).status_code == 403
