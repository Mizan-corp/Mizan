"""Website orders: the Website tab's admin surface for site-origin orders.

The Website module is the rebuild of the suspended storefront module (user decision
2026-11-25 17:33: orders placed on the site are managed from the Website tab). The
records stay in the storefront module's models.py - StorefrontOrder is the only
website-orders record (Sales' Sale carries no website-origin field). The storefront
module's public commerce routes stay suspended; this is the authenticated back-office
surface only, every route guarded by site.manage and filtered by the caller's
workspace.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.activities.general.modules.storefront.models import StorefrontOrder
from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.auth.models.user import User
from app.platform.tenancy.context import current_tenant_id

orders_router = APIRouter(prefix="/site/orders", tags=["Site orders"])

# The lifecycle the suspended storefront checkout wrote; kept verbatim so existing
# rows stay valid.
ORDER_STATUSES = ("pending", "confirmed", "preparing", "out_for_delivery", "completed", "cancelled")


class OrderStatusIn(BaseModel):
    status: str = Field(pattern=r"^(pending|confirmed|preparing|out_for_delivery|completed|cancelled)$")


def _tenant_id(user: User) -> uuid.UUID:
    tid = current_tenant_id.get() or user.tenant_id
    if not tid:
        raise HTTPException(status_code=400, detail="لا توجد مساحة عمل مرتبطة")
    return tid


def _order(o: StorefrontOrder) -> dict:
    return {
        "id": str(o.id),
        "order_number": o.order_number,
        "customer_name": o.customer_name,
        "customer_phone": o.customer_phone,
        "customer_email": o.customer_email,
        "delivery_type": o.delivery_type,
        "delivery_address": o.delivery_address,
        "table_number": o.table_number,
        "notes": o.notes,
        "subtotal": o.subtotal,
        "delivery_fee": o.delivery_fee,
        "discount_amount": o.discount_amount,
        "coupon_code": o.coupon_code,
        "total_amount": o.total_amount,
        "status": o.status,
        "payment_method": o.payment_method,
        "payment_status": o.payment_status,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "items": [
            {
                "product_name": itm.product_name,
                "unit_price": itm.unit_price,
                "quantity": itm.quantity,
                "total_price": itm.total_price,
                "notes": itm.notes,
            }
            for itm in o.items
        ],
    }


@orders_router.get("")
async def list_orders(
    status_filter: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm("site.manage")),
):
    """List the workspace's website orders, newest first."""
    stmt = select(StorefrontOrder).where(StorefrontOrder.tenant_id == _tenant_id(user))
    if status_filter and status_filter != "all":
        if status_filter not in ORDER_STATUSES:
            raise HTTPException(status_code=422, detail="حالة الطلب غير معروفة")
        stmt = stmt.where(StorefrontOrder.status == status_filter)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(
            StorefrontOrder.order_number.ilike(like),
            StorefrontOrder.customer_name.ilike(like),
            StorefrontOrder.customer_phone.ilike(like),
        ))
    stmt = stmt.order_by(StorefrontOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    orders = (await db.execute(stmt)).scalars().all()
    return {"items": [_order(o) for o in orders], "page": page, "page_size": page_size,
            "statuses": list(ORDER_STATUSES)}


@orders_router.post("/{order_id}/status")
async def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm("site.manage")),
):
    """Move a website order along its lifecycle; completing a COD order marks it paid."""
    stmt = select(StorefrontOrder).where(
        StorefrontOrder.id == order_id,
        StorefrontOrder.tenant_id == _tenant_id(user),
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    order.status = payload.status
    if payload.status == "completed" and order.payment_method == "cod":
        order.payment_status = "paid"
    await db.commit()
    return {"ok": True, "status": order.status, "payment_status": order.payment_status}
