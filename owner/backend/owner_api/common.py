"""Small helpers shared by the owner API routers."""
from __future__ import annotations

from datetime import UTC, datetime

from app.models.billing import BillingInvoice
from app.models.tenant import Tenant


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def days_until(moment: datetime) -> int:
    """Whole days left, rounded up while ahead; completed days once past (negative)."""
    seconds = (moment - datetime.now(UTC)).total_seconds()
    return int(-(-seconds // 86400)) if seconds >= 0 else -int(-seconds // 86400)


def invoice_out(i: BillingInvoice, t: Tenant | None = None) -> dict:
    return {
        "ref": i.invoice_ref,
        "workspace_id": str(i.tenant_id),
        "workspace_name": t.name if t else None,
        "plan": i.plan,
        "cycle": i.billing_cycle,
        "amount_egp": i.amount_egp,
        "method": i.payment_method,
        "status": i.status,
        "period_start": iso(i.period_start),
        "period_end": iso(i.period_end),
        "paid_at": iso(i.paid_at),
        "created_at": iso(i.created_at),
    }
