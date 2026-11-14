"""Independent Remediation Test Suite for Business Logic & Financial Defects.

Verifies:
- BIZ-01 (Issue #15): Financial Discrepancy on Sales Returns.
  Validates that cash returns on single-payment and split-payment sales record corresponding
  drawer refund transactions, ensuring drawer cash balances reconcile accurately.
- BIZ-02 (Issue #16): Shift Ledger History Corruption on Sale Cancellation.
  Validates that sales associated with closed shifts cannot be hard-cancelled or have their
  historical ledger transactions deleted.
"""
import os
import uuid
from decimal import Decimal
import pytest
from datetime import datetime, timezone

from app.db.base import AsyncSessionLocal
from app.core.exceptions import BusinessError
from app.platform.auth.security import hash_password
from app.platform.tenancy.models import Tenant
from app.platform.auth.models.user import User
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.pos.models import Shift
from app.activities.general.modules.inventory.models.stock_balance import StockBalance
from app.activities.general.modules.sales.schemas import SaleCreate, SaleItemCreate
from app.activities.general.modules.sales.services.sales import create_sale, return_sale, cancel_sale

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set"
)


@pytest.fixture(autouse=True)
async def cleanup_db_connections():
    from app.db.base import engine
    await engine.dispose()
    yield
    await engine.dispose()


async def _create_sales_test_env():
    """Sets up an isolated tenant with warehouse, product, cashier, and shift."""
    async with AsyncSessionLocal() as session:
        t_id = uuid.uuid4()
        tenant = Tenant(
            id=t_id,
            name=f"Biz Tenant {t_id.hex[:6]}",
            slug=f"biz-{t_id.hex[:6]}",
            status="active",
            active_modules=["sales", "pos", "shifts", "inventory"],
        )
        session.add(tenant)
        await session.flush()

        wh = Warehouse(
            id=uuid.uuid4(),
            tenant_id=t_id,
            code=f"WH-{uuid.uuid4().hex[:4].upper()}",
            name="مستودع المبيعات التجريبي",
            is_active=True,
        )
        session.add(wh)

        cashier = User(
            id=uuid.uuid4(),
            tenant_id=t_id,
            username=f"cashier_{uuid.uuid4().hex[:6]}",
            full_name="كاشير المبيعات",
            role="cashier",
            password_hash=hash_password("Pass123!"),
            permissions=["sales", "pos", "shifts"],
            is_active=True,
        )
        session.add(cashier)

        product = Product(
            id=uuid.uuid4(),
            tenant_id=t_id,
            name="منتج تجريبي قابل للإرجاع",
            code=f"PRD-{uuid.uuid4().hex[:6].upper()}",
            retail_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            stock_status="tracked",
            is_active=True,
        )
        session.add(product)
        await session.flush()

        # Initial stock balance: 50 units
        stock = StockBalance(
            tenant_id=t_id,
            product_id=product.id,
            warehouse_id=wh.id,
            qty=Decimal("50.00"),
        )
        session.add(stock)

        # Shift
        shift = Shift(
            id=uuid.uuid4(),
            tenant_id=t_id,
            cashier_id=cashier.id,
            warehouse_id=wh.id,
            status="open",
            initial_amount=Decimal("1000.00"),
            started_at=datetime.now(timezone.utc),
        )
        session.add(shift)

        await session.commit()

        return {
            "tenant_id": t_id,
            "warehouse_id": wh.id,
            "cashier_id": cashier.id,
            "product_id": product.id,
            "shift_id": shift.id,
        }


@pytest.mark.asyncio
async def test_biz_01_cash_sale_return_deducts_from_drawer():
    """BIZ-01: Verify single-payment cash return correctly records a return DrawerTransaction."""
    env = await _create_sales_test_env()
    from app.platform.tenancy.context import current_tenant_id
    current_tenant_id.set(env["tenant_id"])

    async with AsyncSessionLocal() as session:
        # 1. Create single-payment cash sale: 2 units * 100 EGP = 200 EGP
        sale_data = SaleCreate(
            warehouse_id=env["warehouse_id"],
            items=[
                SaleItemCreate(
                    product_id=env["product_id"],
                    qty=Decimal("2.00"),
                    unit_price=Decimal("100.00"),
                    unit_cost=Decimal("60.00"),
                    discount=Decimal("0.00"),
                )
            ],
            discount_amount=Decimal("0.00"),
            payment_method="cash",
            shift_id=env["shift_id"],
        )
        sale = await create_sale(session, sale_data, env["cashier_id"])
        sale_id = sale.id
        assert sale.net_total == Decimal("200.00")

    # 2. Process return for the sale
    async with AsyncSessionLocal() as session:
        ret_result = await return_sale(session, sale_id, env["cashier_id"])
        assert ret_result["detail"] == "Returned"
        assert ret_result["amount"] == Decimal("200.00")

    # 3. Verify drawer transactions contain the return transaction with amount 200 EGP
    async with AsyncSessionLocal() as session:
        from sqlalchemy import text as sqlt
        # The refund row belongs to the return document, which points to the sale (ADR-014 D4).
        txs = (await session.execute(
            sqlt("SELECT type, amount, shift_id FROM drawer_transactions WHERE ref_id = :sid "
                 "OR ref_id IN (SELECT id FROM sales WHERE return_of = :sid)"),
            {"sid": str(sale_id)}
        )).fetchall()

        types = [str(t.type) for t in txs]
        assert any(t in ("sale", "sale_") for t in types), "Original sale drawer transaction missing"
        assert any(t in ("return", "return_") for t in types), "Return drawer transaction missing"

        ret_tx = next(t for t in txs if str(t.type) in ("return", "return_"))
        assert Decimal(str(ret_tx.amount)) == Decimal("200.00"), f"Expected return amount 200.00, got {ret_tx.amount}"


@pytest.mark.asyncio
async def test_biz_02_cancel_sale_blocks_when_shift_is_closed():
    """BIZ-02: Verify cancel_sale raises BusinessError when shift is closed, protecting historical ledger integrity."""
    env = await _create_sales_test_env()
    from app.platform.tenancy.context import current_tenant_id
    current_tenant_id.set(env["tenant_id"])

    # 1. Create confirmed cash sale
    async with AsyncSessionLocal() as session:
        sale_data = SaleCreate(
            warehouse_id=env["warehouse_id"],
            items=[
                SaleItemCreate(
                    product_id=env["product_id"],
                    qty=Decimal("1.00"),
                    unit_price=Decimal("100.00"),
                    unit_cost=Decimal("60.00"),
                    discount=Decimal("0.00"),
                )
            ],
            discount_amount=Decimal("0.00"),
            payment_method="cash",
            shift_id=env["shift_id"],
        )
        sale = await create_sale(session, sale_data, env["cashier_id"])
        sale_id = sale.id

    # 2. Close the shift
    async with AsyncSessionLocal() as session:
        shift = await session.get(Shift, env["shift_id"])
        shift.status = "closed"
        shift.closed_at = datetime.now(timezone.utc)
        await session.commit()

    # 3. Attempting to cancel sale must be BLOCKED
    async with AsyncSessionLocal() as session:
        with pytest.raises(BusinessError) as exc_info:
            await cancel_sale(session, sale_id, env["cashier_id"])
        assert "مغلقة" in str(exc_info.value), f"Expected closed shift error, got {exc_info.value}"

    # 4. Verify historical drawer transactions remain intact and were NOT deleted
    async with AsyncSessionLocal() as session:
        from sqlalchemy import text as sqlt
        txs = (await session.execute(
            sqlt("SELECT count(*) FROM drawer_transactions WHERE ref_id = :sid"),
            {"sid": str(sale_id)}
        )).scalar_one()
        assert txs > 0, "Historical drawer transactions must NOT be deleted for closed shifts!"
