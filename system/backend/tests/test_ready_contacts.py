"""Contacts, production readiness (PRODUCTION_READINESS.md, contacts).

CON-1  write-offs, deleting and stopping customers need `finance` or a manager.
CON-2  the statement is one ordered, paged list with a running balance; unknown customer 404.
CON-3  a receipt pays a confirmed credit invoice of the customer, never more than is due.
CON-4  receipts are idempotent and can be reversed (money, balance and ledger).
CON-6  inputs are bounded (an empty name is a 422).
"""
import uuid
from decimal import Decimal

import pytest

from app.activities.general.modules.sales.schemas import SaleItemCreate
from app.activities.general.modules.sales.services import sales as sales_service
from app.db.base import AsyncSessionLocal
from app.platform.tenancy.context import current_tenant_id
from tests.test_accounting_ledger import _lines
from tests.test_ready_finance import _client, _one, _sale, _sql, _ws, pytestmark  # noqa: F401

D = Decimal


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


# ── CON-1 ─────────────────────────────────────────────────────────────────────────────────────

async def test_write_offs_and_removing_customers_need_finance_or_a_manager():
    env = await _ws()
    h = env["h"]
    cid = env["customer_id"]
    async with _client() as c:
        assert (await c.put(f"/customers/{cid}/balance", json={"balance": "0"}, headers=h["cashier"])).status_code == 403
        assert (await c.post(f"/customers/{cid}/deactivate", headers=h["cashier"])).status_code == 403
        assert (await c.delete(f"/customers/{cid}", headers=h["cashier"])).status_code == 403
        assert (await c.put(f"/customers/{cid}/balance", json={"balance": "250"}, headers=h["accountant"])).status_code == 200
        assert (await c.put(f"/customers/{cid}/balance", json={"balance": "200"}, headers=h["boss"])).status_code == 200
        assert (await c.post(f"/customers/{cid}/deactivate", headers=h["boss"])).status_code == 200
        assert (await c.post(f"/customers/{cid}/activate", headers=h["accountant"])).status_code == 200
        # the cashier still serves customers
        assert (await c.post("/customers", json={"name": "عميل الكاشير"}, headers=h["cashier"])).status_code == 200
        assert (await c.put(f"/customers/{cid}", json={"name": None}, headers=h["cashier"])).status_code == 422


# ── CON-2, CON-3, CON-4 ───────────────────────────────────────────────────────────────────────

async def test_the_statement_is_ordered_paged_with_a_running_balance():
    env = await _ws()
    h = env["h"]
    cid = env["customer_id"]
    # a credit invoice of 200 less 20 discount, a receipt of 50, then a write-down of 10
    await _sale(env, customer_id=cid, is_credit=True, discount_amount=D("20"),
                items=[SaleItemCreate(product_id=env["product_id"], qty=D("2"), unit_price=D("100"))])
    async with _client() as c:
        assert (await c.post(f"/customers/{cid}/payments", json={"amount": "50", "safe_id": str(env["safe_id"])},
                             headers=h["cashier"])).status_code == 200
        assert (await c.put(f"/customers/{cid}/balance", json={"balance": "120"}, headers=h["accountant"])).status_code == 200
        p1 = (await c.get(f"/customers/{cid}/ledger", params={"page_size": 2}, headers=h["cashier"])).json()
        p2 = (await c.get(f"/customers/{cid}/ledger", params={"page_size": 2, "page": 2}, headers=h["cashier"])).json()
        assert p1["total"] == 3 and p1["pages"] == 2
        lines = p1["items"] + p2["items"]
        assert [x["type"] for x in lines] == ["invoice", "payment", "adjustment"]
        assert [x["balance"] for x in lines] == [180.0, 130.0, 120.0]
        assert lines[0]["debit"] == 180.0 and lines[1]["credit"] == 50.0 and lines[2]["credit"] == 10.0
        newest = (await c.get(f"/customers/{cid}/ledger", params={"newest_first": True}, headers=h["cashier"])).json()
        assert newest["items"][0]["type"] == "adjustment" and newest["items"][0]["balance"] == 120.0
        account = (await c.get(f"/customers/{cid}/account", headers=h["cashier"])).json()
        assert (account["total_invoiced"], account["total_paid"], account["balance_due"], account["balance"]) == (180.0, 50.0, 120.0, 120.0)
        assert (await c.get(f"/customers/{uuid.uuid4()}/ledger", headers=h["cashier"])).status_code == 404


async def test_a_receipt_pays_a_credit_invoice_of_the_customer_and_never_more_than_due():
    env = await _ws()
    h = env["h"]
    cid = env["customer_id"]
    other = uuid.uuid4()
    await _sql(env, "INSERT INTO customers (id, tenant_id, name, balance, is_cash, is_active) VALUES (:id, :t, 'آخر', 0, false, true)", id=other, t=env["tenant_id"])
    credit = await _sale(env, customer_id=cid, is_credit=True, paid_amount=D("30"))     # 30 down, 70 on account
    cash = await _sale(env, customer_id=cid)
    cancelled = await _sale(env, customer_id=cid, is_credit=True)
    async with AsyncSessionLocal() as s:
        await sales_service.cancel_sale(s, cancelled.id, env["cashier_id"])
    pay = {"safe_id": str(env["safe_id"])}
    async with _client() as c:
        async def receipt(sale_id, amount, customer=cid):
            return await c.post(f"/customers/{customer}/payments", json={"amount": amount, "sale_id": str(sale_id), **pay},
                                headers=h["cashier"])
        assert (await receipt(cash.id, "10")).status_code == 409
        assert (await receipt(cancelled.id, "10")).status_code == 409
        assert (await receipt(credit.id, "10", customer=other)).status_code == 400
        assert (await receipt(credit.id, "71")).status_code == 409
        assert (await receipt(credit.id, "40")).status_code == 200
        assert (await receipt(credit.id, "31")).status_code == 409
        assert (await receipt(credit.id, "30")).status_code == 200
        assert (await receipt(uuid.uuid4(), "1")).status_code == 404


async def test_receipts_are_idempotent_and_can_be_reversed():
    env = await _ws(accounting=True)
    h = env["h"]
    cid, sid = env["customer_id"], env["safe_id"]
    await _sql(env, "UPDATE customers SET balance = 300 WHERE id = :c", c=cid)
    body = {"amount": "100", "safe_id": str(sid), "client_id": str(uuid.uuid4())}
    async with _client() as c:
        first = (await c.post(f"/customers/{cid}/payments", json=body, headers=h["cashier"])).json()
        again = (await c.post(f"/customers/{cid}/payments", json=body, headers=h["cashier"])).json()
        assert first["id"] == again["id"]
        assert await _one(env, "SELECT count(*) FROM customer_payments WHERE customer_id = :c", c=cid) == 1
        assert await _one(env, "SELECT balance FROM safes WHERE id = :s", s=sid) == D("1100")

        reverse = f"/customers/payments/{first['id']}/reverse"
        assert (await c.post(reverse, json={"reason": "خطأ في التحصيل"}, headers=h["cashier"])).status_code == 403
        r = await c.post(reverse, json={"reason": "خطأ في التحصيل"}, headers=h["accountant"])
        assert r.status_code == 200, r.text
        assert r.json()["amount"] == -100.0 and r.json()["reverses_id"] == first["id"]
        twice = await c.post(reverse, json={"reason": "خطأ في التحصيل"}, headers=h["accountant"])
        assert twice.status_code == 409
        assert (await c.post(f"/customers/payments/{r.json()['id']}/reverse", json={"reason": "عكس العكس"},
                             headers=h["accountant"])).status_code == 409
        lines = (await c.get(f"/customers/{cid}/ledger", headers=h["cashier"])).json()["items"]
        assert [x["type"] for x in lines] == ["payment", "payment_reversal"] and not lines[0]["can_reverse"]
    assert await _one(env, "SELECT balance FROM safes WHERE id = :s", s=sid) == D("1000")
    assert await _one(env, "SELECT balance FROM customers WHERE id = :c", c=cid) == D("300")
    ledger = await _lines("customer_payment", uuid.UUID(first["id"]))
    assert sum(d for _, d, _, _ in ledger) == sum(cr for _, _, cr, _ in ledger) == D("200")  # the entry and its reversal
    assert len(await _sql(env, "SELECT 1 FROM acc_entries WHERE source_type = 'customer_payment' AND event = 'reverse'")) == 1
