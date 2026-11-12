"""Inventory: demo data for a new workspace (rows marked is_demo, removable by the owner).

Called by app/framework/demo.py in a fixed order with one random generator, so the same
workspace size gives the same data."""
from decimal import Decimal

from app.modules.general.inventory.models.product import Category, Product, Subcategory
from app.modules.general.inventory.models.stock_balance import StockBalance
from app.modules.general.inventory.models.warehouse import Warehouse

BRANCH_NAMES = ["الفرع الرئيسي", "فرع المعادي", "فرع مدينة نصر", "فرع 6 أكتوبر", "فرع مدينة نصر الجديدة"]


async def seed_warehouses(db, ctx) -> None:
    ctx.warehouses = [
        Warehouse(id=ctx.new_id(), code=f"WH{i+1}", name=BRANCH_NAMES[i % len(BRANCH_NAMES)],
                  warehouse_type="showroom" if i == 0 else "warehouse", is_demo=True)
        for i in range(ctx.n_branches)
    ]
    db.add_all(ctx.warehouses)
    await db.flush()  # FK targets exist before any referencing row


async def seed_catalog(db, ctx) -> None:
    """The activity's catalogue (category -> item names) as products with prices."""
    rng, categories, products = ctx.rng, [], []
    for cat_seq, (cat_name, items) in enumerate(ctx.catalog, start=1):
        cat = Category(id=ctx.new_id(), name=cat_name, code=f"C{cat_seq:02d}", is_demo=True)
        sub = Subcategory(id=ctx.new_id(), category=cat, name=cat_name, code=f"S{cat_seq:02d}", is_demo=True)
        categories.append(cat)
        for j in range(ctx.n_products // len(ctx.catalog) + 1):
            if len(products) >= ctx.n_products:
                break
            item = items[j % len(items)]
            # An item is a name, or (name, retail price) when the activity knows realistic prices.
            base_name, price = (item, None) if isinstance(item, str) else item
            variant = ["", " — جودة أولى", " (عرض خاص)", " — سوق محلي", " — استيراد"][len(products) % 5]
            if price is not None:
                retail = (Decimal(str(price)) * Decimal(str(1 + (len(products) % 5) * 0.05))).quantize(Decimal("0.25"))
                cost = (retail / Decimal("1.25")).quantize(Decimal("0.25"))
            else:
                cost = Decimal(rng.randrange(15, 900))
                retail = (cost * Decimal("1.35")).quantize(Decimal("0.25"))
            products.append(Product(
                id=ctx.new_id(), subcategory_id=sub.id, name=base_name + variant,
                code=f"P{len(products)+1:04d}", barcode=f"62{rng.randrange(10**11, 10**12)}",
                unit=rng.choice(["عدد", "عدد", "عدد", "متر", "كجم"]),
                retail_price=retail, wholesale_price=(retail * Decimal("0.88")).quantize(Decimal("0.25")),
                cost_price=cost, reorder_point=Decimal(rng.randrange(5, 25)),
                is_active=True, is_demo=True,
            ))
    db.add_all(categories)
    db.add_all(products)
    ctx.products = products


async def seed_stock(db, ctx) -> None:
    """Opening stock per branch, with a few low-stock items for the dashboard."""
    rng, balances = ctx.rng, []
    for w in ctx.warehouses:
        for p in ctx.products:
            qty = Decimal(rng.randrange(0, 220))
            if rng.random() < 0.12:
                qty = Decimal(rng.randrange(0, 4))
            balances.append(StockBalance(product_id=p.id, warehouse_id=w.id, qty=qty, is_demo=True))
    db.add_all(balances)
