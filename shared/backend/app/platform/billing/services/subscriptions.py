"""Subscriptions and invoices: one place for the money rules.

Used by the billing API (checkout, payment webhooks), the admin panel and the
owner panel, so a paid invoice activates a plan the same way everywhere.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.billing.plans import PLANS_CONFIG, get_plan, get_plan_limits
from app.platform.billing.models import BillingInvoice
from app.platform.tenancy.models import Subscription, Tenant

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


def period_days(cycle: str) -> int:
    return 365 if cycle == "annual" else 30


async def unused_paid_value(db: AsyncSession, tenant_id: uuid.UUID, now: datetime) -> float:
    """What the paid time still ahead is worth (EGP): each paid period that hasn't ended counts
    for the share of it not yet used (a period that hasn't started counts in full)."""
    rows = (await db.execute(
        select(BillingInvoice).where(
            BillingInvoice.tenant_id == tenant_id, BillingInvoice.status == "paid", BillingInvoice.period_end > now,
        )
    )).scalars().all()
    value = 0.0
    for inv in rows:
        if not inv.period_start or not inv.period_end:
            continue
        length = (inv.period_end - inv.period_start).total_seconds()
        if length > 0:
            value += float(inv.amount_egp) * min(1.0, (inv.period_end - max(inv.period_start, now)).total_seconds() / length)
    return value


async def checkout_quote(db: AsyncSession, tenant: Tenant, *, plan: str, cycle: str) -> dict:
    """What paying for `plan` now costs and when it runs (#68). The owner sees this before paying.

    - new: no paid time left (trial, lapsed, complimentary): starts now.
    - renewal: the same plan; starts where the paid time ends.
    - upgrade: a dearer plan; starts now, at full price, and the paid time not yet used becomes
      extra days on the new plan, at the new plan's daily rate (nothing is lost, and the amount
      sent to Paymob is always the plan's price).
    - downgrade: a cheaper plan; starts where the paid time ends (the workspace keeps the plan it
      paid for until then).
    """
    if plan not in PAID_PLANS:
        raise ValueError(f"not a paid plan: {plan}")
    if cycle not in ("monthly", "annual"):
        raise ValueError(f"unknown billing cycle: {cycle}")
    now = datetime.now(UTC)
    amount = invoice_amount(plan, cycle)
    days = period_days(cycle)
    current_end = await paid_until(db, tenant.id)
    has_paid_time = tenant.plan in PAID_PLANS and current_end is not None and current_end > now
    credit_egp, credit_days = 0.0, 0
    if not has_paid_time:
        kind, start = "new", now
    elif plan == tenant.plan:
        kind, start = "renewal", current_end
    elif monthly_price(plan) > monthly_price(tenant.plan):
        kind, start = "upgrade", now
        credit_egp = round(await unused_paid_value(db, tenant.id, now), 2)
        credit_days = int(credit_egp // (amount / days)) if amount else 0
    else:
        kind, start = "downgrade", current_end
    return {
        "kind": kind,
        "plan": plan,
        "cycle": cycle,
        "amount_egp": amount,
        "period_start": start,
        "period_end": start + timedelta(days=days + credit_days),
        "credit_egp": credit_egp,
        "credit_days": credit_days,
        "current_plan": tenant.plan,
        "current_paid_until": current_end,
    }


async def new_invoice(
    db: AsyncSession,
    tenant: Tenant,
    *,
    plan: str,
    cycle: str,
    method: str,
) -> BillingInvoice:
    """A pending invoice for a paid plan, as `checkout_quote` describes it: renewals and
    downgrades start where the paid time ends, upgrades start now with the unused paid time as
    extra days. The caller commits."""
    q = await checkout_quote(db, tenant, plan=plan, cycle=cycle)
    now = datetime.now(UTC)
    start = q["period_start"]
    notes = None
    if q["kind"] == "upgrade" and q["credit_days"]:
        notes = (f"ترقية من باقة {plan_name(tenant.plan)}: أُضيف {q['credit_days']} يومًا مقابل "
                 f"{q['credit_egp']:g} ج.م من الفترة المدفوعة غير المستخدمة.")
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
        period_end=q["period_end"],
        notes=notes,
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
        now = invoice.paid_at
        starts_now = invoice.period_start is None or invoice.period_start <= now + timedelta(minutes=5)
        if starts_now and tenant.plan != invoice.plan:
            # An upgrade (or a new plan): the paid time it credited (#68) ends now, so an older
            # period can't bring the old plan back later.
            credited = (await db.execute(select(BillingInvoice).where(
                BillingInvoice.tenant_id == tenant.id, BillingInvoice.id != invoice.id,
                BillingInvoice.status == "paid", BillingInvoice.period_end > now,
            ))).scalars().all()
            for old in credited:
                old.period_end = max(old.period_start or now, now)
                note = f"انتهت مبكرًا: حُسب الجزء غير المستخدم في {invoice.invoice_ref}."
                old.notes = f"{old.notes}\n{note}" if old.notes else note
            tenant.paid_until = invoice.period_end
        elif invoice.period_end and (tenant.paid_until is None or invoice.period_end > tenant.paid_until):
            tenant.paid_until = invoice.period_end  # renewals start where the paid period ends (#66)
        if starts_now:
            tenant.plan = invoice.plan
            tenant.limits = get_plan_limits(invoice.plan)
        # A period that starts later (a renewal or a downgrade) switches the plan then:
        # apply_due_plan_changes, run by the subscriptions job.
        tenant.status = "active"
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


async def apply_due_plan_changes(db: AsyncSession) -> int:
    """Move workspaces onto the plan of the paid period now running, when it differs (#68): a
    downgrade paid ahead starts when the dearer period ends. Run by the subscriptions job before
    it checks for lapsed periods. Returns how many changed; the caller commits."""
    now = datetime.now(UTC)
    running = (await db.execute(
        select(BillingInvoice, Tenant).join(Tenant, Tenant.id == BillingInvoice.tenant_id).where(
            BillingInvoice.status == "paid", BillingInvoice.period_start <= now, BillingInvoice.period_end > now,
            Tenant.status.in_(("active", "expired")),
        ).order_by(BillingInvoice.tenant_id, BillingInvoice.period_start.desc(), BillingInvoice.paid_at.desc())
    )).all()
    changed, seen = 0, set()
    for inv, tenant in running:
        if tenant.id in seen:
            continue
        seen.add(tenant.id)
        if tenant.plan != inv.plan:
            tenant.plan = inv.plan
            tenant.limits = get_plan_limits(inv.plan)
            tenant.status = "active"
            changed += 1
    return changed
