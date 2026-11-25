"""Tenant Storefront & Omnichannel Ordering: business logic.

Functions take the database session and plain values, do one business operation in one
transaction, and raise HTTPException with an Arabic message for the user. Routers and other
modules call these; they never reach into another module's tables.
"""
from __future__ import annotations

from fastapi import HTTPException

# The lifecycle the checkout writes and the order tracker reports. The Website tab's
# orders surface (app/platform/site/orders.py) uses these; it must not invent its own.
ORDER_STATUSES = ("pending", "confirmed", "preparing", "out_for_delivery", "completed", "cancelled")


def apply_order_status_transition(order, new_status: str) -> None:
    """Move a site-origin order along its lifecycle (the domain rule the suspended
    storefront admin router carried inline): any documented status is accepted, and
    completing a cash-on-delivery order settles its payment. The caller owns tenant
    scoping and the transaction."""
    if new_status not in ORDER_STATUSES:
        raise HTTPException(status_code=422, detail="حالة الطلب غير معروفة")
    order.status = new_status
    if new_status == "completed" and order.payment_method == "cod":
        order.payment_status = "paid"
