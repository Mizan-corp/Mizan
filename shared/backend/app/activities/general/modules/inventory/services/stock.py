import uuid
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError
from app.activities.general.modules.inventory.models.product import Product
from app.activities.general.modules.inventory.models.stock import MovementType, StockMovement
from app.activities.general.modules.inventory.models.stock_balance import StockBalance


async def get_balance(db: AsyncSession, product_id: uuid.UUID, warehouse_id: uuid.UUID, for_update: bool = False) -> Decimal:
    """Get current stock balance — O(1) read from maintained stock_balances table."""
    if for_update:
        # Lock the stock_balances row for update (creates row if not exists)
        result = await db.execute(text("""
            INSERT INTO stock_balances (product_id, warehouse_id, qty)
            VALUES (:pid, :wid, 0)
            ON CONFLICT (product_id, warehouse_id) DO NOTHING
            RETURNING qty
        """), {"pid": product_id, "wid": warehouse_id})
        row = result.fetchone()
        if row:
            return row.qty
        # Fallback: row was just created by another transaction
        result = await db.execute(
            select(StockBalance.qty).where(
                StockBalance.product_id == product_id,
                StockBalance.warehouse_id == warehouse_id,
            ).with_for_update()
        )
        return result.scalar_one_or_none() or Decimal("0")
    else:
        # Simple read from maintained table
        result = await db.execute(
            select(StockBalance.qty).where(
                StockBalance.product_id == product_id,
                StockBalance.warehouse_id == warehouse_id,
            )
        )
        return result.scalar_one_or_none() or Decimal("0")


async def _update_stock_balance(db: AsyncSession, product_id: uuid.UUID, warehouse_id: uuid.UUID, delta: Decimal):
    """Atomically update stock_balances by delta (can be positive or negative)."""
    await db.execute(text("""
        INSERT INTO stock_balances (product_id, warehouse_id, qty, updated_at)
        VALUES (:pid, :wid, GREATEST(:delta, 0), now())
        ON CONFLICT (product_id, warehouse_id) DO UPDATE SET
            qty = GREATEST(stock_balances.qty + :delta, 0),
            updated_at = now()
    """), {"pid": product_id, "wid": warehouse_id, "delta": delta})


IN_TYPES = ("opening_stock", "purchase", "return_in", "adjustment_in", "transfer_in")


def is_inbound(movement_type) -> bool:
    return str(movement_type).split(".")[-1] in IN_TYPES


# Inbound movements whose cost changes the average (ADR-014 D5). A transfer only moves stock between
# branches; the average is kept for the whole workspace.
COSTED_IN_TYPES = ("opening_stock", "purchase", "return_in", "adjustment_in")
_AVG_PLACES = Decimal("0.0001")


async def _movement_cost(db: AsyncSession, product_id, movement_type, qty, unit_cost) -> Decimal:
    """The cost a movement is recorded at, keeping products.avg_cost (weighted moving average,
    workspace-wide). Inbound stock with a cost moves the average:
    (old qty × old average + qty × cost) ÷ (old qty + qty). Everything else is valued at the
    average at this moment, whatever the caller sent."""
    kind = str(movement_type).split(".")[-1]
    cost = Decimal(str(unit_cost)) if unit_cost is not None else None
    costed = kind in COSTED_IN_TYPES and cost is not None and cost > 0
    # Only a costed receipt locks the product (outgoing stock already holds its balance row lock;
    # locking the product too would deadlock against a receipt).
    row = (await db.execute(text("SELECT avg_cost, cost_price FROM products WHERE id = :pid"
                                 + (" FOR UPDATE" if costed else "")), {"pid": product_id})).one_or_none()
    if row is None:
        return cost or Decimal("0")
    avg = Decimal(str(row.avg_cost or 0))
    if avg == 0:
        # A product that never had a costed receipt is valued at its listed cost.
        avg = Decimal(str(row.cost_price or 0))
    if costed:
        on_hand = Decimal(str((await db.execute(
            text("SELECT COALESCE(SUM(qty), 0) FROM stock_balances WHERE product_id = :pid"), {"pid": product_id}
        )).scalar() or 0))
        qty = Decimal(str(qty))
        if on_hand <= 0 or avg == 0:
            new_avg = cost
        else:
            new_avg = (on_hand * avg + qty * cost) / (on_hand + qty)
        await db.execute(text("UPDATE products SET avg_cost = :a WHERE id = :pid"),
                         {"a": new_avg.quantize(_AVG_PLACES), "pid": product_id})
        return cost
    return avg.quantize(Decimal("0.01"))


async def apply_movement(db: AsyncSession, *, product_id, warehouse_id, movement_type, qty, unit_cost=None,
                         unit_price=None, created_by=None, ref_id=None, ref_type=None, sale_id=None,
                         purchase_id=None, note=None, lot: dict | None = None) -> tuple[StockMovement, list]:
    """The one way stock changes: the movement, its balance, and the inventory variant's rules
    (batches: a pharmacy receives stock into a batch and takes it out by first expiry, ADR-006
    phase 4). `lot` carries batch details for stock coming in. Returns the movement and the
    batches it was taken from or put into (empty when the workspace doesn't track batches).

    The movement's unit_cost is decided here (ADR-014 D5): the given cost for costed inbound
    stock (purchases, opening stock, returns at the sold line's cost, adjustments with a cost),
    the product's average cost for everything else, including every sale."""
    unit_cost = await _movement_cost(db, product_id, movement_type, qty, unit_cost)
    mv = StockMovement(
        product_id=product_id, warehouse_id=warehouse_id, movement_type=movement_type, qty=qty,
        unit_cost=unit_cost, unit_price=unit_price, note=note, created_by=created_by,
        ref_id=ref_id, ref_type=ref_type, sale_id=sale_id, purchase_id=purchase_id,
    )
    db.add(mv)
    inbound = is_inbound(movement_type)
    await _update_stock_balance(db, product_id, warehouse_id, qty if inbound else -qty)
    if inbound:
        # Mark the product as tracked in this warehouse (and the company view) once stock arrives.
        await db.execute(text("""
            INSERT INTO warehouse_product_status (warehouse_id, product_id, status)
            VALUES (:wid, :pid, 'tracked')
            ON CONFLICT (warehouse_id, product_id) DO UPDATE SET status = 'tracked'
        """), {"wid": warehouse_id, "pid": product_id})
        await db.execute(text("UPDATE products SET stock_status = 'tracked' WHERE id = :pid AND stock_status = 'untracked'"),
                         {"pid": product_id})
    from app.framework.hooks import emit

    await db.flush()
    results = await emit("inventory.after_movement", db, movement=mv, inbound=inbound, lot=lot)
    return mv, (results[0] or []) if results else []


async def record_movement(db: AsyncSession, data, created_by: uuid.UUID, ref_id=None, ref_type=None,
                          sale_id: uuid.UUID = None, purchase_id: uuid.UUID = None) -> StockMovement:
    """Record a stock movement (see apply_movement)."""
    lot = {k: getattr(data, k) for k in ("batch_number", "expiry_date") if getattr(data, k, None)} or None
    mv, _ = await apply_movement(
        db, product_id=data.product_id, warehouse_id=data.warehouse_id, movement_type=data.movement_type,
        qty=data.qty, unit_cost=data.unit_cost, unit_price=data.unit_price, note=data.note, created_by=created_by,
        ref_id=ref_id, ref_type=ref_type, sale_id=sale_id, purchase_id=purchase_id, lot=lot,
    )
    return mv


async def transfer_stock(db: AsyncSession, data, created_by: uuid.UUID):
    """Transfer stock between warehouses — uses maintained balances for validation."""
    balance = await get_balance(db, data.product_id, data.from_warehouse_id, for_update=True)
    if balance < data.qty:
        raise BusinessError(f"Insufficient stock: available {balance}")

    from app.activities.general.modules.inventory.schemas.stock import StockMovementCreate
    out = StockMovementCreate(
        product_id=data.product_id, warehouse_id=data.from_warehouse_id,
        movement_type=MovementType.transfer_out, qty=data.qty, note=data.note,
    )
    in_ = StockMovementCreate(
        product_id=data.product_id, warehouse_id=data.to_warehouse_id,
        movement_type=MovementType.transfer_in, qty=data.qty, note=data.note,
    )
    await record_movement(db, out, created_by)
    await record_movement(db, in_, created_by)
    await db.commit()


async def get_low_stock(db: AsyncSession, warehouse_id: uuid.UUID, threshold: Decimal = Decimal("5")):
    """Get products with stock <= threshold — uses maintained balances for O(1) query."""
    result = await db.execute(
        select(Product, StockBalance.qty)
        .join(StockBalance, Product.id == StockBalance.product_id)
        .where(
            StockBalance.warehouse_id == warehouse_id,
            StockBalance.qty >= 0,
            StockBalance.qty <= threshold,
        )
    )
    return result.all()


async def get_valuation(db: AsyncSession, warehouse_id: uuid.UUID):
    """Get inventory valuation — uses maintained balances for O(n) query (n = products with stock)."""
    result = await db.execute(
        select(
            func.sum(StockBalance.qty * Product.cost_price).label("cost_value"),
            func.sum(StockBalance.qty * Product.retail_price).label("retail_value"),
            func.count(Product.id).label("product_count"),
        )
        .join(StockBalance, Product.id == StockBalance.product_id)
        .where(StockBalance.warehouse_id == warehouse_id, StockBalance.qty > 0)
    )
    return result.one()


async def check_low_stock_and_notify(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    product_ids: list[uuid.UUID],
    warehouse_id: uuid.UUID,
):
    """
    Check stock after sale. If current_qty <= product.reorder_level,
    creates in-app notification for managers and triggers optional email notification.
    """
    from datetime import datetime, UTC, timedelta
    from app.platform.notifications.models.notification import Notification

    cutoff = datetime.now(UTC) - timedelta(hours=4)

    # Fetch products and their balances
    res = await db.execute(
        select(Product, StockBalance.qty)
        .join(StockBalance, Product.id == StockBalance.product_id)
        .where(
            Product.id.in_(product_ids),
            StockBalance.warehouse_id == warehouse_id,
        )
    )
    rows = res.all()

    low_stock_items = []
    for prod, qty in rows:
        reorder_threshold = prod.reorder_level if prod.reorder_level is not None else int(prod.reorder_point or 5)
        if qty <= reorder_threshold:
            low_stock_items.append((prod, qty, reorder_threshold))

    if not low_stock_items:
        return

    # Check if a recent low stock notification exists to avoid spamming
    existing_stmt = select(Notification).where(
        Notification.type == "low_stock",
        Notification.created_at >= cutoff,
    )
    if tenant_id:
        existing_stmt = existing_stmt.where(Notification.tenant_id == tenant_id)
    if (await db.execute(existing_stmt)).scalar_one_or_none():
        return

    sample_str = "، ".join([f"{p.name} (رصيد: {q})" for p, q, _ in low_stock_items[:3]])
    notif = Notification(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        type="low_stock",
        severity="warning",
        title="تنبيه: انخفاض المخزون عن حد إعادة الطلب",
        body=f"وصلت {len(low_stock_items)} منتجات للحد الأدنى لإعادة الطلب: {sample_str}. يُرجى مراجعة المخزون وتوريد كميات جديدة.",
        link="/inventory",
        data_json={"count": len(low_stock_items), "items": [str(p.id) for p, _, _ in low_stock_items]},
        is_read=False,
    )
    db.add(notif)
    await db.commit()

    # Optional email notification (behind feature flag)
    try:
        from app.platform.notifications.service import send_low_stock_email_alert
        await send_low_stock_email_alert(db, tenant_id, low_stock_items)
    except Exception:
        pass

