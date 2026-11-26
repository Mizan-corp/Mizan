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
    """Atomically update stock_balances by delta (can be positive or negative). Never clamped: the
    balance is always the sum of the movements (an out-movement is checked before, see
    _check_available)."""
    await db.execute(text("""
        INSERT INTO stock_balances (product_id, warehouse_id, qty, updated_at)
        VALUES (:pid, :wid, :delta, now())
        ON CONFLICT (product_id, warehouse_id) DO UPDATE SET
            qty = stock_balances.qty + :delta,
            updated_at = now()
    """), {"pid": product_id, "wid": warehouse_id, "delta": delta})


IN_TYPES = ("opening_stock", "purchase", "return_in", "adjustment_in", "transfer_in")
OUT_TYPES = ("sale", "damage", "adjustment_out", "transfer_out", "return_out")


def _qty_text(q) -> str:
    return f"{Decimal(str(q)).normalize():f}"


async def is_untracked(db: AsyncSession, product_id: uuid.UUID) -> bool:
    """A product whose stock isn't tracked (a service, or a product never stocked anywhere): decided
    by the product itself (`products.stock_status`), never by a missing per-warehouse status row."""
    status = await db.scalar(text("SELECT stock_status FROM products WHERE id = :id"), {"id": product_id})
    return status == "untracked"


async def negative_stock_allowed(db: AsyncSession) -> bool:
    """Whether the workspace lets stock go below zero: the inventory setting
    `prevent_negative_stock` (on by default) switched off."""
    from app.framework.loader import registry

    try:
        value = (await registry.get_settings(db, "inventory"))["values"].get("prevent_negative_stock", True)
    except KeyError:
        return False
    return str(value).strip().lower() in ("false", "0", "no", "off")


async def _check_available(db: AsyncSession, product_id, warehouse_id, qty, kind: str, allow_negative: bool) -> None:
    """Before stock leaves: lock the balance row and refuse when it doesn't cover the quantity, unless
    the product is untracked, the caller allows it (a document that decided so) or the workspace
    allows negative stock."""
    if kind in COSTED_OUT_TYPES:
        # Same lock order as a receipt: the product first, then the balance (see _movement_cost).
        await db.execute(text("SELECT 1 FROM products WHERE id = :pid FOR UPDATE"), {"pid": product_id})
    balance = await get_balance(db, product_id, warehouse_id, for_update=True)
    qty = Decimal(str(qty))
    if balance >= qty or allow_negative:
        return
    if await is_untracked(db, product_id) or await negative_stock_allowed(db):
        return
    name = await db.scalar(text("SELECT name FROM products WHERE id = :id"), {"id": product_id}) or ""
    raise BusinessError(f"الرصيد غير كافٍ من «{name}» في هذا المخزن: المتاح {_qty_text(balance)} والمطلوب {_qty_text(qty)}")


def is_inbound(movement_type) -> bool:
    return str(movement_type).split(".")[-1] in IN_TYPES


# Inbound movements whose cost changes the average (ADR-014 D5). A transfer only moves stock between
# branches; the average is kept for the whole workspace.
COSTED_IN_TYPES = ("opening_stock", "purchase", "return_in", "adjustment_in")
# Outbound stock that leaves at the cost it came in at, not at the average: goods sent back to a
# supplier. The average is recalculated without them.
COSTED_OUT_TYPES = ("return_out",)
_AVG_PLACES = Decimal("0.0001")
# Movements that change the stock's value without a document of their own (announced as stock.adjusted).
ADJUSTMENT_TYPES = ("adjustment_in", "adjustment_out", "damage")
# What may be entered by hand (POST /stock/movements, /stock/adjustment/bulk). Opening stock needs its
# own permission; purchases, sales, returns and transfers only come from their documents.
HAND_TYPES = ADJUSTMENT_TYPES
OPENING_TYPE = "opening_stock"


async def _movement_cost(db: AsyncSession, product_id, movement_type, qty, unit_cost) -> Decimal:
    """The cost a movement is recorded at, keeping products.avg_cost (weighted moving average,
    workspace-wide). Inbound stock with a cost moves the average:
    (old qty × old average + qty × cost) ÷ (old qty + qty). Everything else is valued at the
    average at this moment, whatever the caller sent."""
    kind = str(movement_type).split(".")[-1]
    cost = Decimal(str(unit_cost)) if unit_cost is not None else None
    costed = kind in COSTED_IN_TYPES and cost is not None and cost > 0
    costed_out = kind in COSTED_OUT_TYPES and cost is not None and cost > 0
    # Only a costed receipt locks the product (outgoing stock already holds its balance row lock;
    # locking the product too would deadlock against a receipt). A return to a supplier locks the
    # products first, before touching any balance, so it takes locks in the same order as a receipt.
    row = (await db.execute(text("SELECT avg_cost, cost_price FROM products WHERE id = :pid"
                                 + (" FOR UPDATE" if costed or costed_out else "")), {"pid": product_id})).one_or_none()
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
    if costed_out:
        on_hand = Decimal(str((await db.execute(
            text("SELECT COALESCE(SUM(qty), 0) FROM stock_balances WHERE product_id = :pid"), {"pid": product_id}
        )).scalar() or 0))
        left = on_hand - Decimal(str(qty))
        if left > 0 and avg > 0:
            new_avg = max(Decimal("0"), (on_hand * avg - Decimal(str(qty)) * cost) / left)
            await db.execute(text("UPDATE products SET avg_cost = :a WHERE id = :pid"),
                             {"a": new_avg.quantize(_AVG_PLACES), "pid": product_id})
        return cost
    return avg.quantize(Decimal("0.01"))


async def apply_movement(db: AsyncSession, *, product_id, warehouse_id, movement_type, qty, unit_cost=None,
                         unit_price=None, created_by=None, ref_id=None, ref_type=None, sale_id=None,
                         purchase_id=None, note=None, lot: dict | None = None,
                         allow_negative: bool = False) -> tuple[StockMovement, list]:
    """The one way stock changes: the movement, its balance, and the inventory variant's rules
    (batches: a pharmacy receives stock into a batch and takes it out by first expiry, ADR-006
    phase 4). `lot` carries batch details for stock coming in. Returns the movement and the
    batches it was taken from or put into (empty when the workspace doesn't track batches).

    Stock going out is checked first (_check_available): a tracked product can't go below zero
    unless the workspace allows negative stock or the caller passes `allow_negative`. The balance
    is never clamped, so it always equals the sum of the movements.

    The movement's unit_cost is decided here (ADR-014 D5): the given cost for costed inbound
    stock (purchases, opening stock, returns at the sold line's cost, adjustments with a cost),
    the product's average cost for everything else, including every sale."""
    kind = str(movement_type).split(".")[-1]
    if kind in OUT_TYPES:
        await _check_available(db, product_id, warehouse_id, qty, kind, allow_negative)
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
    if kind in ADJUSTMENT_TYPES or kind == OPENING_TYPE:
        # Stock written up or off by hand, or opening stock: modules that follow it (the ledger,
        # ADR-014 D3) post it here (opening stock only once the ledger has its opening entry).
        from app.framework.events import notify

        await notify("stock.adjusted", db, movement=mv, user_id=created_by)
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


async def transfer_stock(db: AsyncSession, data, user) -> dict:
    """Move stock from one warehouse to another: a transfer_out and its transfer_in (the same batches
    arrive, for workspaces that track them), with one reference and an audit entry. The source must
    hold the quantity, whatever the negative-stock setting. Callers check warehouse access and commit."""
    from app.activities.general.modules.inventory.models.warehouse import Warehouse
    from app.core.exceptions import NotFoundError
    from app.platform.audit.service import log as audit_log

    if data.from_warehouse_id == data.to_warehouse_id:
        raise BusinessError("لا يمكن التحويل من المخزن إلى نفسه — اختر مخزناً آخر للوجهة")
    names = {}
    for wid in (data.from_warehouse_id, data.to_warehouse_id):
        w = (await db.execute(select(Warehouse).where(Warehouse.id == wid))).scalar_one_or_none()
        if not w:
            raise NotFoundError("المخزن غير موجود")
        if not w.is_active:
            raise BusinessError(f"المخزن «{w.name}» موقوف")
        names[wid] = w.name
    product = await db.scalar(select(Product.name).where(Product.id == data.product_id))
    if product is None:
        raise NotFoundError("الصنف غير موجود")
    balance = await get_balance(db, data.product_id, data.from_warehouse_id, for_update=True)
    if balance < data.qty:
        raise BusinessError(f"الرصيد غير كافٍ من «{product}» في المخزن «{names[data.from_warehouse_id]}»: "
                            f"المتاح {_qty_text(balance)} والمطلوب {_qty_text(data.qty)}")
    ref_id = uuid.uuid4()
    _, taken = await apply_movement(db, product_id=data.product_id, warehouse_id=data.from_warehouse_id,
                                    movement_type=MovementType.transfer_out, qty=data.qty, note=data.note,
                                    created_by=user.id, ref_id=ref_id, ref_type="transfer")
    for lot in taken or [None]:
        await apply_movement(db, product_id=data.product_id, warehouse_id=data.to_warehouse_id,
                             movement_type=MovementType.transfer_in, qty=lot["qty"] if lot else data.qty,
                             note=data.note, created_by=user.id, ref_id=ref_id, ref_type="transfer", lot=lot)
    await audit_log(db, "stock", "transfer", user.id, user.full_name, ref_id,
                    {"product_id": str(data.product_id), "qty": str(data.qty),
                     "from": str(data.from_warehouse_id), "to": str(data.to_warehouse_id)},
                    f"تحويل {_qty_text(data.qty)} من «{product}» من {names[data.from_warehouse_id]} إلى {names[data.to_warehouse_id]}")
    return {"ref_id": ref_id, "product": product, "qty": data.qty}


async def recompute_avg_cost(db: AsyncSession, product_id: uuid.UUID) -> Decimal:
    """Rebuild products.avg_cost by replaying the product's remaining movements in order, with the same
    rule as _movement_cost (used after movements were removed by a stock reset). A product left with no
    costed receipt gets 0, i.e. it is valued at its listed cost again."""
    rows = (await db.execute(text(
        "SELECT movement_type::text AS kind, qty, unit_cost FROM stock_movements WHERE product_id = :pid "
        "ORDER BY created_at, id"), {"pid": product_id})).all()
    on_hand, avg = Decimal("0"), Decimal("0")
    for r in rows:
        qty, cost = Decimal(str(r.qty or 0)), Decimal(str(r.unit_cost or 0))
        if r.kind in COSTED_IN_TYPES and cost > 0:
            avg = cost if on_hand <= 0 or avg == 0 else (on_hand * avg + qty * cost) / (on_hand + qty)
            on_hand += qty
        elif r.kind in COSTED_OUT_TYPES and cost > 0:
            left = on_hand - qty
            if left > 0 and avg > 0:
                avg = max(Decimal("0"), (on_hand * avg - qty * cost) / left)
            on_hand = left
        else:
            on_hand += qty if r.kind in IN_TYPES else -qty
    avg = avg.quantize(_AVG_PLACES)
    await db.execute(text("UPDATE products SET avg_cost = :a WHERE id = :pid"), {"a": avg, "pid": product_id})
    return avg


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
            # At the average cost the ledger values stock at (ADR-014 D5); the listed cost only for a
            # product that never had a costed receipt.
            func.sum(StockBalance.qty * func.coalesce(func.nullif(Product.avg_cost, 0), Product.cost_price, 0)).label("cost_value"),
            func.sum(StockBalance.qty * Product.retail_price).label("retail_value"),
            func.count(Product.id).label("product_count"),
        )
        .join(StockBalance, Product.id == StockBalance.product_id)
        .where(StockBalance.warehouse_id == warehouse_id, StockBalance.qty > 0)
    )
    return result.one()


async def reorder_alerts_enabled(db: AsyncSession) -> bool:
    """The inventory setting `enable_reorder_alerts` (on by default): whether stock reaching a
    product's reorder level raises a notification (in the app and, where set up, by email)."""
    from app.framework.loader import registry

    try:
        value = (await registry.get_settings(db, "inventory"))["values"].get("enable_reorder_alerts", True)
    except KeyError:
        return True
    return str(value).strip().lower() not in ("false", "0", "no", "off")


async def products_at_reorder_level(db: AsyncSession, limit: int = 50) -> list:
    """Active tracked products whose stock in all warehouses is at or below their reorder level
    (when they have one), lowest stock first: (id, name, qty, level)."""
    return (await db.execute(text("""
        SELECT p.id, p.name, COALESCE(b.qty, 0) AS qty, p.reorder_level AS level
        FROM products p
        LEFT JOIN (SELECT product_id, SUM(qty) AS qty FROM stock_balances GROUP BY product_id) b ON b.product_id = p.id
        WHERE p.is_active AND p.stock_status = 'tracked' AND p.reorder_level > 0
          AND COALESCE(b.qty, 0) <= p.reorder_level
        ORDER BY COALESCE(b.qty, 0), p.name
        LIMIT :lim
    """), {"lim": limit})).all()


async def check_low_stock_and_notify(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    product_ids: list[uuid.UUID],
    warehouse_id: uuid.UUID,
):
    """
    Check stock after sale. If current_qty <= product.reorder_level,
    creates in-app notification for managers and triggers optional email notification.
    Nothing when the workspace switched `enable_reorder_alerts` off (INV-10).
    """
    from datetime import datetime, UTC, timedelta
    from app.platform.notifications.models.notification import Notification

    if not await reorder_alerts_enabled(db):
        return
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

