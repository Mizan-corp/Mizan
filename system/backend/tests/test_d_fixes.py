"""Phase D, part 2 (PRODUCTION_READINESS.md, "Phase D"): the bugs phase C found, and performance
and audit work.

1. Cancelling a customer receipt's drawer row (shift screen) gives the invoice its debt back:
   sales.paid_amount, the customer's balance and the ledger agree.
2. Saving some of a module's settings keeps the others; each key and value is checked against the
   manifest (422).
3. Collections are a stock-assembly helper (not sold): a PUT without prices keeps them.
4. HR-13: the employees list is paged; calculating a month runs the same number of queries for any
   number of employees.
5. HR-14: the HR audit log records employees, attendance, entry adjustments and every step of a
   payroll month, with who and what.
6. ACC-1: journal entry numbers come from a per-workspace counter row; two posts at once get
   distinct consecutive numbers.
7. PLAT-9 rest: the remaining indexes exist (models and database).
8. Idempotency keys: the nightly clean-up; two simultaneous requests with one key have one effect
   and the same answer.
"""
import asyncio
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text

from app.activities.general.modules.sales.schemas import SaleItemCreate  # noqa: F401
from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.tenancy.context import bind_tenant, current_tenant_id
from tests.test_ready_finance import _client, _one, _sale, _sql, _ws, pytestmark  # noqa: F401

D = Decimal
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _receivable(env, customer_id) -> Decimal:
    """What the ledger says the customer owes (receivables, their party)."""
    return await _one(env, """
        SELECT COALESCE(SUM(l.debit - l.credit), 0) FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id
        WHERE a.role = 'receivables' AND l.party_id = :c
    """, c=customer_id)


# ── 1. A drawer receipt cancelled from the shift screen ──────────────────────────────────────

async def test_cancelling_a_drawer_receipt_gives_the_invoice_its_debt_back():
    """Old code: the cancel gave the customer the debt back (and the ledger reversed the receipt)
    but the invoice kept paid_amount 60 and its 60 "paid", so it could never be paid in full again."""
    from app.activities.general.modules.contacts import service as contacts
    from app.activities.general.modules.contacts.service import INVOICE_DUE
    from app.activities.general.modules.pos import service as pos_service

    env = await _ws(accounting=True)
    cid = env["customer_id"]
    credit = await _sale(env, customer_id=cid, is_credit=True)  # 100 on the customer's account
    current_tenant_id.set(env["tenant_id"])
    async with AsyncSessionLocal() as s:
        user = await s.get(User, env["cashier_id"])
        payment = await contacts.receive_payment(s, cid, D("60"), user, sale_id=credit.id)  # cash, into the open drawer
        await s.commit()
        payment_id = payment.id
    dt = await _one(env, "SELECT id FROM drawer_transactions WHERE customer_payment_id = :p", p=payment_id)
    assert await _one(env, "SELECT paid_amount FROM sales WHERE id = :s", s=credit.id) == D("60")
    assert await _one(env, "SELECT balance FROM customers WHERE id = :c", c=cid) == D("40")
    assert await _receivable(env, cid) == D("40")

    async with AsyncSessionLocal() as s:
        await pos_service.delete_drawer_transaction(s, dt, env["cashier_id"])

    assert await _one(env, "SELECT paid_amount FROM sales WHERE id = :s", s=credit.id) == D("0")
    assert await _one(env, "SELECT balance FROM customers WHERE id = :c", c=cid) == D("100")
    assert await _receivable(env, cid) == D("100")
    due = (await _sql(env, INVOICE_DUE, id=credit.id))[0]
    assert due.credit - due.returned - due.paid == D("100")
    reversal = (await _sql(env, "SELECT amount, sale_id, reverses_id FROM customer_payments WHERE reverses_id = :p",
                           p=payment_id))[0]
    assert (reversal.amount, reversal.sale_id) == (D("-60"), credit.id)

    # The invoice can be paid in full again, and the receipt can't be reversed a second time.
    async with AsyncSessionLocal() as s:
        user = await s.get(User, env["cashier_id"])
        await contacts.receive_payment(s, cid, D("100"), user, sale_id=credit.id, safe_id=env["safe_id"])
        await s.commit()
    assert await _one(env, "SELECT paid_amount FROM sales WHERE id = :s", s=credit.id) == D("100")
    assert await _one(env, "SELECT balance FROM customers WHERE id = :c", c=cid) == D("0")
    assert await _receivable(env, cid) == D("0")
    async with AsyncSessionLocal() as s:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as e:
            await contacts.reverse_drawer_receipt(s, payment_id, env["cashier_id"])
        assert e.value.status_code == 409


# ── 2. Module settings: partial update, checked against the manifest ─────────────────────────

async def test_saving_one_setting_keeps_the_others_and_values_are_checked():
    """Old code: each save replaced the whole row, so saving one key put every other back to its
    default; unknown keys were dropped silently and any value was stored."""
    env = await _ws()
    h = env["h"]["admin"]
    async with _client() as c:
        r = await c.post("/modules/pos/settings", json={"settings": {"allow_price_override": True}}, headers=h)
        assert r.status_code == 200, r.text
        r = await c.post("/modules/pos/settings", json={"settings": {"auto_print_receipt": True}}, headers=h)
        values = r.json()["settings"]["values"]
        assert values["allow_price_override"] is True and values["auto_print_receipt"] is True
        assert values["require_active_shift"] is True  # never saved: its default

        for bad in ({"allow_price_override": "yes"}, {"no_such_setting": 1}, {"enable_quick_numpad": 1}):
            r = await c.post("/modules/pos/settings", json={"settings": bad}, headers=h)
            assert r.status_code == 422, (bad, r.text)
        r = await c.post("/modules/contacts/settings", json={"settings": {"default_credit_limit": "x"}}, headers=h)
        assert r.status_code == 422
        assert (await c.post("/modules/contacts/settings", json={"settings": {"default_credit_limit": 500}},
                             headers=h)).status_code == 200
        # null puts a key back to its default; the refused saves changed nothing.
        r = await c.post("/modules/pos/settings", json={"settings": {"auto_print_receipt": None}}, headers=h)
        values = r.json()["settings"]["values"]
        assert values["auto_print_receipt"] is False and values["allow_price_override"] is True
        # A cashier can't change settings.
        assert (await c.post("/modules/pos/settings", json={"settings": {"allow_price_override": False}},
                             headers=env["h"]["cashier"])).status_code == 403
    # Keys a module no longer declares are neither shown nor sent back (they would be refused).
    await _sql(env, "UPDATE store_settings SET value = :v WHERE key = 'mod_settings_pos'",
               v='{"allow_price_override": true, "valuation_method": "fifo"}')
    async with _client() as c:
        got = (await c.get("/modules/pos/settings", headers=h)).json()["values"]
        assert "valuation_method" not in got and got["allow_price_override"] is True
        assert (await c.post("/modules/pos/settings", json={"settings": got}, headers=h)).status_code == 200


async def test_two_settings_saved_at_once_both_count():
    from app.framework.loader import registry

    env = await _ws()

    async def save(values):
        async with AsyncSessionLocal() as s:
            await bind_tenant(s, env["tenant_id"])
            await registry.save_settings(s, "pos", values)

    await asyncio.gather(save({"allow_price_override": True}), save({"auto_print_receipt": True}))
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        values = (await registry.get_settings(s, "pos"))["values"]
    assert values["allow_price_override"] is True and values["auto_print_receipt"] is True


# ── 3. Collections: a stock-assembly helper ──────────────────────────────────────────────────

async def test_a_collection_saved_without_prices_keeps_them():
    """The screen no longer offers a selling price (collections aren't sold); old code zeroed the
    stored prices on every edit that didn't send them."""
    env = await _ws()
    h = env["h"]["admin"]
    item = {"product_id": str(env["product_id"]), "qty": "2"}
    async with _client() as c:
        coll = (await c.post("/collections", json={"name": "كرتونة", "retail_price": "150", "wholesale_price": "120",
                                                    "items": [item]}, headers=h)).json()
        assert (await c.put(f"/collections/{coll['id']}", json={"name": "كرتونة رمضان", "items": [item]},
                            headers=h)).status_code == 200
        listed = next(x for x in (await c.get("/collections", headers=h)).json()["items"] if x["id"] == str(coll["id"]))
        assert listed["name"] == "كرتونة رمضان"
        assert (D(str(listed["retail_price"])), D(str(listed["wholesale_price"]))) == (D("150"), D("120"))
        # Its cost (average cost, as stock is valued) is shown to those who see costs only.
        assert D(str(listed["items"][0]["avg_cost"])) == D("60")
        hidden = next(x for x in (await c.get("/collections", headers=env["h"]["cashier"])).json()["items"]
                      if x["id"] == str(coll["id"]))
        assert hidden["items"][0]["avg_cost"] is None and hidden["items"][0]["cost_price"] is None


# ── 4. HR-13 ─────────────────────────────────────────────────────────────────────────────────

async def test_the_employees_list_is_paged_and_searched():
    from tests.test_hr_ready import _client as hr_client
    from tests.test_hr_ready import _headers, _workspace

    ws = await _workspace()
    h = _headers(ws, "admin")
    async with hr_client() as c:
        first = (await c.get("/hr/employees", params={"page_size": 1}, headers=h)).json()
        assert set(first) == {"items", "total", "page", "page_size"} and first["total"] == 2 and len(first["items"]) == 1
        second = (await c.get("/hr/employees", params={"page_size": 1, "page": 2}, headers=h)).json()
        assert first["items"][0]["id"] != second["items"][0]["id"]
        found = (await c.get("/hr/employees", params={"q": "ب"}, headers=h)).json()
        assert [e["name"] for e in found["items"]] == ["موظف ب"]
        assert (await c.get("/hr/employees", params={"q": "%"}, headers=h)).json()["total"] == 0
        assert (await c.get("/hr/employees", params={"page_size": 500}, headers=h)).status_code == 422


async def test_calculating_a_month_doesnt_query_per_employee():
    """Old code: two queries per employee (attendance, HR records) and one more per entry."""
    from app.activities.general.modules.hr.services import payroll
    from tests.test_hr_ready import MONTH, _attend, _session, _workspace
    from tests.test_query_counts import count_queries

    ws = await _workspace()
    db, user = await _session(ws)
    async with db:
        for emp in ws["emps"]:
            for day in (3, 4):
                await _attend(db, emp, day)
        await db.execute(text("INSERT INTO hr_advances (id, tenant_id, employee_id, amount, date, record_type) "
                              "VALUES (gen_random_uuid(), :t, :e, 10, :d, 'خصم')"),
                         {"t": ws["tid"], "e": ws["emps"][0], "d": date(2025, 2, 5)})
        await db.commit()
        await payroll.calculate_payroll_month(db, MONTH, str(user.id))  # the period exists from here on
        with count_queries() as two:
            await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        for i in range(4):
            eid = (await db.execute(text("""
                INSERT INTO hr_employees (id, tenant_id, emp_code, name, monthly_salary, shift_schedule)
                VALUES (gen_random_uuid(), :t, :code, :n, 2600, '09:00-17:00') RETURNING id
            """), {"t": ws["tid"], "code": f"X{i}-{ws['tid'].hex[:4]}", "n": f"موظف {i}"})).scalar_one()
            await _attend(db, eid, 3)
        await db.commit()
        with count_queries() as six:
            out = await payroll.calculate_payroll_month(db, MONTH, str(user.id))
        assert out["employees"] == 6
        assert len(six) == len(two), (len(two), len(six))
        entries = dict((await db.execute(text(
            "SELECT employee_id, deductions FROM hr_payroll_entries pe JOIN hr_payroll_periods p ON p.id = pe.period_id "
            "WHERE p.month = :m"), {"m": MONTH})).all())
        assert len(entries) == 6 and entries[ws["emps"][0]] == D("10.00") and entries[ws["emps"][1]] == D("0.00")
    assert not any("to_char" in q.lower() for q in six)


# ── 5. HR-14 ─────────────────────────────────────────────────────────────────────────────────

async def test_the_hr_audit_log_records_every_change_and_step():
    """Old code: only salary changes, entry adjustments and advances were logged."""
    from tests.test_hr_ready import MONTH, _attend, _headers, _session, _workspace
    from tests.test_hr_ready import _client as hr_client

    ws = await _workspace()
    h = _headers(ws, "admin")
    emp = str(ws["emps"][0])
    db, _ = await _session(ws)
    async with db:
        await _attend(db, ws["emps"][1], 4)
        await db.commit()
    async with hr_client() as c:
        new = (await c.post("/hr/employees", headers=h, json={"name": "موظفة جديدة", "monthly_salary": "3000"})).json()
        assert (await c.put(f"/hr/employees/{new['id']}", headers=h, json={"position": "محاسبة"})).status_code == 200
        assert (await c.delete(f"/hr/employees/{new['id']}", headers=h)).status_code == 204
        assert (await c.put(f"/hr/employees/{new['id']}", headers=h, json={"is_active": True})).status_code == 200
        r = await c.post("/hr/attendance", headers=h, json={"employee_id": emp, "work_date": "2025-02-03",
                                                           "check_in": "09:00", "check_out": "17:00", "status": "present"})
        assert r.status_code == 200, r.text
        assert (await c.post("/hr/attendance", headers=h, json={"employee_id": emp, "work_date": "2025-02-03",
                                                               "check_in": "10:00", "check_out": "17:00", "status": "present",
                                                               "edit_reason": "نسي البصمة"})).status_code == 200
        assert (await c.post("/hr/payroll/calculate", headers=h, json={"month": MONTH})).status_code == 200
        rows = (await c.get("/hr/payroll", params={"month": MONTH}, headers=h)).json()
        assert (await c.put(f"/hr/payroll/{rows[0]['id']}", headers=h, json={"bonus": "50"})).status_code == 200
        for step in ("submit", "approve", "reopen", "submit", "approve"):
            r = await c.post(f"/hr/payroll/period/{step}", params={"month": MONTH}, headers=h)
            assert r.status_code == 200, (step, r.text)
        r = await c.post("/hr/payroll/period/pay", params={"month": MONTH}, headers=h, json={"safe_id": str(ws["safe_id"])})
        assert r.status_code == 200, r.text
        log = (await c.get("/hr/audit-log", params={"page_size": 200}, headers=h)).json()["items"]

    seen = [(r["action_type"], r["entity_type"]) for r in reversed(log)]
    for expected in [("create", "employee"), ("update", "employee"), ("stop", "employee"), ("start", "employee"),
                     ("create", "attendance"), ("update", "attendance"), ("calculate", "payroll_period"),
                     ("update", "payroll_entry"), ("submit", "payroll_period"), ("approve", "payroll_period"),
                     ("reopen", "payroll_period"), ("pay", "payroll_period")]:
        assert expected in seen, (expected, seen)
    assert seen.count(("approve", "payroll_period")) == 2
    assert all(r["performed_by_name"] == "admin" for r in log)
    by = {(r["action_type"], r["entity_type"]): r for r in log}
    assert by[("update", "employee")]["details"] == {"position": {"from": "", "to": "محاسبة"}}
    assert by[("stop", "employee")]["employee_name"] == "موظفة جديدة"
    edit = by[("update", "attendance")]
    assert edit["reason"] == "نسي البصمة" and edit["employee_name"] == "موظف أ" and set(edit["details"]) == {"date", "check_in"}
    assert by[("update", "payroll_entry")]["employee_name"] is not None
    assert by[("pay", "payroll_period")]["entity_id"] == MONTH
    assert by[("pay", "payroll_period")]["details"]["safe_id"] == str(ws["safe_id"])
