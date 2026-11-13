"""Warehouses: deactivating one, and resetting its stock. Callers commit."""
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError
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
    """Delete a warehouse's stock movements and balances (a fresh start). Recorded in the audit log."""
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
