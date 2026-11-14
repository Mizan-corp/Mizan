"""Warehouses: deactivating one, and resetting its stock. Callers commit."""
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


async def reset_stock(db: AsyncSession, warehouse_id: uuid.UUID, user) -> int:
    """Delete a warehouse's stock movements and balances (a fresh start while it is being set up).
    Recorded in the audit log. Once stock has been sold, bought or returned there, its movements
    are part of the books (ADR-014 D4) and the reset is refused: correct stock with an adjustment."""
    used = (await db.execute(text(
        "SELECT COUNT(*) FROM stock_movements WHERE warehouse_id = :wid "
        "AND (sale_id IS NOT NULL OR purchase_id IS NOT NULL "
        "OR movement_type IN ('sale', 'purchase', 'return_in'))"
    ), {"wid": warehouse_id})).scalar() or 0
    if used:
        raise ConflictError("لا يمكن تصفير مخزون هذا المخزن بعد تسجيل مبيعات أو مشتريات عليه — "
                            "استخدم تسوية المخزون لتصحيح الكميات")
    count = (await db.execute(text("SELECT COUNT(*) FROM stock_movements WHERE warehouse_id = :wid"), {"wid": warehouse_id})).scalar() or 0
    if count > RESET_LIMIT:
        raise BusinessError(f"لا يمكن إعادة تعيين {count} حركة — تجاوز الحد الأقصى")
    for table in ("stock_movements", "stock_balances", "warehouse_product_status"):
        await db.execute(text(f"DELETE FROM {table} WHERE warehouse_id = :wid"), {"wid": warehouse_id})
    await db.execute(text("""
        UPDATE products SET stock_status = 'untracked'
        WHERE id NOT IN (SELECT DISTINCT product_id FROM stock_movements)
        AND id NOT IN (SELECT DISTINCT product_id FROM warehouse_product_status)
    """))
    await audit_log(db, "warehouse", "reset_stock", user.id, user.full_name, warehouse_id,
                    {"movements_deleted": count}, f"تصفير مخزون المخزن ({count} حركة)")
    return count
