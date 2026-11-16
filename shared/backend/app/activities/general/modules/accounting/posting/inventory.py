"""Posting rules for stock adjustments and damage (ADR-014 D3, step 3).

Stock adjusted (source 'stock_movement', event 'adjust'), dated today, valued at the movement's
unit cost (the product's average cost when none was given, see inventory stock._movement_cost):
    written off (adjustment out, damage): Dr inventory shortage and damage / Cr inventory
    written up (adjustment in):           Dr inventory / Cr other income
Not posted here: opening stock (the opening entry covers it), purchases and sales (posted with their
documents), purchase returns (with the return), transfers between branches (one inventory account).
"""
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.accounting.posting.common import role, tenant_of
from app.activities.general.modules.accounting.services.posting import cr, dr, post, today

KINDS = {"adjustment_in": "زيادة جرد", "adjustment_out": "نقص جرد", "damage": "بضاعة تالفة"}


async def on_stock_adjusted(db: AsyncSession, *, movement, user_id=None, **_) -> None:
    kind = str(movement.movement_type).split(".")[-1]
    if kind not in KINDS:
        return
    value = (Decimal(str(movement.qty or 0)) * Decimal(str(movement.unit_cost or 0))).quantize(Decimal("0.01"))
    if value <= 0:
        return
    tid = tenant_of(movement)
    inventory = await role(db, tid, "inventory")
    other = await role(db, tid, "other_income" if kind == "adjustment_in" else "inventory_loss")
    lines = [dr(inventory, value), cr(other, value)] if kind == "adjustment_in" else [dr(other, value), cr(inventory, value)]
    await post(db, tid, "stock_movement", movement.id, "adjust", today(), lines,
               memo=f"{KINDS[kind]}" + (f" — {movement.note}" if movement.note else ""),
               warehouse_id=movement.warehouse_id, user_id=user_id or movement.created_by)
