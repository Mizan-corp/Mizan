"""Paymob (Accept) online payments: Intention API + Unified Checkout.

1. `create_checkout` creates a payment intention for a pending invoice and
   returns the Unified Checkout URL the owner is sent to.
2. Paymob POSTs the transaction to the owner API's callback with `?hmac=`;
   `verify_hmac` checks it before anything changes.
3. The owner is redirected back to the owner panel, which polls the invoice:
   the redirect itself is never trusted.

Docs: https://developers.paymob.com (Intention API, HMAC transaction callback).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from app.core.config import settings
from app.models.billing import BillingInvoice
from app.models.owner import OwnerAccount
from app.models.tenant import Tenant

logger = logging.getLogger("mizan.paymob")

# The transaction callback's HMAC covers these fields of `obj`, in this order.
HMAC_FIELDS = (
    "amount_cents",
    "created_at",
    "currency",
    "error_occured",
    "has_parent_transaction",
    "id",
    "integration_id",
    "is_3d_secure",
    "is_auth",
    "is_capture",
    "is_refunded",
    "is_standalone_payment",
    "is_voided",
    "order.id",
    "owner",
    "pending",
    "source_data.pan",
    "source_data.sub_type",
    "source_data.type",
    "success",
)


class PaymobError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.PAYMOB_SECRET_KEY and settings.PAYMOB_PUBLIC_KEY and settings.PAYMOB_HMAC_SECRET and integration_ids())


def integration_ids() -> list[int]:
    return [int(x) for x in settings.PAYMOB_INTEGRATION_IDS.replace(" ", "").split(",") if x.isdigit()]


def _base() -> str:
    return settings.PAYMOB_BASE_URL.rstrip("/")


def _field(obj: dict, dotted: str) -> Any:
    value: Any = obj
    for part in dotted.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def _as_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def transaction_hmac(obj: dict, secret: str | None = None) -> str:
    message = "".join(_as_text(_field(obj, f)) for f in HMAC_FIELDS)
    return hmac.new((secret or settings.PAYMOB_HMAC_SECRET).encode(), message.encode(), hashlib.sha512).hexdigest()


def verify_hmac(obj: dict, received: str | None) -> bool:
    if not settings.PAYMOB_HMAC_SECRET or not received:
        return False
    return hmac.compare_digest(transaction_hmac(obj), received.strip().lower())


def transaction_state(obj: dict) -> str:
    if obj.get("is_refunded"):
        return "refunded"
    if obj.get("is_voided"):
        return "voided"
    if obj.get("pending"):
        return "pending"
    return "paid" if obj.get("success") else "failed"


def _split_name(full: str) -> tuple[str, str]:
    parts = (full or "").split()
    return (parts[0] if parts else "Mizan"), (" ".join(parts[1:]) or "Owner")


def _post_json(url: str, body: dict, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read()[:500].decode(errors="replace")
        logger.warning("Paymob %s → %s: %s", url, e.code, detail)
        raise PaymobError(f"Paymob refused the request ({e.code})") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise PaymobError(f"Couldn't reach Paymob: {e}") from None


async def create_checkout(invoice: BillingInvoice, tenant: Tenant, owner: OwnerAccount) -> dict:
    """Create an intention for `invoice`; return its checkout URL and ids."""
    if not is_configured():
        raise PaymobError("Paymob isn't configured")
    amount_cents = round(invoice.amount_egp * 100)
    first, last = _split_name(owner.full_name)
    phone = owner.phone or "NA"
    body = {
        "amount": amount_cents,
        "currency": "EGP",
        "payment_methods": integration_ids(),
        "items": [{
            "name": f"Mizan {invoice.plan} ({invoice.billing_cycle})"[:50],
            "amount": amount_cents,
            "description": f"{tenant.name} — {invoice.invoice_ref}"[:255],
            "quantity": 1,
        }],
        "billing_data": {
            "first_name": first, "last_name": last,
            "email": owner.email or f"{owner.login}@owners.mizan.local",
            "phone_number": phone,
            "apartment": "NA", "floor": "NA", "street": "NA", "building": "NA",
            "city": "NA", "state": "NA", "country": "EG",
        },
        "special_reference": invoice.invoice_ref,
        "notification_url": f"{settings.OWNER_API_URL.rstrip('/')}/account/paymob/callback",
        "redirection_url": f"{settings.OWNER_APP_URL.rstrip('/')}/payment/{invoice.invoice_ref}",
        "extras": {"invoice_ref": invoice.invoice_ref, "tenant_id": str(tenant.id)},
    }
    data = await asyncio.to_thread(
        _post_json, f"{_base()}/v1/intention/", body, {"Authorization": f"Token {settings.PAYMOB_SECRET_KEY}"}
    )
    secret = data.get("client_secret")
    if not secret:
        raise PaymobError("Paymob didn't return a client secret")
    return {
        "checkout_url": f"{_base()}/unifiedcheckout/?publicKey={settings.PAYMOB_PUBLIC_KEY}&clientSecret={secret}",
        "intention_id": data.get("id"),
        "order_id": data.get("intention_order_id"),
    }
