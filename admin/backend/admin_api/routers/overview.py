"""Overview: the state of the platform and what needs attention today."""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_api.common import days_until, iso, tenant_names
from admin_api.routers.activity import recent_activity
from app.db.base import get_db
from app.dependencies import require_superadmin
from app.platform.billing.models import BillingInvoice
from app.platform.tenancy.models import Subscription, Tenant
from app.platform.auth.models.user import User
from app.platform.billing.services.subscriptions import PAID_PLANS, revenue_breakdown

router = APIRouter(prefix="/admoon/overview", tags=["admin: overview"])

WEEKS = 12


@router.get("")
async def overview(db: AsyncSession = Depends(get_db), _: User = Depends(require_superadmin)):
    now = datetime.now(UTC)
    on_trial = (Tenant.plan == "trial") & (Tenant.status != "suspended")
    total, active, trial, paying, suspended = (await db.execute(select(
        func.count(Tenant.id),
        func.count(case((Tenant.status == "active", 1))),
        func.count(case((on_trial, 1))),
        func.count(case(((Tenant.status == "active") & Tenant.plan.in_(PAID_PLANS), 1))),
        func.count(case((Tenant.status == "suspended", 1))),
    ))).one()

    # Signups per week for the last WEEKS weeks (oldest first, empty weeks included).
    week = func.date_trunc("week", Tenant.created_at)
    since = (now - timedelta(weeks=WEEKS - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    since -= timedelta(days=since.weekday())
    by_week = {w.date(): n for w, n in (await db.execute(
        select(week, func.count()).where(Tenant.created_at >= since).group_by(week)
    )).all()}
    signups = [{"week": (since + timedelta(weeks=i)).date().isoformat(),
                "count": by_week.get((since + timedelta(weeks=i)).date(), 0)} for i in range(WEEKS)]

    # Needs attention, most urgent first.
    attention: list[dict] = []
    expired = (await db.execute(select(Tenant).where(on_trial, Tenant.trial_ends_at < now)
                                .order_by(Tenant.trial_ends_at))).scalars().all()
    attention += [{"kind": "trial_expired", "tenant_id": str(t.id), "tenant_name": t.name,
                   "days": -days_until(t.trial_ends_at), "at": iso(t.trial_ends_at)} for t in expired]

    # Open Paymob checkouts settle themselves; only manual invoices need a person.
    pending = (await db.execute(select(BillingInvoice).where(BillingInvoice.status == "pending", BillingInvoice.payment_method != "paymob")
                                .order_by(BillingInvoice.created_at))).scalars().all()
    requests = (await db.execute(select(Subscription).where(Subscription.status == "requested")
                                 .order_by(Subscription.created_at))).scalars().all()
    names = await tenant_names(db, {i.tenant_id for i in pending} | {r.tenant_id for r in requests})
    attention += [{"kind": "invoice_pending", "tenant_id": str(i.tenant_id), "tenant_name": names.get(i.tenant_id),
                   "ref": i.invoice_ref, "amount_egp": i.amount_egp, "plan": i.plan,
                   "at": iso(i.created_at)} for i in pending]
    attention += [{"kind": "upgrade_request", "tenant_id": str(r.tenant_id), "tenant_name": names.get(r.tenant_id),
                   "request_id": str(r.id), "plan": r.plan, "phone": r.contact_phone,
                   "at": iso(r.created_at)} for r in requests]

    ending = (await db.execute(select(Tenant).where(on_trial, Tenant.trial_ends_at >= now,
                                                    Tenant.trial_ends_at < now + timedelta(days=7))
                               .order_by(Tenant.trial_ends_at))).scalars().all()
    attention += [{"kind": "trial_ending", "tenant_id": str(t.id), "tenant_name": t.name,
                   "days": days_until(t.trial_ends_at), "at": iso(t.trial_ends_at)} for t in ending]

    newest = (await db.execute(select(Tenant).order_by(Tenant.created_at.desc()).limit(5))).scalars().all()

    return {
        "counts": {"workspaces": total, "active": active, "on_trial": trial, "paying": paying, "suspended": suspended,
                   "users": await db.scalar(select(func.count(User.id))) or 0},
        "revenue": await revenue_breakdown(db),
        "signups": signups,
        "signups_last_30_days": await db.scalar(select(func.count(Tenant.id))
                                                .where(Tenant.created_at >= now - timedelta(days=30))) or 0,
        "attention": attention,
        "newest": [{"id": str(t.id), "name": t.name, "sector": t.sector, "plan": t.plan,
                    "created_at": iso(t.created_at)} for t in newest],
        "activity": await recent_activity(db, limit=8),
    }
