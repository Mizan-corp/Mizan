"""Subscriptions and invoices: one place for the money rules.

Used by the billing API (checkout, payment webhooks), the admin panel and the
owner panel, so a paid invoice activates a plan the same way everywhere.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import PLANS_CONFIG, get_plan, get_plan_limits
from app.models.billing import BillingInvoice
from app.models.tenant import Subscription, Tenant

PAID_PLANS = tuple(p for p in PLANS_CONFIG if p != "trial")


def monthly_price(plan: str) -> float:
    """List price per month for a plan (0 for the trial or unknown plans)."""
    return float(PLANS_CONFIG.get(plan, {}).get("price_monthly_egp", 0) or 0)


def plan_name(plan: str) -> str:
    return get_plan(plan)["name"]


def is_paying(tenant: Tenant) -> bool:
    return tenant.plan in PAID_PLANS and tenant.status == "active"


async def monthly_recurring_revenue(db: AsyncSession) -> float:
    """MRR from money actually paid: for every active workspace on a paid plan,
    its latest paid invoice for that plan, annual invoices spread over 12 months."""
    return (await revenue_breakdown(db))["mrr_egp"]


async def revenue_breakdown(db: AsyncSession) -> dict:
    """MRR plus the paid-plan workspaces with no paid invoice (complimentary)."""
    paying = (await db.execute(
        select(Tenant.id, Tenant.plan).where(Tenant.status == "active", Tenant.plan.in_(PAID_PLANS))
    )).all()
    if not paying:
        return {"mrr_egp": 0.0, "paying": 0, "complimentary": 0}
    invoices = (await db.execute(
        select(BillingInvoice)
        .where(BillingInvoice.status == "paid", BillingInvoice.tenant_id.in_([t for t, _ in paying]))
        .order_by(BillingInvoice.paid_at.desc())
    )).scalars().all()
    latest: dict = {}
    for inv in invoices:
        latest.setdefault((inv.tenant_id, inv.plan), inv)
    mrr, complimentary = 0.0, 0
    for tenant_id, plan in paying:
        inv = latest.get((tenant_id, plan))
        if inv is None:
            complimentary += 1
            continue
        mrr += inv.amount_egp / 12 if inv.billing_cycle == "annual" else inv.amount_egp
    return {"mrr_egp": round(mrr, 2), "paying": len(paying) - complimentary, "complimentary": complimentary}


def invoice_amount(plan: str, cycle: str) -> float:
    cfg = get_plan(plan)
    return float(cfg["price_annual_egp"] if cycle == "annual" else cfg["price_monthly_egp"])


async def paid_until(db: AsyncSession, tenant_id: uuid.UUID) -> datetime | None:
    """End of the latest paid period, if any."""
    return await db.scalar(
        select(BillingInvoice.period_end)
        .where(BillingInvoice.tenant_id == tenant_id, BillingInvoice.status == "paid")
        .order_by(BillingInvoice.period_end.desc().nulls_last())
        .limit(1)
    )


async def new_invoice(
    db: AsyncSession,
    tenant: Tenant,
    *,
    plan: str,
    cycle: str,
    method: str,
) -> BillingInvoice:
    """A pending invoice for a paid plan. Renewing the current plan early starts
    the new period where the paid one ends. The caller commits."""
    if plan not in PAID_PLANS:
        raise ValueError(f"not a paid plan: {plan}")
    if cycle not in ("monthly", "annual"):
        raise ValueError(f"unknown billing cycle: {cycle}")
    now = datetime.now(UTC)
    start = now
    if tenant.plan == plan:
        current_end = await paid_until(db, tenant.id)
        if current_end and current_end > now:
            start = current_end
    invoice = BillingInvoice(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        # Unguessable: it's the gateway's merchant order id and appears in URLs.
        invoice_ref=f"INV-{now:%Y%m}-{uuid.uuid4().hex[:10].upper()}",
        plan=plan,
        billing_cycle=cycle,
        amount_egp=invoice_amount(plan, cycle),
        payment_method=method,
        status="pending",
        period_start=start,
        period_end=start + timedelta(days=365 if cycle == "annual" else 30),
    )
    db.add(invoice)
    await db.flush()
    return invoice


async def activate_invoice(
    db: AsyncSession,
    invoice: BillingInvoice,
    *,
    reference: str | None = None,
    note: str | None = None,
) -> Tenant | None:
    """Mark an invoice paid and move its workspace onto the invoiced plan.

    Ends the trial, applies the plan's limits, reactivates the workspace and
    marks the latest subscription request active. Idempotent for paid invoices.
    The caller commits.
    """
    if invoice.status == "paid":
        return await db.get(Tenant, invoice.tenant_id)

    invoice.status = "paid"
    invoice.paid_at = datetime.now(UTC)
    invoice.payment_gateway_ref = reference or invoice.payment_gateway_ref or f"MANUAL-{uuid.uuid4().hex[:10].upper()}"
    if note:
        invoice.notes = f"{invoice.notes}\n{note}" if invoice.notes else note

    tenant = await db.get(Tenant, invoice.tenant_id)
    if tenant:
        tenant.plan = invoice.plan
        tenant.status = "active"
        tenant.limits = get_plan_limits(invoice.plan)
        tenant.trial_ends_at = None
        if invoice.period_end:
            # Single-device and LAN workspaces: the licence runs to the end of the paid period.
            from app.platform.licensing.services.licences import extend_to, is_on_premise

            if is_on_premise(tenant):
                await extend_to(db, tenant, invoice.period_end)

    latest = (
        await db.execute(
            select(Subscription).where(Subscription.tenant_id == invoice.tenant_id).order_by(desc(Subscription.created_at))
        )
    ).scalars().first()
    if latest:
        latest.status = "active"
    return tenant
