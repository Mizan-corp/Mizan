"""Posting rules of step 3 of ADR-014 D12: purchases, supplier payments and purchase returns, stock
adjustments, payroll and HR advances, clinic invoices and the manager's shift deposit.

Each rule posts one balanced entry in its document's transaction, only for workspaces with the
accounting module; posting twice does nothing; a reopened payroll month is reversed once.
"""
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.activities.general.modules.accounting.posting import purchases as purchase_posting
from app.activities.general.modules.accounting.services import chart, posting
from app.activities.general.modules.contacts.models.party import Customer, Supplier
from app.activities.general.modules.finance.models.payment_wallet import PaymentWallet
from app.activities.general.modules.hr.models.payroll import HrEmployee, HrPayrollPeriod
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement, get_balance
from app.activities.general.modules.pos import service as pos_service
from app.activities.general.modules.pos.models import Shift
from app.activities.general.modules.purchases import service as purchase_service
from app.activities.general.modules.purchases.schemas.purchase import (
    PurchaseCreate,
    PurchaseItemCreate,
    PurchaseReceive,
    PurchaseReturnCreate,
    PurchaseReturnItemIn,
)
from app.db.base import AsyncSessionLocal
from app.models.registry import load_all_models
from app.platform.auth.models.user import User
from app.platform.auth.security import hash_password
from app.platform.tenancy.context import bind_tenant, current_tenant_id, install_tenancy_events
from app.platform.tenancy.models import Tenant

load_all_models()
install_tenancy_events()

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")

MODULES = ["sales", "pos", "shifts", "inventory", "finance", "contacts", "purchases", "hr", "healthcare_clinic"]
D = Decimal
SAFE = "خزنة — الخزينة الرئيسية"
DRAWER = "درج كاشير — فرع وسط البلد"


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()
    current_tenant_id.set(None)


async def _env(accounting: bool = True) -> dict:
    """A workspace (with or without accounting): a branch, a manager-cashier with an open shift (1000 in
    the drawer), a supplier, a safe holding 1000 and a product with 50 units at cost 60."""
    t_id = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=t_id, name=f"Post2 {t_id.hex[:6]}", slug=f"post2-{t_id.hex[:8]}", status="active",
                     active_modules=MODULES + (["accounting"] if accounting else [])))
        await s.flush()
        wh = Warehouse(id=uuid.uuid4(), tenant_id=t_id, code=f"WH-{t_id.hex[:4]}", name="فرع وسط البلد", is_active=True)
        cashier = User(id=uuid.uuid4(), tenant_id=t_id, username=f"p2_{t_id.hex[:8]}", full_name="كاشير",
                       role="admin", password_hash=hash_password("Pass123!"), is_manager=True,
                       permissions=["sales", "pos", "shifts", "purchases", "inventory", "payroll"], is_active=True)
        product = Product(id=uuid.uuid4(), tenant_id=t_id, name="صنف", code=f"P-{t_id.hex[:6]}",
                          retail_price=D("100"), cost_price=D("60"), stock_status="tracked", is_active=True)
        supplier = Supplier(id=uuid.uuid4(), tenant_id=t_id, name="مورد", balance=D("0"))
        customer = Customer(id=uuid.uuid4(), tenant_id=t_id, name="عميل", balance=D("0"))
        wallet = PaymentWallet(id=uuid.uuid4(), tenant_id=t_id, name="فودافون كاش", type="vodafone",
                               balance=D("0"), is_active=True)
        s.add_all([wh, cashier, product, supplier, customer, wallet])
        await s.flush()
        shift = Shift(id=uuid.uuid4(), tenant_id=t_id, cashier_id=cashier.id, warehouse_id=wh.id, status="open",
                      initial_amount=D("1000"), started_at=datetime.now(UTC))
        s.add(shift)
        await s.commit()
    current_tenant_id.set(t_id)
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, t_id)
        safe_id = uuid.uuid4()
        await s.execute(text("INSERT INTO safes (id, tenant_id, name, balance) VALUES (:id, :t, 'الخزينة الرئيسية', 1000)"),
                        {"id": safe_id, "t": t_id})
        await apply_movement(s, product_id=product.id, warehouse_id=wh.id, movement_type=MovementType.opening_stock,
                             qty=D("50"), unit_cost=D("60"), created_by=cashier.id)
        await s.commit()
    return {"tenant_id": t_id, "warehouse_id": wh.id, "cashier_id": cashier.id, "product_id": product.id,
            "shift_id": shift.id, "supplier_id": supplier.id, "wallet_id": wallet.id, "safe_id": safe_id}


async def _user(s, env) -> User:
    user = await s.get(User, env["cashier_id"])
    s.expunge(user)
    return user


async def _set(source_type: str, source_id=None, event: str | None = None) -> set[tuple]:
    """{(account role or name, debit, credit, party_id)} of the entries of a document (or of every
    entry of a source type when no id is given)."""
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text("""
            SELECT COALESCE(a.role, a.name) AS acc, l.debit, l.credit, l.party_id
            FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id JOIN acc_entries e ON e.id = l.entry_id
            WHERE e.source_type = :st AND (CAST(:sid AS uuid) IS NULL OR e.source_id = :sid)
              AND (CAST(:ev AS text) IS NULL OR e.event = :ev)
        """), {"st": source_type, "sid": source_id, "ev": event})).all()
    return {(r.acc, r.debit, r.credit, r.party_id) for r in rows}


async def _balances() -> dict[str, Decimal]:
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text("""
            SELECT COALESCE(a.role, a.name) AS acc, SUM(l.debit - l.credit) AS bal
            FROM acc_lines l JOIN acc_accounts a ON a.id = l.account_id GROUP BY 1
        """))).all()
    return {r.acc: r.bal for r in rows}


async def _count(sql: str, **params) -> int:
    async with AsyncSessionLocal() as s:
        return (await s.execute(text(sql), params)).scalar_one()


async def _scalar(sql: str, **params):
    async with AsyncSessionLocal() as s:
        return (await s.execute(text(sql), params)).scalar_one()


async def _receive(env, qty="10", cost="70", paid="200", **extra) -> uuid.UUID:
    """A purchase order of `qty` at `cost` from the supplier, received, with `paid` paid from the safe."""
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        po = await purchase_service.create_purchase(s, PurchaseCreate(
            warehouse_id=env["warehouse_id"], supplier_id=env["supplier_id"],
            items=[PurchaseItemCreate(product_id=env["product_id"], qty=D(qty), unit_cost=D(cost))]), user)
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await purchase_service.receive_purchase(s, uuid.UUID(po["id"]), PurchaseReceive(
            amount_paid=D(paid), safe_id=env["safe_id"], **extra), user)
    return uuid.UUID(po["id"])


async def test_purchase_received_with_a_part_payment():
    env = await _env()
    po = await _receive(env)  # 10 x 70 = 700, 200 paid from the safe
    sup = env["supplier_id"]
    assert await _set("purchase", po, "receive") == {
        ("inventory", D("700.00"), D("0.00"), None),
        ("payables", D("0.00"), D("700.00"), sup),
        ("payables", D("200.00"), D("0.00"), sup),
        (SAFE, D("0.00"), D("200.00"), None),
    }
    bal = await _balances()
    assert bal["payables"] == D("-500.00") and bal["inventory"] == D("700.00") and bal[SAFE] == D("-200.00")
    # The ledger agrees with the supplier's balance and the safe.
    assert await _scalar("SELECT balance FROM suppliers WHERE id = :id", id=sup) == D("500.00")
    assert await _scalar("SELECT balance FROM safes WHERE id = :id", id=env["safe_id"]) == D("800.00")

    # Posting the same receipt again changes nothing; receiving it again is refused.
    async with AsyncSessionLocal() as s:
        await purchase_posting.on_purchase_received(s, purchase={
            "id": po, "tenant_id": env["tenant_id"], "po_number": "PO", "supplier_id": sup, "total": D("700"),
            "amount_paid": D("200"), "safe_id": env["safe_id"], "wallet_id": None, "warehouse_id": env["warehouse_id"]})
        await s.commit()
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_id = :id", id=po) == 1
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        with pytest.raises(Exception, match="مستلم بالفعل"):
            await purchase_service.receive_purchase(s, po, PurchaseReceive(), user)


async def test_a_fully_unpaid_purchase_posts_only_the_payable():
    env = await _env()
    po = await _receive(env, paid="0")
    assert await _set("purchase", po) == {("inventory", D("700.00"), D("0.00"), None),
                                          ("payables", D("0.00"), D("700.00"), env["supplier_id"])}


async def test_supplier_payment_and_manual_charge():
    env = await _env()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        pay = await purchase_service.record_supplier_transaction(s, env["supplier_id"], D("150"), "credit", user,
                                                                 safe_id=env["safe_id"], notes="دفعة")
        charge = await purchase_service.record_supplier_transaction(s, env["supplier_id"], D("90"), "debit", user,
                                                                    notes="فاتورة صيانة")
        await s.commit()
    sup = env["supplier_id"]
    assert await _set("supplier_tx", pay["id"], "payment") == {("payables", D("150.00"), D("0.00"), sup),
                                                               (SAFE, D("0.00"), D("150.00"), None)}
    assert await _set("supplier_tx", charge["id"], "charge") == {("other_expenses", D("90.00"), D("0.00"), None),
                                                                 ("payables", D("0.00"), D("90.00"), sup)}
    assert await _scalar("SELECT balance FROM suppliers WHERE id = :id", id=sup) == D("-60.00")
    assert (await _balances())["payables"] == D("60.00")  # we paid 60 more than we owed


async def test_purchase_return_moves_stock_supplier_balance_and_ledger():
    env = await _env()
    po = await _receive(env)  # 10 x 70; the supplier is owed 500
    sup = env["supplier_id"]
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        first = await purchase_service.create_purchase_return(s, po, PurchaseReturnCreate(
            items=[PurchaseReturnItemIn(product_id=env["product_id"], qty=D("4"))]), user)
    assert first["total"] == D("280.00")
    assert await _set("purchase_return", uuid.UUID(first["id"]), "confirm") == {
        ("payables", D("280.00"), D("0.00"), sup), ("inventory", D("0.00"), D("280.00"), None)}
    assert await _scalar("SELECT balance FROM suppliers WHERE id = :id", id=sup) == D("220.00")
    async with AsyncSessionLocal() as s:
        assert await get_balance(s, env["product_id"], env["warehouse_id"]) == D("56")
    mv = await _scalar("SELECT unit_cost FROM stock_movements WHERE movement_type = 'return_out'")
    assert mv == D("70.00")

    # The rest goes back too: the supplier pays 100 back into the safe, the remaining 320 lowers the balance.
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        second = await purchase_service.create_purchase_return(s, po, PurchaseReturnCreate(
            items=[PurchaseReturnItemIn(product_id=env["product_id"], qty=D("6"))], refund_amount=D("100"),
            safe_id=env["safe_id"]), user)
    assert await _set("purchase_return", uuid.UUID(second["id"]), "confirm") == {
        (SAFE, D("100.00"), D("0.00"), None), ("payables", D("320.00"), D("0.00"), sup),
        ("inventory", D("0.00"), D("420.00"), None)}
    assert await _scalar("SELECT balance FROM suppliers WHERE id = :id", id=sup) == D("-100.00")
    assert await _scalar("SELECT balance FROM safes WHERE id = :id", id=env["safe_id"]) == D("900.00")
    # Back to 50 units, and the weighted average is back at 60: the goods left at the cost they came in.
    async with AsyncSessionLocal() as s:
        assert await get_balance(s, env["product_id"], env["warehouse_id"]) == D("50")
    avg = await _scalar("SELECT avg_cost FROM products WHERE id = :id", id=env["product_id"])
    assert abs(avg - D("60")) < D("0.001")
    bal = await _balances()
    assert bal["inventory"] == D("0.00") and bal["payables"] == D("100.00")

    # Nothing is left to return, and the numbers stay as they were after the refusal.
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        with pytest.raises(HTTPException) as e:
            await purchase_service.create_purchase_return(s, po, PurchaseReturnCreate(
                items=[PurchaseReturnItemIn(product_id=env["product_id"], qty=D("1"))]), user)
        assert e.value.status_code == 400
        await s.rollback()
    assert await _count("SELECT count(*) FROM purchase_returns") == 2
    async with AsyncSessionLocal() as s:
        info = await purchase_service.list_purchase_returns(s, po)
    assert info["returnable"][0]["returnable"] == D("0") and len(info["returns"]) == 2


async def test_purchase_return_is_refused_for_an_unreceived_order_and_more_than_the_stock():
    env = await _env()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        po = await purchase_service.create_purchase(s, PurchaseCreate(
            warehouse_id=env["warehouse_id"], supplier_id=env["supplier_id"],
            items=[PurchaseItemCreate(product_id=env["product_id"], qty=D("5"), unit_cost=D("70"))]), user)
    body = PurchaseReturnCreate(items=[PurchaseReturnItemIn(product_id=env["product_id"], qty=D("1"))])
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        with pytest.raises(Exception, match="لم يُستلم"):
            await purchase_service.create_purchase_return(s, uuid.UUID(po["id"]), body, user)
        await s.rollback()
    # Received, then sold off: the stock in the warehouse is below what would go back.
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await purchase_service.receive_purchase(s, uuid.UUID(po["id"]), PurchaseReceive(), user)
    async with AsyncSessionLocal() as s:
        await apply_movement(s, product_id=env["product_id"], warehouse_id=env["warehouse_id"],
                             movement_type=MovementType.damage, qty=D("53"), note="تلف")
        await s.commit()
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        with pytest.raises(HTTPException, match="أقل من الكمية المرتجعة"):
            await purchase_service.create_purchase_return(s, uuid.UUID(po["id"]), PurchaseReturnCreate(
                items=[PurchaseReturnItemIn(product_id=env["product_id"], qty=D("5"))]), user)
        await s.rollback()


async def test_stock_adjustments_post_loss_and_gain_but_not_opening_or_transfers():
    env = await _env()
    p, w = env["product_id"], env["warehouse_id"]
    async with AsyncSessionLocal() as s:
        out, dmg, up, tr = [(await apply_movement(s, product_id=p, warehouse_id=w, movement_type=t, qty=q, note="x",
                                                   unit_cost=c))[0]
                            for t, q, c in [(MovementType.adjustment_out, D("3"), None), (MovementType.damage, D("2"), None),
                                            (MovementType.adjustment_in, D("4"), None),
                                            (MovementType.transfer_out, D("1"), None)]]
        await s.commit()
    assert await _set("stock_movement", out.id) == {("inventory_loss", D("180.00"), D("0.00"), None),
                                                    ("inventory", D("0.00"), D("180.00"), None)}
    assert await _set("stock_movement", dmg.id) == {("inventory_loss", D("120.00"), D("0.00"), None),
                                                    ("inventory", D("0.00"), D("120.00"), None)}
    assert await _set("stock_movement", up.id) == {("inventory", D("240.00"), D("0.00"), None),
                                                   ("other_income", D("0.00"), D("240.00"), None)}
    assert await _set("stock_movement", tr.id) == set()
    # Only the three adjustments are posted: the opening stock and the transfer are not.
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_type = 'stock_movement'") == 3
    assert (await _balances())["inventory"] == D("-60.00")  # -180 - 120 + 240


async def test_new_chart_accounts_reach_existing_workspaces_once():
    env = await _env()
    tid = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        await chart.ensure_chart(s, tid)
        await bind_tenant(s, tid)
        # A workspace whose chart was copied before these accounts existed.
        await s.execute(text("DELETE FROM acc_accounts WHERE role IN ('inventory_loss', 'insurance_receivables')"))
        await s.commit()
    async with AsyncSessionLocal() as s:
        acc = await chart.account_by_role(s, tid, "inventory_loss")  # added on demand, under expenses
        assert acc.type == "expense" and not acc.is_group
        assert await chart.add_missing_accounts(s, tid) == 0  # the same pass added the other one too
        await s.commit()
    assert await _count("SELECT count(*) FROM acc_accounts WHERE role = 'insurance_receivables'") == 1
    assert await _count("SELECT count(*) FROM acc_accounts WHERE role = 'inventory_loss'") == 1


async def _payroll(env, month: str) -> dict:
    """Two employees and a payroll month in review. A: salary 5000 + overtime 200 + bonus 300, less
    lateness 100, a deduction 150 and an advance 500 recovered = net 4750. B: 3000, net 3000."""
    tid = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        a = HrEmployee(id=uuid.uuid4(), tenant_id=tid, name="موظف أ", monthly_salary=D("5000"))
        b = HrEmployee(id=uuid.uuid4(), tenant_id=tid, name="موظف ب", monthly_salary=D("3000"))
        period = HrPayrollPeriod(id=uuid.uuid4(), tenant_id=tid, month=month, status="review")
        s.add_all([a, b, period])
        await s.flush()
        await bind_tenant(s, tid)
        for emp, base, ot, bonus, late, ded, adv, net in [(a, 5000, 200, 300, 100, 150, 500, 4750),
                                                           (b, 3000, 0, 0, 0, 0, 0, 3000)]:
            await s.execute(text("""
                INSERT INTO hr_payroll_entries (id, tenant_id, period_id, employee_id, base_salary, overtime_pay,
                    bonus_payment, bonus, bonuses, lateness_deduction, deductions, advances, net_salary, status)
                VALUES (:id, :t, :p, :e, :base, :ot, 0, :bonus, :bonus, :late, :ded, :adv, :net, 'review')
            """), {"id": uuid.uuid4(), "t": tid, "p": period.id, "e": emp.id, "base": base, "ot": ot, "bonus": bonus,
                   "late": late, "ded": ded, "adv": adv, "net": net})
        await s.execute(text("UPDATE safes SET balance = 20000 WHERE id = :id"), {"id": env["safe_id"]})
        await s.commit()
    return {"a": a.id, "b": b.id, "period": period.id}


async def test_hr_advance_then_payroll_approve_and_pay():
    from app.activities.general.modules.hr.routes import hr as hr_routes
    from app.activities.general.modules.hr.schemas import AdvanceCreate
    from app.activities.general.modules.hr.services import payroll

    env = await _env()
    month = posting.today().strftime("%Y-%m")
    ids = await _payroll(env, month)
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        # A cash advance (سلفة) pays out of the safe; a deduction (خصم) moves no cash and posts nothing.
        adv = await hr_routes.add_advance(AdvanceCreate(employee_id=ids["a"], amount=D("500"), safe_id=env["safe_id"]),
                                          db=s, current_user=user)
        await hr_routes.add_advance(AdvanceCreate(employee_id=ids["a"], amount=D("150"), record_type="خصم"),
                                    db=s, current_user=user)
    assert await _set("hr_advance", uuid.UUID(adv["id"]), "pay") == {
        ("employee_advances", D("500.00"), D("0.00"), ids["a"]), (SAFE, D("0.00"), D("500.00"), None)}
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_type = 'hr_advance'") == 1

    async with AsyncSessionLocal() as s:
        await payroll.approve_payroll_period(s, month, str(env["cashier_id"]))
    expense = await _scalar("SELECT expense_id FROM hr_payroll_periods WHERE month = :m", m=month)
    # Expense = net 7750 + withheld 750; advances recovered 500; the deduction and lateness 250 are income.
    assert await _set("payroll", expense, "approve") == {
        ("salaries_expense", D("8500.00"), D("0.00"), None),
        ("salaries_payable", D("0.00"), D("4750.00"), ids["a"]), ("salaries_payable", D("0.00"), D("3000.00"), ids["b"]),
        ("employee_advances", D("0.00"), D("500.00"), ids["a"]), ("other_income", D("0.00"), D("250.00"), None)}
    bal = await _balances()
    assert bal["employee_advances"] == D("0.00")  # paid out 500, recovered 500
    assert bal["salaries_payable"] == D("-7750.00")

    async with AsyncSessionLocal() as s:
        await payroll.pay_payroll_period(s, month, str(env["cashier_id"]), safe_id=env["safe_id"])
    period_id = ids["period"]
    assert await _set("payroll", period_id, "pay") == {
        ("salaries_payable", D("4750.00"), D("0.00"), ids["a"]), ("salaries_payable", D("3000.00"), D("0.00"), ids["b"]),
        (SAFE, D("0.00"), D("7750.00"), None)}
    bal = await _balances()
    assert bal["salaries_payable"] == D("0.00")  # approved, then paid: nothing owed
    assert bal[SAFE] == D("-8250.00")  # 500 advance + 7750 salaries
    assert await _scalar("SELECT balance FROM safes WHERE id = :id", id=env["safe_id"]) == D("11750.00")


async def test_reopening_an_approved_month_reverses_its_entry_once_and_it_can_be_approved_again():
    from app.activities.general.modules.hr.services import payroll

    env = await _env()
    month = posting.today().strftime("%Y-%m")
    await _payroll(env, month)
    actor = str(env["cashier_id"])
    async with AsyncSessionLocal() as s:
        await payroll.approve_payroll_period(s, month, actor)
    first = await _scalar("SELECT expense_id FROM hr_payroll_periods WHERE month = :m", m=month)
    async with AsyncSessionLocal() as s:
        await payroll.reopen_payroll_period(s, month, actor)
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_id = :id AND event = 'reverse'", id=first) == 1
    assert (await _balances())["salaries_expense"] == D("0.00")
    # The expense cancel and the reversal are one change, not two: no other reversal exists.
    assert await _count("SELECT count(*) FROM acc_entries WHERE event = 'reverse'") == 1

    async with AsyncSessionLocal() as s:  # reviewed and approved again: a new approval, its own entry
        await s.execute(text("UPDATE hr_payroll_periods SET status = 'review' WHERE month = :m"), {"m": month})
        await s.commit()
    async with AsyncSessionLocal() as s:
        await payroll.approve_payroll_period(s, month, actor)
    second = await _scalar("SELECT expense_id FROM hr_payroll_periods WHERE month = :m", m=month)
    assert second != first
    assert (await _balances())["salaries_expense"] == D("8500.00")
    # A paid month can't be reopened.
    async with AsyncSessionLocal() as s:
        await payroll.pay_payroll_period(s, month, actor, safe_id=env["safe_id"])
    async with AsyncSessionLocal() as s:
        with pytest.raises(Exception, match="تم صرفه"):
            await payroll.reopen_payroll_period(s, month, actor)
        await s.rollback()


async def test_clinic_invoice_paid_in_two_parts_posts_revenue_once():
    from app.activities.healthcare.modules.healthcare_clinic import models as clinic
    from app.activities.healthcare.modules.healthcare_clinic import router as clinic_router

    env = await _env()
    tid = env["tenant_id"]
    async with AsyncSessionLocal() as s:
        patient = clinic.ClinicPatient(id=str(uuid.uuid4()), tenant_id=tid, patient_mrn="MRN-1", full_name="مريض",
                                       national_id="1", phone="1", gender="ذكر", date_of_birth="1990-01-01")
        s.add(patient)
        await s.flush()
        inv = clinic.ClinicInvoice(id=str(uuid.uuid4()), tenant_id=tid, invoice_ref="CI-1", patient_id=patient.id,
                                   patient_name="مريض", charges=[{"description": "كشف", "amount": 300}], total=300.0,
                                   insurance_amount=100.0, patient_amount=200.0, paid_amount=0.0, status="pending")
        s.add(inv)
        await s.commit()
        inv_id = inv.id
    for amount in (120.0, 80.0):
        async with AsyncSessionLocal() as s:
            user = await _user(s, env)
            await clinic_router.pay_invoice(inv_id, clinic_router.InvoicePayRequest(amount=amount, payment_method="cash"),
                                            db=s, tenant_id=str(tid), current_user=user, _=user)
    # One revenue entry: the patient's 200 and the insurer's 100.
    assert await _set("clinic_invoice", uuid.UUID(inv_id), "revenue") == {
        ("receivables", D("200.00"), D("0.00"), None), ("insurance_receivables", D("100.00"), D("0.00"), None),
        ("sales", D("0.00"), D("300.00"), None)}
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_type = 'clinic_invoice'") == 1
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_type = 'clinic_payment'") == 2
    pays = await _set("clinic_payment")
    assert pays == {(DRAWER, D("120.00"), D("0.00"), None), ("receivables", D("0.00"), D("120.00"), None),
                    (DRAWER, D("80.00"), D("0.00"), None), ("receivables", D("0.00"), D("80.00"), None)}
    bal = await _balances()
    assert bal["receivables"] == D("0.00") and bal["insurance_receivables"] == D("100.00")
    assert bal[DRAWER] == D("200.00") and bal["sales"] == D("-300.00")
    assert await _count("SELECT count(*) FROM sale_payments") == 2  # one sale, one line per payment


async def test_manager_close_deposits_the_cash_taken_out_into_the_one_safe():
    env = await _env()
    async with AsyncSessionLocal() as s:
        await pos_service.close_shift_with_manager(s, env["shift_id"], SimpleNamespace(
            manager_id=env["cashier_id"], manager_password="Pass123!", closing_balance=D("1000"),
            next_day_drawer=D("300"), notes=None), env["cashier_id"])
    assert await _scalar("SELECT deposit_amount FROM shifts WHERE id = :id", id=env["shift_id"]) == D("700.00")
    assert await _scalar("SELECT balance FROM safes WHERE id = :id", id=env["safe_id"]) == D("1700.00")
    assert await _scalar("SELECT amount FROM safe_deposits WHERE shift_id = :id", id=env["shift_id"]) == D("700.00")
    assert await _set("safe_movement", None, "deposit") == {(SAFE, D("700.00"), D("0.00"), None),
                                                            (DRAWER, D("0.00"), D("700.00"), None)}


async def test_manager_close_leaves_the_deposit_when_the_safe_is_ambiguous():
    env = await _env()
    async with AsyncSessionLocal() as s:
        await bind_tenant(s, env["tenant_id"])
        await s.execute(text("INSERT INTO safes (id, tenant_id, name, balance) VALUES (:id, :t, 'خزنة ثانية', 0)"),
                        {"id": uuid.uuid4(), "t": env["tenant_id"]})
        await s.commit()
    async with AsyncSessionLocal() as s:
        await pos_service.close_shift_with_manager(s, env["shift_id"], SimpleNamespace(
            manager_id=env["cashier_id"], manager_password="Pass123!", closing_balance=D("1000"),
            next_day_drawer=D("300"), notes=None), env["cashier_id"])
    assert await _scalar("SELECT deposit_amount FROM shifts WHERE id = :id", id=env["shift_id"]) == D("700.00")
    assert await _scalar("SELECT balance FROM safes WHERE id = :id", id=env["safe_id"]) == D("1000.00")
    assert await _count("SELECT count(*) FROM acc_entries WHERE source_type = 'safe_movement'") == 0


async def test_a_workspace_without_accounting_posts_nothing_in_step_3():
    from app.activities.general.modules.hr.routes import hr as hr_routes
    from app.activities.general.modules.hr.schemas import AdvanceCreate

    env = await _env(accounting=False)
    po = await _receive(env)
    async with AsyncSessionLocal() as s:
        user = await _user(s, env)
        await purchase_service.record_supplier_transaction(s, env["supplier_id"], D("50"), "credit", user,
                                                           safe_id=env["safe_id"])
        await purchase_service.create_purchase_return(s, po, PurchaseReturnCreate(
            items=[PurchaseReturnItemIn(product_id=env["product_id"], qty=D("2"))]), user)
        await apply_movement(s, product_id=env["product_id"], warehouse_id=env["warehouse_id"],
                             movement_type=MovementType.damage, qty=D("1"), note="تلف")
        ids = await _payroll(env, posting.today().strftime("%Y-%m"))
        await hr_routes.add_advance(AdvanceCreate(employee_id=ids["a"], amount=D("100"), safe_id=env["safe_id"]),
                                    db=s, current_user=user)
        await s.commit()
    # The documents happened (stock, supplier, safe) but no ledger exists.
    assert await _count("SELECT count(*) FROM purchase_returns") == 1
    assert await _count("SELECT count(*) FROM acc_entries") == 0
    assert await _count("SELECT count(*) FROM acc_accounts") == 0
