"""Warehouses: updating, deactivating and resetting the stock of one. Callers commit."""
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.activities.general.modules.inventory.models.warehouse import Warehouse
from app.platform.audit.service import log as audit_log

RESET_LIMIT = 1000


async def deactivate(db: AsyncSession, warehouse_id: uuid.UUID, user) -> None:
    """A warehouse with movements, sales or shifts can't be removed; otherwise it is deactivated."""
    w = (await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))).scalar_one_or_none()
    if not w:
        raise NotFoundError()
    counts = {}
    for table in ("stock_movements", "sales", "shifts"):
        counts[table] = await db.scalar(text(f"SELECT COUNT(*) FROM {table} WHERE warehouse_id = :id"), {"id": warehouse_id}) or 0
    if sum(counts.values()):
        raise BusinessError(
            f"لا يمكن حذف هذا المخزن — يحتوي على {counts['stock_movements']} حركة مخزون، {counts['sales']} فاتورة بيع، "
            f"و{counts['shifts']} شيفت. يرجى حذف البيانات المرتبطة أولاً."
        )
    w.is_active = False
    await audit_log(db, "warehouse", "deactivate", user.id, user.full_name, warehouse_id, {"name": w.name}, f"تعطيل المخزن {w.name}")


async def ensure_can_deactivate(db: AsyncSession, w: Warehouse) -> None:
    """A warehouse that still holds stock (or has an open shift) can't be stopped: move or adjust the
    stock first. A negative balance counts too."""
    held = await db.scalar(text(
        "SELECT COUNT(*) FROM stock_balances WHERE warehouse_id = :id AND qty <> 0"), {"id": w.id}) or 0
    if held:
        raise ConflictError(f"لا يمكن إيقاف المخزن «{w.name}» وبه رصيد لـ {held} صنف — "
                            "حوّل البضاعة إلى مخزن آخر أو سوِّ الرصيد أولاً")
    shifts = await db.scalar(text(
        "SELECT COUNT(*) FROM shifts WHERE warehouse_id = :id AND status = 'open'"), {"id": w.id}) or 0
    if shifts:
        raise ConflictError(f"لا يمكن إيقاف المخزن «{w.name}» وبه وردية مفتوحة — أغلق الوردية أولاً")


async def update(db: AsyncSession, warehouse_id: uuid.UUID, data, user) -> Warehouse:
    """Rename, recode or (de)activate a warehouse. Codes are unique in the workspace."""
    w = (await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))).scalar_one_or_none()
    if not w:
        raise NotFoundError("المخزن غير موجود")
    changes = data.model_dump(exclude_none=True)
    if "code" in changes and changes["code"] != w.code:
        await ensure_code_free(db, changes["code"], exclude=w.id)
    if changes.get("is_active") is False and w.is_active:
        await ensure_can_deactivate(db, w)
    if changes.get("is_active") is True and not w.is_active and w.tenant_id:
        # Bringing one back counts against the plan's branches like adding one.
        from app.platform.billing.services.plan_gating import check_branch_creation_limit

        await check_branch_creation_limit(db, w.tenant_id)
    for k, v in changes.items():
        setattr(w, k, v)
    await audit_log(db, "warehouse", "update", user.id, user.full_name, w.id,
                    {k: str(v) for k, v in changes.items()}, f"تعديل المخزن {w.name}")
    return w


async def ensure_code_free(db: AsyncSession, code: str, exclude: uuid.UUID | None = None) -> None:
    taken = await db.scalar(select(Warehouse.id).where(Warehouse.code == code, Warehouse.id != exclude)
                            if exclude else select(Warehouse.id).where(Warehouse.code == code))
    if taken:
        raise ConflictError(f"كود المخزن «{code}» مستخدم لمخزن آخر")


# Movements a reset may remove: stock entered by hand while the warehouse is being set up. Anything
# from a document (sales, purchases, returns) or a transfer (its other half is in another warehouse)
# is part of the books (ADR-014 D4).
RESETTABLE_TYPES = ("opening_stock", "adjustment_in", "adjustment_out", "damage")


async def reset_stock(db: AsyncSession, warehouse_id: uuid.UUID, user) -> int:
    """Delete a warehouse's stock movements and balances (a fresh start while it is being set up).
    Allowed only while every movement there was entered by hand (opening stock, adjustments, damage)
    and none is in the ledger: modules that follow stock (accounting) refuse through the
    `stock.resetting` event when one is posted or the books have started. The workspace average cost
    of the products concerned is rebuilt from their remaining movements. Recorded in the audit log."""
    from app.activities.general.modules.inventory.services.stock import recompute_avg_cost
    from app.framework.events import notify

    w = (await db.execute(select(Warehouse).where(Warehouse.id == warehouse_id))).scalar_one_or_none()
    if not w:
        raise NotFoundError("المخزن غير موجود")
    used = (await db.execute(text(
        "SELECT COUNT(*) FROM stock_movements WHERE warehouse_id = :wid "
        "AND (sale_id IS NOT NULL OR purchase_id IS NOT NULL OR movement_type::text <> ALL(:kinds))"
    ), {"wid": warehouse_id, "kinds": list(RESETTABLE_TYPES)})).scalar() or 0
    if used:
        raise ConflictError("لا يمكن تصفير مخزون هذا المخزن بعد تسجيل مبيعات أو مشتريات أو مرتجعات أو تحويلات عليه — "
                            "استخدم تسوية المخزون لتصحيح الكميات")
    count = (await db.execute(text("SELECT COUNT(*) FROM stock_movements WHERE warehouse_id = :wid"), {"wid": warehouse_id})).scalar() or 0
    if count > RESET_LIMIT:
        raise BusinessError(f"لا يمكن إعادة تعيين {count} حركة — تجاوز الحد الأقصى ({RESET_LIMIT})")
    rows = (await db.execute(text(
        "SELECT id, product_id FROM stock_movements WHERE warehouse_id = :wid"), {"wid": warehouse_id})).all()
    await notify("stock.resetting", db, warehouse_id=warehouse_id, movement_ids=[r.id for r in rows], user_id=user.id)
    products = sorted({r.product_id for r in rows}, key=str)
    for table in ("stock_movements", "stock_balances", "warehouse_product_status"):
        await db.execute(text(f"DELETE FROM {table} WHERE warehouse_id = :wid"), {"wid": warehouse_id})
    for pid in products:
        await recompute_avg_cost(db, pid)
    if products:
        await db.execute(text("""
            UPDATE products SET stock_status = 'untracked'
            WHERE id = ANY(:ids)
              AND NOT EXISTS (SELECT 1 FROM stock_movements m WHERE m.product_id = products.id)
              AND NOT EXISTS (SELECT 1 FROM warehouse_product_status s WHERE s.product_id = products.id)
        """), {"ids": products})
    await audit_log(db, "warehouse", "reset_stock", user.id, user.full_name, warehouse_id,
                    {"movements_deleted": count}, f"تصفير مخزون المخزن ({count} حركة)")
    return count
