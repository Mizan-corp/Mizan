"""Billing: invoices, upgrade requests and revenue across all workspaces."""
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_api.common import iso, record, tenant_names
from app.db.base import get_db
from app.dependencies import require_superadmin
from app.models.billing import BillingInvoice
from app.models.tenant import Subscription
from app.models.user import User
from app.services.subscriptions import activate_invoice, plan_name, revenue_breakdown

router = APIRouter(prefix="/admoon/billing", tags=["admin: billing"])


@router.get("")
async def billing_overview(
    status: Literal["pending", "paid", "failed"] | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    pending_count, pending_total = (await db.execute(
        select(func.count(BillingInvoice.id), func.coalesce(func.sum(BillingInvoice.amount_egp), 0))
        .where(BillingInvoice.status == "pending")
    )).one()
    collected = await db.scalar(
        select(func.coalesce(func.sum(BillingInvoice.amount_egp), 0))
        .where(BillingInvoice.status == "paid", BillingInvoice.paid_at >= month_start)
    )

    stmt = select(BillingInvoice).order_by((BillingInvoice.status == "pending").desc(), BillingInvoice.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(BillingInvoice.status == status)
    invoices = (await db.execute(stmt)).scalars().all()
    requests = (await db.execute(
        select(Subscription).where(Subscription.status == "requested")
        .order_by(Subscription.created_at.desc()).limit(100)
    )).scalars().all()
    names = await tenant_names(db, {i.tenant_id for i in invoices} | {r.tenant_id for r in requests})

    return {
        "summary": {
            **(await revenue_breakdown(db)),
            "pending_count": pending_count,
            "pending_egp": float(pending_total),
            "collected_this_month_egp": float(collected or 0),
        },
        "invoices": [
            {"ref": i.invoice_ref, "tenant_id": str(i.tenant_id), "tenant_name": names.get(i.tenant_id),
             "plan": i.plan, "plan_name": plan_name(i.plan), "cycle": i.billing_cycle, "amount_egp": i.amount_egp,
             "method": i.payment_method, "status": i.status, "created_at": iso(i.created_at), "paid_at": iso(i.paid_at)}
            for i in invoices
        ],
        "requests": [
            {"id": str(r.id), "tenant_id": str(r.tenant_id), "tenant_name": names.get(r.tenant_id),
             "plan": r.plan, "plan_name": plan_name(r.plan), "status": r.status, "phone": r.contact_phone,
             "created_at": iso(r.created_at)}
            for r in requests
        ],
    }


class MarkPaid(BaseModel):
    reference: str | None = Field(default=None, max_length=128, description="Bank or wallet transfer reference")
    note: str | None = Field(default=None, max_length=500)


@router.post("/invoices/{ref}/mark-paid")
async def mark_invoice_paid(
    ref: str,
    body: MarkPaid,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    invoice = (await db.execute(select(BillingInvoice).where(BillingInvoice.invoice_ref == ref))).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == "paid":
        raise HTTPException(status_code=409, detail="This invoice is already paid")
    await activate_invoice(db, invoice, reference=body.reference, note=body.note)
    await db.commit()
    await record(db, admin, "invoice_marked_paid", tenant_id=invoice.tenant_id, request=request,
                 invoice=ref, plan=invoice.plan, amount_egp=invoice.amount_egp, reference=body.reference)
    return {"ok": True}


@router.post("/requests/{request_id}/dismiss")
async def dismiss_request(
    request_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superadmin),
):
    sub = await db.get(Subscription, request_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Request not found")
    sub.status = "dismissed"
    await db.commit()
    await record(db, admin, "upgrade_request_dismissed", tenant_id=sub.tenant_id, request=request, plan=sub.plan)
    return {"ok": True}
