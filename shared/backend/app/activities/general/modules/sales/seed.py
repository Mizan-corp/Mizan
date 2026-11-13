"""Sales: demo data for a new workspace (rows marked is_demo, removable by the owner).

Called by app/framework/demo.py in a fixed order with one random generator, so the same
workspace size gives the same data."""
from datetime import timedelta
from decimal import Decimal

from app.activities.general.modules.sales.models.sale import Sale, SaleItem, SaleMode, SaleStatus
from app.activities.general.modules.sales.models.sale_payment import SalePayment


async def seed(db, ctx) -> None:
    """Two weeks of sales: cash-heavy, some on credit, a few cancelled."""
    rng, sales, payments = ctx.rng, [], []
    for k in range(ctx.n_sales):
        days_ago = rng.randrange(0, 14)
        ts = ctx.now - timedelta(days=days_ago, hours=rng.randrange(1, 12))
        w = rng.choice(ctx.warehouses)
        cust = None if rng.random() < 0.55 else rng.choice(ctx.customers)
        is_credit = bool(cust and not cust.is_cash and rng.random() < 0.3)
        picked = rng.sample(ctx.products, rng.randrange(1, 4))
        total = Decimal("0")
        sale = Sale(
            id=ctx.new_id(), invoice_number=f"INV-{100000 + k + 1}",
            customer_id=cust.id if cust else None, warehouse_id=w.id, cashier_id=ctx.owner_id,
            created_by=ctx.owner_id, sale_mode=SaleMode.wholesale if (cust and rng.random() < 0.4) else SaleMode.retail,
            status=SaleStatus.cancelled if rng.random() < 0.05 else SaleStatus.confirmed,
            is_credit=is_credit, payment_method="credit" if is_credit else "cash",
            created_at=ts, is_demo=True,
        )
        for p in picked:
            qty = Decimal(rng.randrange(1, 6))
            total += p.retail_price * qty
            sale.items.append(SaleItem(id=ctx.new_id(), product_id=p.id, qty=qty, unit_price=p.retail_price,
                                       unit_cost=p.cost_price, discount=Decimal("0"), is_demo=True))
        sale.total = sale.net_total = total
        sale.paid_amount = Decimal("0") if is_credit else total
        if not is_credit:
            payments.append(SalePayment(id=ctx.new_id(), sale_id=sale.id, method="cash", amount=total, created_at=ts, is_demo=True))
        sales.append(sale)
    db.add_all(sales)
    db.add_all(payments)
    await db.flush()
