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
