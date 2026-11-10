"""Billing in the ERP: read-only plan, usage and invoices.

Subscribing and paying happen in the owner panel (owner/), through Paymob, so
nobody inside a workspace can change its plan. The old checkout,
simulate-payment and unsigned webhook endpoints were removed: the simulator
let any signed-in user activate a paid plan for free.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import PLANS_CONFIG
from app.core.tenancy import current_tenant_id
from app.db.base import get_db
from app.dependencies import get_current_user
from app.models.billing import BillingInvoice
from app.models.user import User
from app.platform.billing.services.plan_gating import get_tenant_limits_and_usage

router = APIRouter(prefix="/billing", tags=["billing"])


# Pydantic Schemas
@router.get("/plans")
async def list_available_plans() -> dict[str, Any]:
    """Return all public SaaS subscription plans and tiers."""
    return {"plans": list(PLANS_CONFIG.values())}


@router.get("/subscription")
async def get_my_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return current tenant's subscription status, quotas, and recent invoices."""
    tid = current_tenant_id.get() or current_user.tenant_id
    if not tid:
        raise HTTPException(status_code=400, detail="لا توجد مساحة عمل مرتبطة")

    usage = await get_tenant_limits_and_usage(db, tid)

    # Invoices
    q_invoices = await db.execute(
        select(BillingInvoice)
        .where(BillingInvoice.tenant_id == tid)
        .order_by(desc(BillingInvoice.created_at))
        .limit(10)
    )
    invoices = q_invoices.scalars().all()

    return {
        **usage,
        "invoices": [
            {
                "id": str(inv.id),
                "invoice_ref": inv.invoice_ref,
                "plan": inv.plan,
                "billing_cycle": inv.billing_cycle,
                "amount_egp": inv.amount_egp,
                "payment_method": inv.payment_method,
                "status": inv.status,
                "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
                "period_end": inv.period_end.isoformat() if inv.period_end else None,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            }
            for inv in invoices
        ],
    }
