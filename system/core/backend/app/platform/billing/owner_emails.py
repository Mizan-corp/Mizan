"""Billing emails to owners (#72): the receipt after a payment, and trial and renewal reminders.

Sent only to a verified address, each once (owner_mail.send_once), never blocking or failing the
payment or the job that triggers it. Cloud workspaces only: on-site installs bill differently.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mizan.billing_emails")

TRIAL_WARN_DAYS = 3
PAID_WARN_DAYS = 7


def _panel(path: str = "/") -> str:
    from app.core.config import settings

    return settings.OWNER_APP_URL.rstrip("/") + path


async def _tenant_owner(db: AsyncSession, tenant_id):
    from app.platform.auth.models.owner import OwnerAccount
    from app.platform.tenancy.models import Tenant

    tenant = await db.get(Tenant, tenant_id)
    owner = (await db.get(OwnerAccount, tenant.owner_account_id, populate_existing=True)
             if tenant and tenant.owner_account_id else None)
    return tenant, owner


async def email_receipt(db: AsyncSession, invoice) -> bool:
    """The paid invoice's receipt to the workspace owner. Call after the payment is committed;
    never raises."""
    from app.platform.auth.services.owner_mail import send_once
    from app.platform.billing.plans import PLANS_CONFIG
    from app.platform.billing.receipt import receipt_file
    from app.platform.notifications.emails import receipt_email

    try:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        tenant, owner = await _tenant_owner(db, invoice.tenant_id)
        if not tenant or not owner:
            return False
        content, media, ext = await receipt_file(invoice, tenant.name, owner.full_name)
        fmt = "%Y-%m-%d"
        period = f"{invoice.period_start:{fmt}} → {invoice.period_end:{fmt}}" if invoice.period_end else f"{invoice.period_start:{fmt}}"
        plan = PLANS_CONFIG.get(invoice.plan, {}).get("name") or invoice.plan
        subject, html, plain = receipt_email(owner.full_name, tenant.name, invoice.invoice_ref, f"{invoice.amount_egp:,.2f} ج.م",
                                             plan, period, _panel("/invoices"))
        return await send_once(db, owner, "receipt", invoice.invoice_ref, subject, html, plain,
                               attachments=[{"filename": f"Mizan-{invoice.invoice_ref}.{ext}", "content": content,
                                             "type": media.split(";")[0]}])
    except Exception as e:
        logger.warning("Receipt email for %s failed: %s", getattr(invoice, "invoice_ref", "?"), e)
        return False


async def billing_reminders(db: AsyncSession) -> dict:
    """Trials ending in 3 days or ended, paid periods ending in 7 days or ended: one email each
    (per workspace and end date) to the owner's verified address."""
    from app.platform.auth.models.owner import OwnerAccount
    from app.platform.auth.services.owner_mail import send_once
    from app.platform.notifications.emails import reminder_email
    from app.platform.tenancy.models import Tenant

    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    now = datetime.now(UTC)
    rows = (await db.execute(
        select(Tenant, OwnerAccount).join(OwnerAccount, OwnerAccount.id == Tenant.owner_account_id)
        .where(Tenant.deployment_mode == "cloud_saas", OwnerAccount.email_verified_at.is_not(None), OwnerAccount.is_active)
        .execution_options(populate_existing=True)  # current rows, not what the session already holds
    )).all()
    sent = 0
    for tenant, owner in rows:
        if tenant.plan == "trial" and tenant.trial_ends_at:
            end, warn = tenant.trial_ends_at, TRIAL_WARN_DAYS
            kinds = ("trial_ending", "trial_expired")
        elif tenant.plan != "trial" and tenant.paid_until:
            end, warn = tenant.paid_until, PAID_WARN_DAYS
            kinds = ("paid_ending", "paid_expired")
        else:
            continue
        if now >= end:
            if now - end > timedelta(days=7):
                continue  # long gone: don't start mailing about it now
            kind = kinds[1]
        elif end - now <= timedelta(days=warn):
            kind = kinds[0]
        else:
            continue
        days = max(0, (end - now).days)
        subject, html, plain = reminder_email(kind, owner.full_name, tenant.name, days, _panel(f"/workspaces/{tenant.id}"))
        try:
            if await send_once(db, owner, kind, f"{tenant.id}:{end:%Y-%m-%d}", subject, html, plain):
                sent += 1
        except Exception as e:
            logger.warning("Reminder %s for %s failed: %s", kind, tenant.id, e)
    return {"message": f"أُرسل {sent} تذكيرًا بالبريد", "items_processed": sent}
