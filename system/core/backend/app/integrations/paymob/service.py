"""Paymob (Accept) online payments.

Two flows, chosen by PAYMOB_FLOW:
- "intention" (default): an Intention API payment, paid on Paymob's Unified Checkout.
- "accept": the Accept API: an order and a payment key, then either our card page
  (a Paymob-hosted iframe, owner/paymob/) or a mobile-wallet payment.

1. `create_checkout` prepares the payment for a pending invoice and returns the URL
   the owner is sent to.
2. Paymob POSTs the transaction to the owner API's callback with `?hmac=`;
   `verify_hmac` checks it before anything changes (the same for both flows).
3. The owner is redirected back to the owner panel, which polls the invoice:
   the redirect itself is never trusted.

Docs: https://developers.paymob.com (Intention API, Accept API, HMAC transaction callback).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from app.core.config import settings
from app.platform.billing.models import BillingInvoice
from app.platform.auth.models.owner import OwnerAccount
from app.platform.tenancy.models import Tenant

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


def _accept_flow() -> bool:
    return settings.PAYMOB_FLOW.strip().lower() == "accept"


def methods() -> list[str]:
    """What an owner can pay with: in the accept flow, card only once our card page
    (PAYMOB_IFRAME_ID) exists; the intention flow offers every integration on one page."""
    if not settings.PAYMOB_HMAC_SECRET:
        return []
    if _accept_flow():
        if not settings.PAYMOB_API_KEY:
            return []
        out = []
        if settings.PAYMOB_CARD_INTEGRATION_ID.strip().isdigit() and settings.PAYMOB_IFRAME_ID.strip().isdigit():
            out.append("card")
        if settings.PAYMOB_WALLET_INTEGRATION_ID.strip().isdigit():
            out.append("wallet")
        return out
    if settings.PAYMOB_SECRET_KEY and settings.PAYMOB_PUBLIC_KEY and integration_ids():
        return ["any"]
    return []


def is_configured() -> bool:
    return bool(methods())


def test_owners() -> set[str]:
    return {x.strip().lower() for x in settings.PAYMOB_TEST_OWNERS.split(",") if x.strip()}


def can_pay(owner: OwnerAccount | None) -> bool:
    """Online payment is open to everyone, or only to PAYMOB_TEST_OWNERS while that is set."""
    if not is_configured():
        return False
    allowed = test_owners()
    return not allowed or (owner is not None and owner.login.lower() in allowed)


WALLET_NUMBER = re.compile(r"^01[0125]\d{8}$")


def normalize_wallet(number: str) -> str | None:
    """An Egyptian mobile-wallet number as 01xxxxxxxxx, or None."""
    digits = re.sub(r"\D", "", number or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("20") and len(digits) == 12:
        digits = "0" + digits[2:]
    return digits if WALLET_NUMBER.match(digits) else None


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


PLAN_LABELS = {"starter": "البداية", "pro": "الاحترافية", "enterprise": "المؤسسات"}


def describe(invoice: BillingInvoice, tenant: Tenant) -> str:
    """What the payment is for, as the card page shows it."""
    plan = PLAN_LABELS.get(invoice.plan, invoice.plan)
    cycle = "سنوي" if invoice.billing_cycle == "annual" else "شهري"
    return f"باقة {plan} · {cycle} · {tenant.name}"[:80]


async def create_checkout(invoice: BillingInvoice, tenant: Tenant, owner: OwnerAccount, *,
                          method: str | None = None, wallet_number: str | None = None) -> dict:
    """Prepare the payment for `invoice`; return the URL to send the owner to, and ids."""
    if not is_configured():
        raise PaymobError("Paymob isn't configured")
    if _accept_flow():
        return await _accept_checkout(invoice, tenant, owner, method or "", wallet_number)
    return await _intention_checkout(invoice, tenant, owner)


async def _intention_checkout(invoice: BillingInvoice, tenant: Tenant, owner: OwnerAccount) -> dict:
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


# ─── Accept API (orders, payment keys, iframe, wallets) ────────────────────

PAYMENT_KEY_SECONDS = 30 * 60


def _billing_data(owner: OwnerAccount, phone: str | None = None) -> dict:
    first, last = _split_name(owner.full_name)
    na = "NA"
    return {
        "first_name": first, "last_name": last,
        "email": owner.email or f"{owner.login}@owners.mizan.local",
        "phone_number": phone or owner.phone or na,
        "apartment": na, "floor": na, "street": na, "building": na, "shipping_method": na,
        "postal_code": na, "city": na, "state": na, "country": "EG",
    }


async def _accept_checkout(invoice: BillingInvoice, tenant: Tenant, owner: OwnerAccount,
                           method: str, wallet_number: str | None) -> dict:
    if method not in methods():
        raise PaymobError(f"Payment method {method!r} isn't available")
    phone = None
    if method == "wallet":
        phone = normalize_wallet(wallet_number or "")
        if not phone:
            raise PaymobError("A valid wallet number is needed")
    base = _base()
    amount_cents = round(invoice.amount_egp * 100)
    auth = await asyncio.to_thread(_post_json, f"{base}/api/auth/tokens", {"api_key": settings.PAYMOB_API_KEY}, {})
    token = auth.get("token")
    if not token:
        raise PaymobError("Paymob didn't return an auth token")
    order = await asyncio.to_thread(_post_json, f"{base}/api/ecommerce/orders", {
        "auth_token": token, "delivery_needed": False, "amount_cents": amount_cents, "currency": "EGP",
        "merchant_order_id": invoice.invoice_ref,
        "items": [{"name": f"Mizan {invoice.plan} ({invoice.billing_cycle})"[:50], "amount_cents": amount_cents,
                   "description": f"{tenant.name} — {invoice.invoice_ref}"[:255], "quantity": 1}],
    }, {})
    if not order.get("id"):
        raise PaymobError("Paymob didn't create an order")
    integration = settings.PAYMOB_CARD_INTEGRATION_ID if method == "card" else settings.PAYMOB_WALLET_INTEGRATION_ID
    key = await asyncio.to_thread(_post_json, f"{base}/api/acceptance/payment_keys", {
        "auth_token": token, "amount_cents": amount_cents, "expiration": PAYMENT_KEY_SECONDS, "order_id": order["id"],
        "billing_data": _billing_data(owner, phone), "currency": "EGP", "integration_id": int(integration),
        "lock_order_when_paid": True,
        "extra": {"invoice_ref": invoice.invoice_ref, "description": describe(invoice, tenant)},
    }, {})
    payment_key = key.get("token")
    if not payment_key:
        raise PaymobError("Paymob didn't return a payment key")
    if method == "card":
        url = f"{base}/api/acceptance/iframes/{settings.PAYMOB_IFRAME_ID.strip()}?payment_token={payment_key}"
    else:
        paid = await asyncio.to_thread(_post_json, f"{base}/api/acceptance/payments/pay", {
            "source": {"identifier": phone, "subtype": "WALLET"}, "payment_token": payment_key,
        }, {})
        url = paid.get("redirect_url") or paid.get("iframe_redirection_url")
        if not url:
            raise PaymobError("Paymob didn't return a wallet page")
    return {"checkout_url": url, "intention_id": None, "order_id": order["id"]}
