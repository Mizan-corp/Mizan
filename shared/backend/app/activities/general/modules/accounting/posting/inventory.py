"""Posting rules for stock adjustments and damage (ADR-014 D3, step 3), and opening stock.

Stock adjusted (source 'stock_movement', event 'adjust'), dated today, valued at the movement's
unit cost (the product's average cost when none was given, see inventory stock._movement_cost):
    written off (adjustment out, damage): Dr inventory shortage and damage / Cr inventory
    written up (adjustment in):           Dr inventory / Cr other income
    opening stock entered after the ledger's opening entry: Dr inventory / Cr opening balance equity
    (before it, the opening entry itself takes the stock in at average cost, so nothing is posted)
Not posted here: purchases and sales (posted with their documents), purchase returns (with the
return), transfers between branches (one inventory account).

A stock reset (`stock.resetting`) is refused once any of the warehouse's movements is in the ledger
or the ledger has its opening entry (the stock is then part of the books).
"""
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.posting.common import role, tenant_of
from app.activities.general.modules.accounting.services.posting import active_source, cr, dr, post, today
from app.core.exceptions import ConflictError

KINDS = {"adjustment_in": "زيادة جرد", "adjustment_out": "نقص جرد", "damage": "بضاعة تالفة",
         "opening_stock": "رصيد افتتاحي للمخزون"}
CREDIT_ROLE = {"adjustment_in": "other_income", "opening_stock": "opening_equity"}


async def _opening_in_force(db: AsyncSession, tid) -> bool:
    entry, _ = await active_source(db, tid, "opening", "opening", "opening")
    return entry is not None


async def on_stock_adjusted(db: AsyncSession, *, movement, user_id=None, **_) -> None:
    kind = str(movement.movement_type).split(".")[-1]
    if kind not in KINDS:
        return
    value = (Decimal(str(movement.qty or 0)) * Decimal(str(movement.unit_cost or 0))).quantize(Decimal("0.01"))
    if value <= 0:
        return
    tid = tenant_of(movement)
    if kind == "opening_stock" and not await _opening_in_force(db, tid):
        return
    inventory = await role(db, tid, "inventory")
    inbound = kind in CREDIT_ROLE
    other = await role(db, tid, CREDIT_ROLE.get(kind, "inventory_loss"))
    lines = [dr(inventory, value), cr(other, value)] if inbound else [dr(other, value), cr(inventory, value)]
    await post(db, tid, "stock_movement", movement.id, "adjust", today(), lines,
               memo=f"{KINDS[kind]}" + (f" — {movement.note}" if movement.note else ""),
               warehouse_id=movement.warehouse_id, user_id=user_id or movement.created_by)


async def on_stock_resetting(db: AsyncSession, *, warehouse_id, movement_ids, **_) -> None:
    tid = tenant_of()
    if movement_ids and await db.scalar(text(
            "SELECT 1 FROM acc_entries WHERE tenant_id = :t AND source_type = 'stock_movement' "
            "AND source_id = ANY(:ids) LIMIT 1"), {"t": tid, "ids": list(movement_ids)}):
        raise ConflictError("لا يمكن تصفير مخزون هذا المخزن: بعض حركاته مُرحّلة في الدفاتر — "
                            "استخدم تسوية المخزون لتصحيح الكميات")
    if movement_ids and await _opening_in_force(db, tid):
        raise ConflictError("لا يمكن تصفير مخزون هذا المخزن بعد القيد الافتتاحي للدفاتر — "
                            "استخدم تسوية المخزون لتصحيح الكميات")
