"""ADR-014 D4: every payment says where the money went, and money documents are cancelled or
deactivated instead of deleted (finance, contacts, purchases, HR)."""
import os
import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine

    await engine.dispose()
    yield
    await engine.dispose()


@pytest.fixture
async def ws():
    """A throwaway workspace with an admin, a safe holding 1000 and a wallet holding 500."""
    from app.db.base import AsyncSessionLocal
    from app.platform.auth.models.user import User
    from app.platform.tenancy.context import bind_tenant, current_tenant_id, install_tenancy_events
    from app.platform.tenancy.models import Tenant
    from app.models.registry import load_all_models

    load_all_models()
    install_tenancy_events()
    tid, uid = uuid.uuid4(), uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(Tenant(id=tid, name=f"Money {tid.hex[:6]}", slug=f"money-{tid.hex[:8]}", status="active"))
        await db.flush()
        db.add(User(id=uid, tenant_id=tid, username=f"money_{tid.hex[:8]}", full_name="محاسب", role="admin",
                    password_hash="x", is_active=True))
        await db.commit()
    async with AsyncSessionLocal() as db:
        await bind_tenant(db, tid)
        safe_id = (await db.execute(text(
            "INSERT INTO safes (name, balance) VALUES ('الخزينة الرئيسية', 1000) RETURNING id"))).scalar_one()
        wallet_id = (await db.execute(text(
            "INSERT INTO payment_wallets (name, type, balance) VALUES ('فودافون كاش', 'vodafone_cash', 500) RETURNING id"
        ))).scalar_one()
        await db.commit()
    yield {"tid": tid, "uid": uid, "safe_id": safe_id, "wallet_id": wallet_id}
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        await db.execute(text("DELETE FROM tenants WHERE id = :t"), {"t": tid})
        await db.commit()


async def _session(ws):
    from app.db.base import AsyncSessionLocal
    from app.platform.auth.models.user import User
    from app.platform.tenancy.context import bind_tenant

    db = AsyncSessionLocal()
    await bind_tenant(db, ws["tid"])
    user = await db.get(User, ws["uid"])
    db.expunge(user)  # like a request's user: loaded once, not expired by the commits under test
    return db, user


async def _safe_balance(db, safe_id) -> Decimal:
    return Decimal(str((await db.execute(text("SELECT balance FROM safes WHERE id=:id"), {"id": safe_id})).scalar_one()))


async def _wallet_balance(db, wallet_id) -> Decimal:
    return Decimal(str((await db.execute(text("SELECT balance FROM payment_wallets WHERE id=:id"),
                                         {"id": wallet_id})).scalar_one()))


async def _expense(db, user, **fields) -> uuid.UUID:
    from app.activities.general.modules.finance.routes.expenses import create_expense
    from app.activities.general.modules.finance.schemas.expense import ExpenseCreate

    row = await create_expense(ExpenseCreate(amount=Decimal("200"), description="كهرباء", **fields), db=db,
                               current_user=user, _=None)
    return row["id"]


async def test_approved_expense_is_cancelled_not_deleted(ws):
    from app.activities.general.modules.finance.routes import expenses as routes
    from app.activities.general.modules.finance.schemas.expense import ExpenseApprove, ExpenseCancel, ExpenseUpdate
    from app.activities.general.modules.finance.services import expenses as service

    db, user = await _session(ws)
    async with db:
        draft = await _expense(db, user, payment_method="cash")
        # a cash expense must name its safe before it can be approved
        with pytest.raises(HTTPException) as e:
            await service.decide(db, draft, True, None, user)
        assert e.value.status_code == 400
        await db.rollback()

        eid = await _expense(db, user, payment_method="cash", safe_id=ws["safe_id"])
        await routes.approve_expense(eid, ExpenseApprove(), db=db, current_user=user)
        assert await _safe_balance(db, ws["safe_id"]) == Decimal("800")

        with pytest.raises(HTTPException) as e:
            await routes.delete_expense(eid, db=db, _=user)
        assert e.value.status_code == 409
        with pytest.raises(HTTPException) as e:
            await routes.update_expense(eid, ExpenseUpdate(amount=Decimal("50")), db=db, _=user)
        assert e.value.status_code == 409
        await db.rollback()
        updated = await routes.update_expense(eid, ExpenseUpdate(notes="فاتورة أكتوبر"), db=db, _=user)
        assert updated["notes"] == "فاتورة أكتوبر"

        cancelled = await routes.cancel_expense(eid, ExpenseCancel(reason="خطأ"), db=db, current_user=user)
        assert cancelled["status"] == "cancelled" and cancelled["cancelled_by"] == user.id and cancelled["cancelled_at"]
        assert await _safe_balance(db, ws["safe_id"]) == Decimal("1000")
        with pytest.raises(HTTPException) as e:
            await routes.cancel_expense(eid, None, db=db, current_user=user)
        assert e.value.status_code == 409
        await db.rollback()

        # a draft can still be deleted
        await routes.delete_expense(draft, db=db, _=user)
        assert (await db.execute(text("SELECT count(*) FROM expenses WHERE id=:id"), {"id": draft})).scalar() == 0


async def test_wallet_expense_cancel_puts_money_back(ws):
    from app.activities.general.modules.finance.routes import expenses as routes
    from app.activities.general.modules.finance.schemas.expense import ExpenseApprove

    db, user = await _session(ws)
    async with db:
        eid = await _expense(db, user, payment_method="wallet")
        await routes.approve_expense(eid, ExpenseApprove(wallet_id=ws["wallet_id"]), db=db, current_user=user)
        assert await _wallet_balance(db, ws["wallet_id"]) == Decimal("300")
        await routes.cancel_expense(eid, None, db=db, current_user=user)
        assert await _wallet_balance(db, ws["wallet_id"]) == Decimal("500")


async def test_customer_receipt_without_shift_goes_to_a_safe(ws):
    from app.activities.general.modules.contacts.models.party import Customer
    from app.activities.general.modules.contacts.routes import parties
    from app.activities.general.modules.contacts.schemas import CustomerPaymentCreate

    db, user = await _session(ws)
    async with db:
        c = Customer(name="عميل آجل", balance=Decimal("300"))
        db.add(c)
        await db.commit()
        cid = c.id
        with pytest.raises(HTTPException) as e:  # no open shift and no safe: refused
            await parties.add_payment(cid, CustomerPaymentCreate(amount=Decimal("100")), db=db, current_user=user)
        assert e.value.status_code == 400
        await db.rollback()

        p = await parties.add_payment(cid, CustomerPaymentCreate(amount=Decimal("100"), safe_id=ws["safe_id"]),
                                      db=db, current_user=user)
        assert p["safe_id"] == str(ws["safe_id"]) and p["method"] == "cash"
        assert await _safe_balance(db, ws["safe_id"]) == Decimal("1100")
        tx = (await db.execute(text("SELECT ref_type, ref_id FROM safe_transactions WHERE safe_id=:s"),
                               {"s": ws["safe_id"]})).one()
        assert tx.ref_type == "customer_payment" and str(tx.ref_id) == p["id"]

        await parties.add_payment(cid, CustomerPaymentCreate(amount=Decimal("50"), wallet_id=ws["wallet_id"]),
                                  db=db, current_user=user)
        assert await _wallet_balance(db, ws["wallet_id"]) == Decimal("550")
        assert (await db.execute(text("SELECT balance FROM customers WHERE id=:c"), {"c": cid})).scalar() == Decimal("150")


async def test_customer_with_transactions_is_deactivated_not_deleted(ws):
    from app.activities.general.modules.contacts.models.party import Customer
    from app.activities.general.modules.contacts.routes import parties
    from app.activities.general.modules.contacts.schemas import SetBalanceRequest

    db, user = await _session(ws)
    async with db:
        fresh, used = Customer(name="عميل جديد"), Customer(name="عميل قديم")
        db.add_all([fresh, used])
        await db.commit()
        fresh_id, used_id = fresh.id, used.id

        # setting the balance records an adjustment: the opening balance first, a correction later
        r = await parties.set_customer_balance(used_id, SetBalanceRequest(balance=Decimal("250"), note="رصيد افتتاحي"),
                                               db=db, current_user=user)
        assert r["kind"] == "opening" and r["amount"] == 250.0
        r = await parties.set_customer_balance(used_id, SetBalanceRequest(balance=Decimal("200")), db=db, current_user=user)
        assert r["kind"] == "adjustment" and r["amount"] == -50.0
        rows = (await db.execute(text(
            "SELECT kind, amount, balance_before, balance_after FROM customer_adjustments WHERE customer_id=:c ORDER BY created_at"
        ), {"c": used_id})).all()
        assert [(k, a, b, af) for k, a, b, af in rows] == [
            ("opening", Decimal("250"), Decimal("0"), Decimal("250")),
            ("adjustment", Decimal("-50"), Decimal("250"), Decimal("200")),
        ]
        account = await parties.customer_account(used_id, db=db, _=user)
        assert account["total_adjustments"] == 200.0 and account["balance_due"] == 200.0

        with pytest.raises(HTTPException) as e:
            await parties.delete_customer(used_id, db=db, _=user)
        assert e.value.status_code == 409
        await db.rollback()
        await parties.deactivate_customer(used_id, db=db, _=user)
        names = {c["name"] for c in await parties.list_customers(db=db, _=user, limit=100, offset=0)}
        assert "عميل قديم" not in names and "عميل جديد" in names
        names = {c["name"] for c in await parties.list_customers(include_inactive=True, db=db, _=user, limit=100, offset=0)}
        assert "عميل قديم" in names

        await parties.delete_customer(fresh_id, db=db, _=user)  # no transactions: deleted


async def _product_and_warehouse(db):
    from app.activities.general.modules.inventory.models.product import Product
    from app.activities.general.modules.inventory.models.warehouse import Warehouse

    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:4]}", name="المخزن", is_active=True)
    p = Product(name="صنف", code=f"P-{uuid.uuid4().hex[:6]}", retail_price=Decimal("20"), cost_price=Decimal("10"),
                stock_status="tracked", is_active=True)
    db.add_all([wh, p])
    await db.commit()
    return p, wh


async def test_purchase_receipt_and_supplier_payment_leave_the_safe(ws):
    from app.activities.general.modules.purchases import service
    from app.activities.general.modules.purchases.routes import suppliers
    from app.activities.general.modules.purchases.schemas.purchase import PurchaseCreate, PurchaseItemCreate, PurchaseReceive

    db, user = await _session(ws)
    async with db:
        p, wh = await _product_and_warehouse(db)
        sid = (await db.execute(text("INSERT INTO suppliers (name) VALUES ('المورد') RETURNING id"))).scalar_one()
        await db.commit()
        po = await service.create_purchase(db, PurchaseCreate(
            warehouse_id=wh.id, supplier_id=sid, items=[PurchaseItemCreate(product_id=p.id, qty=Decimal("10"), unit_cost=Decimal("50"))],
        ), user)

        with pytest.raises(HTTPException) as e:  # a payment on receipt must name its source
            await service.receive_purchase(db, uuid.UUID(po["id"]), PurchaseReceive(amount_paid=Decimal("200")), user)
        assert e.value.status_code == 400
        await db.rollback()

        await service.receive_purchase(db, uuid.UUID(po["id"]),
                                       PurchaseReceive(amount_paid=Decimal("200"), safe_id=ws["safe_id"]), user)
        assert await _safe_balance(db, ws["safe_id"]) == Decimal("800")
        txs = (await db.execute(text(
            "SELECT type, amount, safe_id FROM supplier_transactions WHERE supplier_id=:s ORDER BY type DESC"
        ), {"s": sid})).all()
        assert [(t, a) for t, a, _ in txs] == [("debit", Decimal("500")), ("credit", Decimal("200"))]
        assert txs[1].safe_id == ws["safe_id"]
        assert (await db.execute(text("SELECT balance FROM suppliers WHERE id=:s"), {"s": sid})).scalar() == Decimal("300")

        with pytest.raises(HTTPException) as e:  # a supplier payment must name its source
            await suppliers.add_transaction(sid, suppliers.TxIn(amount=Decimal("100"), type="credit"), db=db, current_user=user)
        assert e.value.status_code == 400
        await db.rollback()
        await suppliers.add_transaction(sid, suppliers.TxIn(amount=Decimal("100"), type="credit", wallet_id=ws["wallet_id"]),
                                        db=db, current_user=user)
        assert await _wallet_balance(db, ws["wallet_id"]) == Decimal("400")
        assert (await db.execute(text("SELECT balance FROM suppliers WHERE id=:s"), {"s": sid})).scalar() == Decimal("200")

        ledger = await suppliers.supplier_ledger(sid, db=db, _=user)
        assert len(ledger["transactions"]) == 3 and ledger["transactions"][0]["wallet_name"] == "فودافون كاش"

        with pytest.raises(HTTPException) as e:
            await suppliers.delete_supplier(sid, db=db, _=user)
        assert e.value.status_code == 409


async def test_payroll_pays_once_from_the_safe(ws):
    from app.activities.general.modules.hr.services import payroll
    from app.core.exceptions import BusinessError

    db, user = await _session(ws)
    async with db:
        emp = (await db.execute(text(
            "INSERT INTO hr_employees (name, monthly_salary) VALUES ('موظف', 3000) RETURNING id"))).scalar_one()
        pid = (await db.execute(text(
            "INSERT INTO hr_payroll_periods (month, status) VALUES ('2026-10', 'review') RETURNING id"))).scalar_one()
        await db.execute(text("""
            INSERT INTO hr_payroll_entries (period_id, employee_id, base_salary, bonuses, net_salary, status)
            VALUES (:p, :e, 3000, 0, 600, 'review')
        """), {"p": pid, "e": emp})
        await db.commit()

        await payroll.approve_payroll_period(db, "2026-10", str(user.id))
        assert await _safe_balance(db, ws["safe_id"]) == Decimal("1000")  # approving moves no money
        expense = (await db.execute(text("SELECT status, payment_method, amount FROM expenses WHERE notes='HR payroll month 2026-10'"))).one()
        assert tuple(expense) == ("approved", "payroll", Decimal("600"))

        with pytest.raises(HTTPException):  # paying needs a source
            await payroll.pay_payroll_period(db, "2026-10", str(user.id))
        await db.rollback()
        await payroll.pay_payroll_period(db, "2026-10", str(user.id), safe_id=ws["safe_id"])
        assert await _safe_balance(db, ws["safe_id"]) == Decimal("400")
        tx = (await db.execute(text("SELECT ref_type, ref_id FROM safe_transactions WHERE safe_id=:s"), {"s": ws["safe_id"]})).one()
        assert tx.ref_type == "payroll" and tx.ref_id == pid

        with pytest.raises(BusinessError):
            await payroll.pay_payroll_period(db, "2026-10", str(user.id), safe_id=ws["safe_id"])
        await db.rollback()
        with pytest.raises(BusinessError):
            await payroll.reopen_payroll_period(db, "2026-10", str(user.id))
        await db.rollback()
        assert await _safe_balance(db, ws["safe_id"]) == Decimal("400")


async def test_reopening_an_approved_payroll_cancels_its_expense(ws):
    from app.activities.general.modules.hr.services import payroll

    db, user = await _session(ws)
    async with db:
        emp = (await db.execute(text(
            "INSERT INTO hr_employees (name, monthly_salary) VALUES ('موظف', 3000) RETURNING id"))).scalar_one()
        pid = (await db.execute(text(
            "INSERT INTO hr_payroll_periods (month, status) VALUES ('2026-09', 'review') RETURNING id"))).scalar_one()
        await db.execute(text("""
            INSERT INTO hr_payroll_entries (period_id, employee_id, base_salary, bonuses, net_salary, status)
            VALUES (:p, :e, 3000, 0, 700, 'review')
        """), {"p": pid, "e": emp})
        await db.commit()
        await payroll.approve_payroll_period(db, "2026-09", str(user.id))
        await payroll.reopen_payroll_period(db, "2026-09", str(user.id))
        assert (await db.execute(text("SELECT status FROM hr_payroll_periods WHERE id=:p"), {"p": pid})).scalar() == "draft"
        assert (await db.execute(text("SELECT status FROM expenses WHERE notes='HR payroll month 2026-09'"))).scalar() == "cancelled"


async def test_advances_are_paid_out_and_bonuses_are_not_deducted(ws):
    from app.activities.general.modules.hr.routes.hr import add_advance
    from app.activities.general.modules.hr.schemas import AdvanceCreate
    from app.activities.general.modules.hr.services import payroll

    db, user = await _session(ws)
    async with db:
        emp = (await db.execute(text(
            "INSERT INTO hr_employees (name, monthly_salary) VALUES ('موظف', 3000) RETURNING id"))).scalar_one()
        await db.commit()
        day = __import__("datetime").date(2026, 8, 10)
        with pytest.raises(HTTPException):  # an advance must name its source
            await add_advance(AdvanceCreate(employee_id=emp, amount=Decimal("100"), date=day), db=db, current_user=user)
        await db.rollback()
        await add_advance(AdvanceCreate(employee_id=emp, amount=Decimal("100"), date=day, safe_id=ws["safe_id"]),
                          db=db, current_user=user)
        await add_advance(AdvanceCreate(employee_id=emp, amount=Decimal("50"), date=day, record_type="مكافأة"),
                          db=db, current_user=user)
        await add_advance(AdvanceCreate(employee_id=emp, amount=Decimal("30"), date=day, record_type="خصم"),
                          db=db, current_user=user)
        assert await _safe_balance(db, ws["safe_id"]) == Decimal("900")  # only the advance moved cash

        assert await payroll.load_hr_records_for_month(db, emp, "2026-08") == {"advance": 100.0, "deduction": 30.0, "bonus": 50.0}
        await payroll.calculate_payroll_month(db, "2026-08", str(user.id), employee_id=emp)
        entry = (await db.execute(text(
            "SELECT advances, deductions, bonuses FROM hr_payroll_entries WHERE employee_id=:e"), {"e": emp})).one()
        assert tuple(entry) == (Decimal("100"), Decimal("30"), Decimal("50"))

        # with no attendance the base pay is 0, so a bonus alone is the whole salary: it adds, it is never deducted
        rewarded = (await db.execute(text(
            "INSERT INTO hr_employees (name, monthly_salary) VALUES ('موظف مكافأ', 3000) RETURNING id"))).scalar_one()
        await db.commit()
        await add_advance(AdvanceCreate(employee_id=rewarded, amount=Decimal("75"), date=day, record_type="مكافأة"),
                          db=db, current_user=user)
        await payroll.calculate_payroll_month(db, "2026-08", str(user.id), employee_id=rewarded)
        entry = (await db.execute(text(
            "SELECT advances, bonuses, net_salary FROM hr_payroll_entries WHERE employee_id=:e"), {"e": rewarded})).one()
        assert tuple(entry) == (Decimal("0"), Decimal("75"), Decimal("75"))


async def test_wallet_reset_is_recorded(ws):
    from app.activities.general.modules.finance.routes.wallets import reset_wallet_balance

    db, user = await _session(ws)
    async with db:
        await reset_wallet_balance(ws["wallet_id"], db=db, current_user=user)
        assert await _wallet_balance(db, ws["wallet_id"]) == Decimal("0")
        tx = (await db.execute(text("SELECT tx_type, amount FROM wallet_transactions WHERE wallet_id=:w"),
                               {"w": ws["wallet_id"]})).one()
        assert tuple(tx) == ("adjustment", Decimal("-500"))
