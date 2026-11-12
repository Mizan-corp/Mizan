"""Billing: invoices and revenue across all workspaces. (Upgrade requests were retired in #70:
subscribing happens in the owner panel.)"""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_api.common import iso, record, tenant_names
from app.db.base import get_db
from app.dependencies import require_superadmin
from app.platform.billing.models import BillingInvoice
from app.platform.auth.models.user import User
from app.platform.billing.services.subscriptions import activate_invoice, plan_name, revenue_breakdown

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
    names = await tenant_names(db, {i.tenant_id for i in invoices})

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
             "method": i.payment_method,
             "paymob": (i.payment_gateway_ref or "").startswith("paymob-order:"), "status": i.status, "created_at": iso(i.created_at), "paid_at": iso(i.paid_at)}
            for i in invoices
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


@router.post("/invoices/{ref}/check-paymob")
async def check_paymob(ref: str, request: Request, db: AsyncSession = Depends(get_db),
                       admin: User = Depends(require_superadmin)):
    """Ask Paymob about a pending invoice whose callback never came, and apply the answer (#67)."""
    from app.integrations.paymob.reconcile import reconcile_invoice

    invoice = (await db.execute(select(BillingInvoice).where(BillingInvoice.invoice_ref == ref))).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    result = await reconcile_invoice(db, invoice)
    if not result.get("checked"):
        raise HTTPException(status_code=409, detail=result.get("reason") or "Couldn't check with Paymob")
    await record(db, admin, "invoice_checked_with_paymob", tenant_id=invoice.tenant_id, request=request,
                 invoice=ref, status=result["status"], transactions=result["transactions"])
    return result


@router.get("/invoices/{ref}/receipt.pdf")
async def invoice_receipt(ref: str, db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    """A paid invoice's receipt, as the owner downloads it (#69)."""
    from fastapi.responses import Response

    from app.platform.auth.models.owner import OwnerAccount
    from app.platform.billing.receipt import receipt_pdf
    from app.platform.tenancy.models import Tenant

    row = (await db.execute(
        select(BillingInvoice, Tenant, OwnerAccount).join(Tenant, Tenant.id == BillingInvoice.tenant_id)
        .outerjoin(OwnerAccount, OwnerAccount.id == Tenant.owner_account_id)
        .where(BillingInvoice.invoice_ref == ref)
    )).first()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice, tenant, owner = row
    if invoice.status != "paid":
        raise HTTPException(status_code=409, detail="Receipts exist for paid invoices only")
    pdf = await receipt_pdf(invoice, tenant.name, (owner.full_name or owner.login) if owner else None)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Mizan-receipt-{invoice.invoice_ref}.pdf"'})
