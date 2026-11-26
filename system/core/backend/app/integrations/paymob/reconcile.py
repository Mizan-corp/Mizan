"""Applying Paymob transactions to invoices, and catching the ones whose callback never came (#67).

`apply_transaction` is the one path a Paymob transaction takes, whether it arrives in the
HMAC-verified callback or is fetched from Paymob's inquiry API: recorded once per transaction
and state (payment_transactions.event_key), matched to the invoice, checked against its amount,
then the invoice is activated (or marked refunded).

The inquiry API uses Paymob's older auth flow (PAYMOB_API_KEY → short-lived token), separate
from the Intention keys. Without the API key, reconciliation is skipped.
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.paymob import service as paymob
from app.platform.auth.models.owner import PaymentTransaction
from app.platform.billing.models import BillingInvoice
from app.platform.billing.services.subscriptions import activate_invoice
from app.platform.tenancy.models import PlatformAuditLog, Tenant

logger = logging.getLogger("mizan.paymob")
ORDER_REF = "paymob-order:"


async def invoice_for(db: AsyncSession, obj: dict) -> BillingInvoice | None:
    order = obj.get("order") or {}
    refs = [order.get("merchant_order_id"), obj.get("special_reference"),
            ((obj.get("payment_key_claims") or {}).get("extra") or {}).get("invoice_ref")]
    for ref in filter(None, refs):
        inv = await db.scalar(select(BillingInvoice).where(BillingInvoice.invoice_ref == str(ref)))
        if inv:
            return inv
    if order.get("id"):
        return await db.scalar(select(BillingInvoice).where(BillingInvoice.payment_gateway_ref == f"{ORDER_REF}{order['id']}"))
    return None


async def apply_transaction(db: AsyncSession, obj: dict, *, source: str = "callback") -> dict:
    """Record a Paymob transaction once and apply it to its invoice. Commits."""
    state = paymob.transaction_state(obj)
    inv = await invoice_for(db, obj)
    amount_cents = int(obj.get("amount_cents") or 0)
    stored = await db.scalar(
        insert(PaymentTransaction)
        .values(
            id=uuid.uuid4(), provider="paymob", event_key=f"paymob:{obj.get('id')}:{state}",
            provider_txn_id=str(obj.get("id")), invoice_id=inv.id if inv else None, state=state,
            amount_cents=amount_cents, currency=str(obj.get("currency") or ""), raw=obj,
        )
        .on_conflict_do_nothing(index_elements=["event_key"])
        .returning(PaymentTransaction.id)
    )
    if stored is None:
        return {"ok": True, "duplicate": True, "state": state}
    if inv is None:
        logger.warning("Paymob txn %s matches no invoice", obj.get("id"))
        await db.commit()
        return {"ok": True, "matched": False, "state": state}

    action = None
    if state == "paid":
        expected = round(inv.amount_egp * 100)
        if amount_cents != expected or (obj.get("currency") or "EGP") != "EGP":
            logger.error("Paymob txn %s amount %s %s ≠ invoice %s (%s)", obj.get("id"), amount_cents,
                         obj.get("currency"), inv.invoice_ref, expected)
            inv.notes = f"{inv.notes or ''}\nPaymob txn {obj.get('id')} paid {amount_cents / 100} {obj.get('currency')}, expected {expected / 100}".strip()
        elif inv.status != "paid":
            # A late payment on an abandoned checkout still counts.
            await activate_invoice(db, inv, reference=f"paymob:{obj.get('id')}")
            action = "invoice_paid_online"
    elif state in ("refunded", "voided") and inv.status == "paid":
        inv.status = "refunded"
        action = "invoice_refunded_online"

    if action:
        tenant_name = await db.scalar(select(Tenant.name).where(Tenant.id == inv.tenant_id))
        db.add(PlatformAuditLog(
            tenant_id=inv.tenant_id, action=action,
            details={"invoice": inv.invoice_ref, "amount_egp": inv.amount_egp, "plan": inv.plan,
                     "transaction": str(obj.get("id")), "workspace_name": tenant_name, "source": source},
        ))
    await db.commit()
    if action == "invoice_paid_online":  # the receipt to the owner's verified email (#72)
        from app.platform.billing.owner_emails import email_receipt

        await email_receipt(db, inv)
    return {"ok": True, "state": state}


# ── Inquiry ───────────────────────────────────────────────────────────────────────────────────

def inquiry_configured() -> bool:
    return bool(settings.PAYMOB_API_KEY)


def _http(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"{settings.PAYMOB_BASE_URL.rstrip('/')}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read() or b"{}")


def _order_transactions(order_id: str) -> list[dict]:
    """Every transaction of a Paymob order, each in the callback's shape."""
    token = _http("POST", "/api/auth/tokens", {"api_key": settings.PAYMOB_API_KEY})["token"]
    order = _http("GET", f"/api/ecommerce/orders/{order_id}?token={token}")
    ids = [t.get("id") for t in order.get("transactions") or [] if isinstance(t, dict) and t.get("id")]
    return [_http("GET", f"/api/acceptance/transactions/{tid}?token={token}") for tid in ids]


async def reconcile_invoice(db: AsyncSession, invoice: BillingInvoice) -> dict:
    """Ask Paymob about a pending invoice's order and apply what it says."""
    if not inquiry_configured():
        return {"checked": False, "reason": "PAYMOB_API_KEY isn't set"}
    if invoice.status != "pending":
        return {"checked": False, "reason": f"The invoice is {invoice.status}, not pending"}
    ref = invoice.payment_gateway_ref or ""
    if not ref.startswith(ORDER_REF):
        return {"checked": False, "reason": "No Paymob order on this invoice"}
    try:
        txns = await asyncio.to_thread(_order_transactions, ref.removeprefix(ORDER_REF))
    except (urllib.error.URLError, KeyError, ValueError) as e:
        logger.warning("Paymob inquiry for %s failed: %s", invoice.invoice_ref, e)
        return {"checked": False, "reason": "Paymob didn't answer"}
    results = [await apply_transaction(db, t, source="inquiry") for t in txns]
    await db.refresh(invoice)
    return {"checked": True, "transactions": len(txns), "applied": sum(1 for r in results if not r.get("duplicate")),
            "status": invoice.status}


async def reconcile_pending(db: AsyncSession, *, older_than=timedelta(minutes=15), younger_than=timedelta(hours=48)) -> dict:
    """Pending Paymob invoices from the last two days whose callback hasn't come (scheduled)."""
    if not inquiry_configured():
        return {"message": "PAYMOB_API_KEY isn't set: nothing checked", "items_processed": 0}
    now = datetime.now(UTC)
    pending = (await db.execute(select(BillingInvoice).where(
        BillingInvoice.status == "pending", BillingInvoice.payment_gateway_ref.like(f"{ORDER_REF}%"),
        BillingInvoice.created_at < now - older_than, BillingInvoice.created_at > now - younger_than,
    ))).scalars().all()
    paid = 0
    for inv in pending:
        r = await reconcile_invoice(db, inv)
        paid += r.get("status") == "paid"
    return {"message": f"Checked {len(pending)} pending Paymob invoice(s); {paid} turned out paid", "items_processed": len(pending)}
