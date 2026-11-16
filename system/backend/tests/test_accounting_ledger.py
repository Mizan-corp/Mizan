"""The ledger (ADR-014 D1, D2, D3, D7; step 2 of D12).

- Enabling accounting copies the standard chart into the workspace, once.
- Sales, returns, cancellations, drawer movements, shift differences, customer receipts and
  adjustments, safe and wallet movements and expenses each post one balanced entry, in the
  document's transaction; cancelling posts the reversing entry, so the net is zero.
- Posting is idempotent, refuses closed months, and the database refuses an unbalanced entry.
- A workspace without the module posts nothing; entries are isolated per workspace.
"""
import os
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.activities.general.modules.accounting.services import chart, ledger
from app.activities.general.modules.accounting.services import posting
from app.platform.tenancy.context import bind_tenant
from app.activities.general.modules.contacts.models.party import Customer
from app.activities.general.modules.finance.models.payment_wallet import PaymentWallet
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement
from app.activities.general.modules.pos import service as pos_service
from app.activities.general.modules.pos.models import DrawerTxType, Shift
from app.activities.general.modules.sales.schemas import SaleCreate, SaleItemCreate, SplitPaymentItem
from app.activities.general.modules.sales.services import sales as sales_service
from app.core.exceptions import BusinessError
from app.db.base import AsyncSessionLocal
from app.models.registry import load_all_models
from app.platform.auth.models.user import User
from app.platform.auth.security import hash_password
from app.platform.tenancy.context import current_tenant_id, install_tenancy_events
from app.platform.tenancy.models import Tenant

load_all_models()
install_tenancy_events()

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

MODULES = ["sales", "pos", "shifts", "inventory", "finance", "contacts"]


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _env(accounting: bool = True) -> dict:
    """A workspace (with or without accounting) with a branch, a cashier with an open shift (1000
    in the drawer), a customer, a wallet, a safe holding 1000, and a product: 50 units at cost 60."""
    t_id = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=t_id, name=f"Ledger {t_id.hex[:6]}", slug=f"ledger-{t_id.hex[:8]}", status="active",
                     active_modules=MODULES + (["accounting"] if accounting else [])))
        await s.flush()
        wh = Warehouse(id=uuid.uuid4(), tenant_id=t_id, code=f"WH-{t_id.hex[:4]}", name="فرع وسط البلد", is_active=True)
        cashier = User(id=uuid.uuid4(), tenant_id=t_id, username=f"led_{t_id.hex[:8]}", full_name="كاشير",
                       role="admin", password_hash=hash_password("Pass123!"), permissions=["sales", "pos", "shifts"],
                       is_active=True)
        product = Product(id=uuid.uuid4(), tenant_id=t_id, name="صنف", code=f"P-{t_id.hex[:6]}",
                          retail_price=Decimal("100"), cost_price=Decimal("60"), stock_status="tracked", is_active=True)
        customer = Customer(id=uuid.uuid4(), tenant_id=t_id, name="عميل", balance=Decimal("0"))
        wallet = PaymentWallet(id=uuid.uuid4(), tenant_id=t_id, name="فودافون كاش", type="vodafone",
                               balance=Decimal("0"), is_active=True)
        s.add_all([wh, cashier, product, customer, wallet])
        await s.flush()
        shift = Shift(id=uuid.uuid4(), tenant_id=t_id, cashier_id=cashier.id, warehouse_id=wh.id, status="open",
                      initial_amount=Decimal("1000"), started_at=datetime.now(UTC))
        s.add(shift)
        await s.commit()
    current_tenant_id.set(t_id)
    async with AsyncSessionLocal() as s:
        safe_id = (await s.execute(text(
            "INSERT INTO safes (name, balance) VALUES ('الخزينة الرئيسية', 1000) RETURNING id"))).scalar_one()
        await apply_movement(s, product_id=product.id, warehouse_id=wh.id, movement_type=MovementType.opening_stock,
                             qty=Decimal("50"), unit_cost=Decimal("60"), created_by=cashier.id)
        await s.commit()
    return {"tenant_id": t_id, "warehouse_id": wh.id, "cashier_id": cashier.id, "product_id": product.id,
            "shift_id": shift.id, "customer_id": customer.id, "wallet_id": wallet.id, "safe_id": safe_id}


def _sale(env, qty="2", price="100", **kw) -> SaleCreate:
    return SaleCreate(warehouse_id=env["warehouse_id"], shift_id=env["shift_id"],
                      items=[SaleItemCreate(product_id=env["product_id"], qty=Decimal(qty), unit_price=Decimal(price))],
                      **kw)


async def _user(s, env) -> User:
    user = await s.get(User, env["cashier_id"])
    s.expunge(user)
    return user


async def _lines(source_type: str, source_id, event: str | None = None) -> list[tuple]:
    """(account role or name, debit, credit, party_id) of the entries of a document."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text("""
            SELECT COALESCE(a.role, a.name) AS acc, l.debit, l.credit, l.party_id
            FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id JOIN acc_entries e ON e.id = l.entry_id
            WHERE e.source_type = :st AND e.source_id = :sid AND (CAST(:ev AS text) IS NULL OR e.event = :ev)
            ORDER BY l.debit DESC, acc
        """), {"st": source_type, "sid": source_id, "ev": event})).all()
    return [(r.acc, r.debit, r.credit, r.party_id) for r in rows]


async def _balances() -> dict[str, Decimal]:
    """Each account's debit minus credit over the whole ledger (accounts with movements only)."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text("""
            SELECT COALESCE(a.role, a.name) AS acc, SUM(l.debit - l.credit) AS bal
            FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id GROUP BY 1
        """))).all()
    return {r.acc: r.bal for r in rows}


async def _count(sql: str, **params) -> int:
    async with AsyncSessionLocal() as s:
        return (await s.execute(text(sql), params)).scalar_one()


D = Decimal


async def test_enabling_copies_the_chart_once():
    env = await _env()
    async with AsyncSessionLocal() as s:
        assert await chart.ensure_chart(s, env["tenant_id"]) is True
        await s.commit()
    async with AsyncSessionLocal() as s:
        assert await chart.ensure_chart(s, env["tenant_id"]) is False
        await s.commit()
    expected = len(chart.load_chart()["accounts"])
    assert await _count("SELECT count(*) FROM acc_accounts") == expected
    roles = await _count("SELECT count(DISTINCT role) FROM acc_accounts WHERE role IS NOT NULL")
    assert roles == await _count("SELECT count(*) FROM acc_accounts WHERE role IS NOT NULL")
    # The read API's tree has the five classes at its root.
    async with AsyncSessionLocal() as s:
        tree = await ledger.accounts_tree(s, env["tenant_id"])
    assert [n["code"] for n in tree] == ["1", "2", "3", "4", "5"]


async def test_cash_pos_sale_posts_the_drawer_revenue_and_cost():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env), env["cashier_id"])
    lines = await _lines("sale", sale.id, "confirm")
    assert lines == [
        ("درج كاشير — فرع وسط البلد", D("200.00"), D("0.00"), None),
        ("cogs", D("120.00"), D("0.00"), None),
        ("inventory", D("0.00"), D("120.00"), None),
        ("sales", D("0.00"), D("200.00"), None),
    ]
    # The drawer is a sub-account of the cash group, linked to the branch.
    async with AsyncSessionLocal() as s:
        parent_role = (await s.execute(text("""
            SELECT p.role FROM acc_money_accounts m JOIN acc_accounts a ON a.id = m.account_id
            JOIN acc_accounts p ON p.id = a.parent_id WHERE m.kind = 'drawer' AND m.ref_id = :wh
        """), {"wh": env["warehouse_id"]})).scalar_one()
    assert parent_role == "cash_group"
    number = await _count("SELECT count(*) FROM acc_entries WHERE number = 'JE-000001'")
    assert number == 1


async def test_credit_sale_debits_receivables_with_the_customer_as_party():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, customer_id=env["customer_id"], is_credit=True),
                                               env["cashier_id"])
    lines = await _lines("sale", sale.id)
    assert ("receivables", D("200.00"), D("0.00"), env["customer_id"]) in lines
    assert ("sales", D("0.00"), D("200.00"), None) in lines


async def test_split_payment_posts_one_debit_per_way_paid():
    env = await _env()
    payments = [SplitPaymentItem(method="cash", amount=D("100")), SplitPaymentItem(method="wallet", amount=D("60"),
                wallet_id=env["wallet_id"]), SplitPaymentItem(method="credit", amount=D("30")),
                SplitPaymentItem(method="bank", amount=D("10"))]
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, customer_id=env["customer_id"], payments=payments),
                                               env["cashier_id"])
    debits = {acc: d for acc, d, c, _ in await _lines("sale", sale.id) if d}
    assert debits == {"درج كاشير — فرع وسط البلد": D("100.00"), "محفظة — فودافون كاش": D("60.00"),
                      "receivables": D("30.00"), "حساب بنكي افتراضي": D("10.00"), "cogs": D("120.00")}


async def test_partial_return_and_cancel_post_their_own_entries():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, qty="3"), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        out = await sales_service.partial_return_sale(s, sale.id, {"items": [{"product_id": env["product_id"], "qty": 1}]},
                                                      env["cashier_id"])
    ret_lines = await _lines("sale_return", uuid.UUID(out["sale_id"]), "confirm")
    assert ret_lines == [
        ("sales_returns", D("100.00"), D("0.00"), None),
        ("inventory", D("60.00"), D("0.00"), None),
        ("cogs", D("0.00"), D("60.00"), None),
        ("درج كاشير — فرع وسط البلد", D("0.00"), D("100.00"), None),
    ]

    # A sale with no return is cancelled: its entry is reversed and the net is zero.
    async with AsyncSessionLocal() as s:
        other = await sales_service.create_sale(s, _sale(env, qty="1"), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        await sales_service.cancel_sale(s, other.id, env["cashier_id"])
    async with AsyncSessionLocal() as s:
        rev = (await s.execute(text(
            "SELECT e.reverses_id, o.id AS orig FROM acc_entries e JOIN acc_entries o ON o.source_id = e.source_id "
            "AND o.event = 'confirm' WHERE e.source_id = :id AND e.event = 'reverse'"), {"id": other.id})).one()
    assert rev.reverses_id == rev.orig
    net = {}
    for acc, d, c, _ in await _lines("sale", other.id):
        net[acc] = net.get(acc, D("0")) + d - c
    assert set(net.values()) == {D("0")}


async def test_customer_receipt_and_adjustment():
    from app.activities.general.modules.contacts import service as contacts

    env = await _env()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await contacts.adjust_balance(s, env["customer_id"], D("500"), "رصيد سابق", user)
        await s.commit()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        payment = await contacts.receive_payment(s, env["customer_id"], D("150"), user, safe_id=env["safe_id"])
        await s.commit()
    assert await _lines("customer_payment", payment.id) == [
        ("خزنة — الخزينة الرئيسية", D("150.00"), D("0.00"), None),
        ("receivables", D("0.00"), D("150.00"), env["customer_id"]),
    ]
    bal = await _balances()
    assert bal["receivables"] == D("350.00") and bal["opening_equity"] == D("-500.00")


async def test_drawer_rows_shift_difference_and_revenue_delivery():
    from types import SimpleNamespace

    env = await _env()
    async with AsyncSessionLocal() as s:
        exp = await pos_service.add_transaction(s, env["shift_id"], DrawerTxType.expense, D("40"), env["cashier_id"],
                                                note="بوفيه")
    async with AsyncSessionLocal() as s:
        dep = await pos_service.add_transaction(s, env["shift_id"], DrawerTxType.deposit, D("25"), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        await pos_service.delete_drawer_transaction(s, dep.id, env["cashier_id"])
    # Money from the drawer to the safe (manager authorisation is checked by the route's service).
    async with AsyncSessionLocal() as s:
        await s.execute(text("UPDATE users SET is_manager = true WHERE id = :id"), {"id": env["cashier_id"]})
        await s.commit()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await pos_service.revenue_delivery(s, env["shift_id"], SimpleNamespace(
            manager_id=env["cashier_id"], manager_password="Pass123!", amount=D("300"), safe_id=env["safe_id"], notes=None),
            user)
    # 1000 - 40 - 300 expected; counted 650: 10 short.
    async with AsyncSessionLocal() as s:
        await pos_service.close_shift(s, env["shift_id"], D("650"), None, None, env["cashier_id"])

    assert await _lines("drawer_tx", exp.id) == [("other_expenses", D("40.00"), D("0.00"), None),
                                                 ("درج كاشير — فرع وسط البلد", D("0.00"), D("40.00"), None)]
    assert len(await _lines("drawer_tx", dep.id)) == 4  # posted, then reversed
    bal = await _balances()
    assert bal["خزنة — الخزينة الرئيسية"] == D("300.00")
    assert bal["cash_shortage"] == D("10.00")
    assert bal["درج كاشير — فرع وسط البلد"] == D("-350.00")  # -40 -300 -10: no opening entry yet (step 4)
    assert bal.get("other_income", D("0")) == D("0")


async def test_expense_approve_then_cancel_nets_to_zero():
    from app.activities.general.modules.finance.services import expenses

    env = await _env()
    async with AsyncSessionLocal() as s:
        await chart.ensure_chart(s, env["tenant_id"])
        rent = (await chart.account_by_role(s, env["tenant_id"], "rent_expense")).id
        cat = (await s.execute(text("INSERT INTO financial_categories (name, type, account_id) "
                                    "VALUES ('إيجار', 'expense', :a) RETURNING id"), {"a": rent})).scalar_one()
        eid = (await s.execute(text("INSERT INTO expenses (amount, description, category_id, safe_id, payment_method, date, status) "
                                    "VALUES (250, 'إيجار المحل', :c, :s, 'cash', :d, 'draft') RETURNING id"),
                               {"c": cat, "s": env["safe_id"], "d": posting.today()})).scalar_one()
        await s.commit()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await expenses.decide(s, eid, True, None, user)
        await s.commit()
    assert await _lines("expense", eid, "approve") == [("rent_expense", D("250.00"), D("0.00"), None),
                                                       ("خزنة — الخزينة الرئيسية", D("0.00"), D("250.00"), None)]
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await expenses.cancel(s, eid, "خطأ", user)
        await s.commit()
    bal = await _balances()
    assert bal["rent_expense"] == 0 and bal["خزنة — الخزينة الرئيسية"] == 0


async def test_posting_into_a_closed_month_is_refused():
    from app.activities.general.modules.finance.services import expenses

    env = await _env()
    last_month = (posting.today().replace(day=1) - timedelta(days=1))
    async with AsyncSessionLocal() as s:
        eid = (await s.execute(text("INSERT INTO expenses (amount, description, safe_id, payment_method, date, status) "
                                    "VALUES (90, 'صيانة', :s, 'cash', :d, 'draft') RETURNING id"),
                               {"s": env["safe_id"], "d": last_month})).scalar_one()
        await s.execute(text("INSERT INTO accounting_periods (month, status) VALUES (:m, 'closed')"),
                        {"m": last_month.strftime("%Y-%m")})
        await s.commit()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        with pytest.raises(BusinessError) as e:
            await expenses.decide(s, eid, True, None, user)
        assert "مغلقة" in str(e.value.detail if hasattr(e.value, "detail") else e.value)
        await s.rollback()
    # Nothing happened: the expense is still a draft and the safe untouched.
    assert await _count("SELECT count(*) FROM expenses WHERE id = :id AND status = 'draft'", id=eid) == 1
    assert await _count("SELECT count(*) FROM safes WHERE id = :id AND balance = 1000", id=env["safe_id"]) == 1


async def test_posting_twice_is_idempotent_and_unbalanced_entries_are_refused():
    env = await _env()
    tid = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        cash = await chart.money_account(s, tid, "safe", env["safe_id"])
        income = (await chart.account_by_role(s, tid, "other_income")).id
        group = (await chart.account_by_role(s, tid, "cash_group")).id
        src = uuid.uuid4()
        lines = [posting.dr(cash, 10), posting.cr(income, 10)]
        first = await posting.post(s, tid, "manual", src, "manual", posting.today(), lines)
        again = await posting.post(s, tid, "manual", src, "manual", posting.today(), lines)
        assert first.id == again.id
        with pytest.raises(BusinessError):
            await posting.post(s, tid, "manual", uuid.uuid4(), "manual", posting.today(),
                               [posting.dr(cash, 10), posting.cr(income, 9)])
        with pytest.raises(BusinessError):
            await posting.post(s, tid, "manual", uuid.uuid4(), "manual", posting.today(),
                               [posting.dr(group, 10), posting.cr(income, 10)])
        await s.commit()
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_id = :id", id=src) == 1

    # The database itself refuses an unbalanced entry at commit, and changes to posted lines.
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, tid)  # raw SQL goes through RLS like the app's own writes
        eid = uuid.uuid4()
        await s.execute(text("INSERT INTO acc_entries (id, tenant_id, number, date, source_type, source_id, event) "
                             "VALUES (:id, :t, 'X-1', CURRENT_DATE, 'manual', :id, 'manual')"), {"id": eid, "t": tid})
        await s.execute(text("INSERT INTO acc_lines (tenant_id, entry_id, account_id, debit) VALUES (:t, :e, :a, 5)"),
                        {"t": tid, "e": eid, "a": cash})
        with pytest.raises(DBAPIError, match="acc_entry_unbalanced"):
            await s.commit()
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, tid)
        with pytest.raises(DBAPIError, match="acc_posted_immutable"):
            await s.execute(text("UPDATE acc_lines SET debit = 20 WHERE entry_id = :e AND debit > 0"), {"e": first.id})


async def test_a_workspace_without_accounting_posts_nothing():
    env = await _env(accounting=False)
    async with AsyncSessionLocal() as s:
        await sales_service.create_sale(s, _sale(env), env["cashier_id"])
    assert await _count("SELECT count(*) FROM acc_entries") == 0
    assert await _count("SELECT count(*) FROM acc_accounts") == 0


async def test_trial_balance_balances_and_entries_are_isolated_per_workspace():
    env = await _env()
    async with AsyncSessionLocal() as s:
        await sales_service.create_sale(s, _sale(env, customer_id=env["customer_id"], is_credit=True), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        await sales_service.create_sale(s, _sale(env, qty="1"), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        tb = await ledger.trial_balance(s, env["tenant_id"], date(2000, 1, 1), posting.today())
        page = await ledger.list_entries(s, env["tenant_id"], page_size=1)
        detail = await ledger.get_entry(s, env["tenant_id"], page["items"][0]["id"])
    assert tb["balanced"] and tb["total_debit"] == tb["total_credit"] == 480.0
    assert page["total"] == 2 and len(page["items"]) == 1
    assert sum(ln["debit"] for ln in detail["lines"]) == sum(ln["credit"] for ln in detail["lines"])

    other = await _env()  # binds the other workspace
    assert other["tenant_id"] != env["tenant_id"]
    assert await _count("SELECT count(*) FROM acc_entries") == 0
    assert await _count("SELECT count(*) FROM acc_lines WHERE tenant_id = :t", t=env["tenant_id"]) == 0


async def test_closing_needs_earlier_months_closed_and_reopening_needs_a_reason():
    from app.activities.general.modules.finance.routes import periods

    env = await _env()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        # The books start with an entry two months back.
        cash = await chart.money_account(s, env["tenant_id"], "safe", env["safe_id"])
        income = (await chart.account_by_role(s, env["tenant_id"], "other_income")).id
        two_back = (posting.today().replace(day=1) - timedelta(days=32)).replace(day=5)
        await posting.post(s, env["tenant_id"], "manual", uuid.uuid4(), "manual", two_back,
                           [posting.dr(cash, 1), posting.cr(income, 1)])
        await s.commit()
        m2, m1 = two_back.strftime("%Y-%m"), (posting.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        with pytest.raises(BusinessError):
            await periods.close_period(m1, db=s, current_user=user)
        await s.rollback()
        await periods.close_period(m2, db=s, current_user=user)
        await periods.close_period(m1, db=s, current_user=user)
        with pytest.raises(BusinessError):  # the later month is reopened first
            await periods.reopen_period(m2, periods.ReopenRequest(reason="تصحيح قيد"), db=s, current_user=user)
        await s.rollback()
        await periods.reopen_period(m1, periods.ReopenRequest(reason="تصحيح قيد"), db=s, current_user=user)
        row = (await s.execute(text("SELECT status, reopen_reason, reopened_by FROM accounting_periods WHERE month = :m"),
                               {"m": m1})).one()
    assert row.status == "open" and row.reopen_reason == "تصحيح قيد" and row.reopened_by == env["cashier_id"]
    assert await _count("SELECT count(*) FROM audit_log WHERE entity_type = 'accounting_period'") == 1
