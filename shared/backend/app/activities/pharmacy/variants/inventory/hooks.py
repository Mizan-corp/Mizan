"""Inventory, pharmacy variant: stock is kept in batches with expiry dates (uses `batches`).

after_movement runs for every stock movement of a workspace whose inventory runs this variant:
stock coming in goes into its batch (batch number and expiry required when receiving), stock
going out is taken first-expiry-first-out, and expired or quarantined batches are never sold.
"""
from app.framework import variants


async def after_movement(db, activity_id=None, movement=None, inbound=False, lot=None, **_):
    from app.activities.pharmacy.modules.batches import service

    if inbound:
        required = bool(variants.setting("inventory", "batches_required", activity_id, False))
        return await service.receive(db, movement, lot, required)
    return await service.take(db, movement, lot)
