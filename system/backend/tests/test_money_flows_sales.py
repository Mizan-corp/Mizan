"""Money flows in sales, POS and stock (ADR-014 D4 and D5).

- Returns are their own documents (`return_of`), with real totals; the sale stays confirmed.
- Cancelling a sale keeps its payment rows and reverses cash, wallet and credit.
- Confirmed sales can't be edited (409).
- Drawer rows are cancelled, not deleted, and the shift summary skips them.
- The cost of a sale line comes from the product's weighted average cost, kept by apply_movement.
- The automatic close of a stale shift uses the same expected cash as a cashier's close.
"""
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.activities.general.modules.contacts.models.party import Customer
from app.activities.general.modules.finance.models.payment_wallet import PaymentWallet
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.services.stock import apply_movement
from app.activities.general.modules.pos import service as pos_service
from app.activities.general.modules.pos.models import DrawerTxType, Shift
from app.activities.general.modules.sales.schemas import SaleCreate, SaleItemCreate, SaleItemUpdate, SplitPaymentItem
from app.activities.general.modules.sales.services import sales as sales_service
from app.core.exceptions import ConflictError
from app.db.base import AsyncSessionLocal
from app.platform.auth.models.user import User
from app.platform.auth.security import hash_password
from app.platform.tenancy.context import current_tenant_id, install_tenancy_events
from app.platform.tenancy.models import Tenant
from app.models.registry import load_all_models

load_all_models()
install_tenancy_events()  # new rows get the workspace, and SQL runs under RLS, as in the app

pytestmark = pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def _env(stock: Decimal = Decimal("50"), cost: Decimal = Decimal("60")) -> dict:
    """A workspace with a branch, a cashier with an open shift (1000 in the drawer), a customer, a
    wallet, and one product with `stock` units received at `cost`."""
    t_id = uuid.uuid4()
    current_tenant_id.set(None)
    async with AsyncSessionLocal() as s:
        s.add(Tenant(id=t_id, name=f"Money {t_id.hex[:6]}", slug=f"money-{t_id.hex[:6]}", status="active",
                     active_modules=["sales", "pos", "shifts", "inventory", "finance", "contacts"]))
        await s.flush()
        wh = Warehouse(id=uuid.uuid4(), tenant_id=t_id, code=f"WH-{t_id.hex[:4]}", name="الفرع", is_active=True)
        cashier = User(id=uuid.uuid4(), tenant_id=t_id, username=f"cash_{t_id.hex[:6]}", full_name="كاشير",
                       role="cashier", password_hash=hash_password("Pass123!"),
                       permissions=["sales", "pos", "shifts"], is_active=True)
        product = Product(id=uuid.uuid4(), tenant_id=t_id, name="صنف", code=f"P-{t_id.hex[:6]}",
                          retail_price=Decimal("100"), cost_price=cost, stock_status="tracked", is_active=True)
        customer = Customer(id=uuid.uuid4(), tenant_id=t_id, name="عميل آجل", balance=Decimal("0"))
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
        if stock:
            await apply_movement(s, product_id=product.id, warehouse_id=wh.id, movement_type=MovementType.opening_stock,
                                 qty=stock, unit_cost=cost, created_by=cashier.id)
        await s.commit()
    return {"tenant_id": t_id, "warehouse_id": wh.id, "cashier_id": cashier.id, "product_id": product.id,
            "shift_id": shift.id, "customer_id": customer.id, "wallet_id": wallet.id}


def _sale(env, qty="2", price="100", discount="0", invoice_discount="0", **kw) -> SaleCreate:
    return SaleCreate(
        warehouse_id=env["warehouse_id"], shift_id=env["shift_id"],
        items=[SaleItemCreate(product_id=env["product_id"], qty=Decimal(qty), unit_price=Decimal(price),
                              discount=Decimal(discount))],
        discount_amount=Decimal(invoice_discount), **kw)


async def _one(sql: str, **params):
    async with AsyncSessionLocal() as s:
        return (await s.execute(text(sql), params)).one()


async def _all(sql: str, **params):
    async with AsyncSessionLocal() as s:
        return (await s.execute(text(sql), params)).all()


async def _expected_cash(shift_id) -> Decimal:
    async with AsyncSessionLocal() as s:
        return (await pos_service.compute_summary(s, shift_id))["expected_balance"]


@pytest.mark.asyncio
async def test_full_return_is_a_linked_document_and_the_sale_stays_confirmed():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, qty="2"), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        out = await sales_service.return_sale(s, sale.id, env["cashier_id"])
    assert out["amount"] == Decimal("200.00")

    orig = await _one("SELECT status, returns_total FROM sales WHERE id = :id", id=sale.id)
    assert orig.status == "confirmed"
    assert orig.returns_total == Decimal("200.00")
    ret = await _one("SELECT id, status, invoice_number, total, net_total, return_of FROM sales WHERE return_of = :id",
                     id=sale.id)
    assert ret.status == "returned" and ret.invoice_number.startswith("RET-")
    assert ret.total == Decimal("200.00") and ret.net_total == Decimal("200.00")
    line = await _one("SELECT qty, unit_cost FROM sale_items WHERE sale_id = :id", id=ret.id)
    assert line.qty == Decimal("2") and line.unit_cost == Decimal("60.00")
    # The cash refund leaves the drawer: 1000 + 200 sold - 200 refunded.
    assert await _expected_cash(env["shift_id"]) == Decimal("1000.00")
    stock = await _one("SELECT qty FROM stock_balances WHERE product_id = :p", p=env["product_id"])
    assert stock.qty == Decimal("50")
    # The sale screen shows the return and what came back; the return names its sale.
    from app.activities.general.modules.sales.routes.sales import get_sale
    async with AsyncSessionLocal() as s:
        shown = await get_sale(sale.id, s, None)
        shown_ret = await get_sale(ret.id, s, None)
    assert [r["invoice_number"] for r in shown["returns"]] == [ret.invoice_number]
    assert shown["items"][0]["returned_qty"] == 2.0 and shown["remaining"] == 0
    assert shown_ret["return_of_number"] == sale.invoice_number
    # Nothing is left to return.
    async with AsyncSessionLocal() as s:
        with pytest.raises(Exception):
            await sales_service.return_sale(s, sale.id, env["cashier_id"])


@pytest.mark.asyncio
async def test_partial_returns_have_real_net_totals_and_the_last_one_refunds_the_rest():
    env = await _env()
    # 3 × 100, invoice discount 30 → net 270 (90 a unit after the discount).
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, qty="3", invoice_discount="30"), env["cashier_id"])
    assert sale.net_total == Decimal("270.00")
    async with AsyncSessionLocal() as s:
        out = await sales_service.partial_return_sale(
            s, sale.id, {"items": [{"product_id": env["product_id"], "qty": 1}]}, env["cashier_id"])
    assert out["total"] == 90.0
    ret = await _one("SELECT total, discount_amount, net_total, return_of FROM sales WHERE id = :id", id=out["sale_id"])
    assert ret.return_of == sale.id
    assert (ret.total, ret.discount_amount, ret.net_total) == (Decimal("100.00"), Decimal("10.00"), Decimal("90.00"))

    # More than what is left is refused.
    async with AsyncSessionLocal() as s:
        with pytest.raises(Exception) as err:
            await sales_service.partial_return_sale(
                s, sale.id, {"items": [{"product_id": env["product_id"], "qty": 3}]}, env["cashier_id"])
    assert "تتجاوز" in str(err.value.detail)

    async with AsyncSessionLocal() as s:
        last = await sales_service.return_sale(s, sale.id, env["cashier_id"])
    assert last["amount"] == Decimal("180.00")
    orig = await _one("SELECT status, returns_total FROM sales WHERE id = :id", id=sale.id)
    assert orig.status == "confirmed" and orig.returns_total == Decimal("270.00")
    refunds = await _all("SELECT sp.method, sp.amount FROM sale_payments sp JOIN sales r ON r.id = sp.sale_id "
                         "WHERE r.return_of = :id", id=sale.id)
    assert sum(r.amount for r in refunds) == Decimal("270.00")
    assert await _expected_cash(env["shift_id"]) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_cancel_keeps_payment_rows_and_reverses_cash_wallet_and_credit():
    env = await _env()
    # Split: 50 cash, 100 wallet, 50 on the customer's account.
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(
            env, qty="2", customer_id=env["customer_id"],
            payments=[SplitPaymentItem(method="cash", amount=Decimal("50")),
                      SplitPaymentItem(method="wallet", amount=Decimal("100"), wallet_id=env["wallet_id"]),
                      SplitPaymentItem(method="credit", amount=Decimal("50"))]), env["cashier_id"])
    assert (await _one("SELECT balance FROM payment_wallets WHERE id = :id", id=env["wallet_id"])).balance == Decimal("100.00")
    assert (await _one("SELECT balance FROM customers WHERE id = :id", id=env["customer_id"])).balance == Decimal("50.00")
    assert await _expected_cash(env["shift_id"]) == Decimal("1050.00")

    async with AsyncSessionLocal() as s:
        await sales_service.cancel_sale(s, sale.id, env["cashier_id"])

    assert (await _one("SELECT status FROM sales WHERE id = :id", id=sale.id)).status == "cancelled"
    rows = await _all("SELECT method, amount FROM sale_payments WHERE sale_id = :id", id=sale.id)
    assert sorted((r.method, r.amount) for r in rows) == [
        ("cash", Decimal("50.00")), ("credit", Decimal("50.00")), ("wallet", Decimal("100.00"))]
    drawer = await _all("SELECT amount, cancelled_at FROM drawer_transactions WHERE ref_id = :id", id=sale.id)
    assert len(drawer) == 1 and drawer[0].cancelled_at is not None
    assert await _expected_cash(env["shift_id"]) == Decimal("1000.00")
    assert (await _one("SELECT balance FROM payment_wallets WHERE id = :id", id=env["wallet_id"])).balance == Decimal("0.00")
    assert (await _one("SELECT balance FROM customers WHERE id = :id", id=env["customer_id"])).balance == Decimal("0.00")
    assert (await _one("SELECT qty FROM stock_balances WHERE product_id = :p", p=env["product_id"])).qty == Decimal("50")


@pytest.mark.asyncio
async def test_cancelling_a_single_wallet_sale_restores_the_wallet():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(
            s, _sale(env, qty="1", payment_method="wallet", wallet_id=env["wallet_id"]), env["cashier_id"])
    assert (await _one("SELECT balance FROM payment_wallets WHERE id = :id", id=env["wallet_id"])).balance == Decimal("100.00")
    async with AsyncSessionLocal() as s:
        await sales_service.cancel_sale(s, sale.id, env["cashier_id"])
    assert (await _one("SELECT balance FROM payment_wallets WHERE id = :id", id=env["wallet_id"])).balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_confirmed_sale_items_cannot_be_edited():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, qty="2"), env["cashier_id"])
    item_id = sale.items[0].id
    async with AsyncSessionLocal() as s:
        with pytest.raises(ConflictError) as err:
            await sales_service.update_sale_item_qty(s, sale.id, item_id, SaleItemUpdate(qty=Decimal("1")),
                                                     env["cashier_id"], "كاشير")
    assert err.value.status_code == 409 and "المرتجع" in err.value.detail
    async with AsyncSessionLocal() as s:
        with pytest.raises(ConflictError):
            await sales_service.delete_sale_item(s, sale.id, item_id, env["cashier_id"])
    line = await _one("SELECT qty FROM sale_items WHERE id = :id", id=item_id)
    assert line.qty == Decimal("2")


@pytest.mark.asyncio
async def test_cancelled_drawer_row_is_kept_reversed_and_left_out_of_the_summary():
    env = await _env()
    async with AsyncSessionLocal() as s:
        dt = await pos_service.add_transaction(s, env["shift_id"], DrawerTxType.deposit, Decimal("40"),
                                               env["cashier_id"], note="سداد", customer_id=env["customer_id"])
    async with AsyncSessionLocal() as s:
        await s.execute(text("UPDATE customers SET balance = 100 WHERE id = :id"), {"id": env["customer_id"]})
        await s.commit()
    assert await _expected_cash(env["shift_id"]) == Decimal("1040.00")

    async with AsyncSessionLocal() as s:
        await pos_service.delete_drawer_transaction(s, dt.id, env["cashier_id"])

    row = await _one("SELECT cancelled_at, cancelled_by FROM drawer_transactions WHERE id = :id", id=dt.id)
    assert row.cancelled_at is not None and row.cancelled_by == env["cashier_id"]
    async with AsyncSessionLocal() as s:
        summary = await pos_service.compute_summary(s, env["shift_id"])
    assert summary["expected_balance"] == Decimal("1000.00")
    assert summary["deposits_total"] == Decimal("0") and summary["transaction_count"] == 0
    # The receipt is reversed by a negative receipt, and the debt comes back.
    payments = await _all("SELECT amount FROM customer_payments WHERE customer_id = :id", id=env["customer_id"])
    assert sorted(p.amount for p in payments) == [Decimal("-40.00"), Decimal("40.00")]
    assert (await _one("SELECT balance FROM customers WHERE id = :id", id=env["customer_id"])).balance == Decimal("140.00")
    async with AsyncSessionLocal() as s:
        with pytest.raises(Exception):
            await pos_service.delete_drawer_transaction(s, dt.id, env["cashier_id"])


@pytest.mark.asyncio
async def test_pos_sale_line_cost_is_the_average_cost_not_the_clients():
    env = await _env(stock=Decimal("10"), cost=Decimal("60"))
    data = _sale(env, qty="1")
    data.items[0].unit_cost = Decimal("999")  # ignored
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, data, env["cashier_id"])
    assert sale.items[0].unit_cost == Decimal("60.00")
    mv = await _one("SELECT unit_cost FROM stock_movements WHERE sale_id = :id", id=sale.id)
    assert mv.unit_cost == Decimal("60.00")


@pytest.mark.asyncio
async def test_average_cost_moves_with_each_costed_receipt():
    env = await _env(stock=Decimal("10"), cost=Decimal("60"))
    async with AsyncSessionLocal() as s:
        await apply_movement(s, product_id=env["product_id"], warehouse_id=env["warehouse_id"],
                             movement_type=MovementType.purchase, qty=Decimal("30"), unit_cost=Decimal("80"),
                             created_by=env["cashier_id"])
        # A transfer or an adjustment without a cost doesn't move the average.
        await apply_movement(s, product_id=env["product_id"], warehouse_id=env["warehouse_id"],
                             movement_type=MovementType.adjustment_in, qty=Decimal("5"), created_by=env["cashier_id"])
        await s.commit()
    p = await _one("SELECT avg_cost, cost_price FROM products WHERE id = :id", id=env["product_id"])
    # (10 × 60 + 30 × 80) ÷ 40 = 75; cost_price (last purchase price) is not touched here.
    assert p.avg_cost == Decimal("75.0000")
    assert p.cost_price == Decimal("60.00")
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, qty="1"), env["cashier_id"])
    assert sale.items[0].unit_cost == Decimal("75.00")


@pytest.mark.asyncio
async def test_confirming_a_draft_records_its_payment():
    env = await _env()
    async with AsyncSessionLocal() as s:
        draft = await sales_service.create_draft_sale(s, _sale(env, qty="1"), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        sale = await sales_service.confirm_draft_sale(s, draft.id, env["cashier_id"])
    assert sale.paid_amount == Decimal("100.00")
    rows = await _all("SELECT method, amount FROM sale_payments WHERE sale_id = :id", id=draft.id)
    assert [(r.method, r.amount) for r in rows] == [("cash", Decimal("100.00"))]
    assert await _expected_cash(env["shift_id"]) == Decimal("1100.00")
    assert (await _one("SELECT unit_cost FROM sale_items WHERE sale_id = :id", id=draft.id)).unit_cost == Decimal("60.00")


@pytest.mark.asyncio
async def test_bank_payment_is_recorded_but_not_put_in_the_drawer():
    env = await _env()
    async with AsyncSessionLocal() as s:
        sale = await sales_service.create_sale(s, _sale(env, qty="1", payment_method="bank"), env["cashier_id"])
    rows = await _all("SELECT method, amount FROM sale_payments WHERE sale_id = :id", id=sale.id)
    assert [(r.method, r.amount) for r in rows] == [("bank", Decimal("100.00"))]
    assert await _expected_cash(env["shift_id"]) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_confirming_a_quotation_on_credit_puts_it_on_the_customer():
    env = await _env()
    async with AsyncSessionLocal() as s:
        q = await sales_service.create_quotation(s, _sale(env, qty="2", customer_id=env["customer_id"]), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        sale = await sales_service.confirm_quotation(s, q.id, env["cashier_id"], destination="credit")
    assert sale.status == "confirmed" and sale.is_credit and sale.paid_amount == Decimal("0")
    assert (await _one("SELECT balance FROM customers WHERE id = :id", id=env["customer_id"])).balance == Decimal("200.00")
    async with AsyncSessionLocal() as s:
        await sales_service.cancel_sale(s, q.id, env["cashier_id"])
    assert (await _one("SELECT balance FROM customers WHERE id = :id", id=env["customer_id"])).balance == Decimal("0.00")


@pytest.mark.asyncio
async def test_reset_stock_is_refused_once_the_branch_has_sold():
    from app.activities.general.modules.inventory.services.warehouses import reset_stock

    env = await _env()
    async with AsyncSessionLocal() as s:
        await sales_service.create_sale(s, _sale(env, qty="1"), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        user = await s.get(User, env["cashier_id"])
        with pytest.raises(ConflictError):
            await reset_stock(s, env["warehouse_id"], user)
    count = await _one("SELECT COUNT(*) AS n FROM stock_movements WHERE warehouse_id = :w", w=env["warehouse_id"])
    assert count.n == 2


@pytest.mark.asyncio
async def test_auto_close_uses_the_expected_cash():
    from app.platform.automation_worker.runner import auto_close_stale_shifts

    env = await _env()
    async with AsyncSessionLocal() as s:
        await sales_service.create_sale(s, _sale(env, qty="1"), env["cashier_id"])  # cash 100
        await sales_service.create_sale(
            s, _sale(env, qty="2", customer_id=env["customer_id"], is_credit=True, payment_method="credit"),
            env["cashier_id"])  # credit 200: no cash
    async with AsyncSessionLocal() as s:
        await pos_service.add_transaction(s, env["shift_id"], DrawerTxType.expense, Decimal("30"), env["cashier_id"])
    async with AsyncSessionLocal() as s:
        await s.execute(text("UPDATE shifts SET started_at = :t WHERE id = :id"),
                        {"t": datetime.now(UTC) - timedelta(hours=30), "id": env["shift_id"]})
        await s.commit()
    # Bound to this workspace (row-level security), so only its shifts are closed.
    async with AsyncSessionLocal() as s:
        out = await auto_close_stale_shifts(s)
    assert out["items_processed"] == 1
    shift = await _one("SELECT status, closing_balance, expected_balance, difference FROM shifts WHERE id = :id",
                       id=env["shift_id"])
    assert shift.status == "closed"
    assert shift.expected_balance == Decimal("1070.00")  # 1000 + 100 cash - 30 expense
    assert shift.closing_balance == Decimal("1070.00") and shift.difference == Decimal("0.00")
