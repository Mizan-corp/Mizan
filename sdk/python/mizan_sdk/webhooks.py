"""Verifying Mizan's webhooks on your server.

Mizan POSTs JSON with headers Mizan-Event, Mizan-Delivery, Mizan-Timestamp and
Mizan-Signature: sha256=<hex HMAC-SHA256 of "<timestamp>.<raw body>" with your webhook secret>.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time


class WebhookError(Exception):
    pass


def verify_webhook(secret: str, body: bytes, timestamp: str, signature: str, tolerance: int = 300) -> dict:
    """The event as a dict, if the request really came from Mizan and is recent; WebhookError otherwise.
    Pass the raw request body (bytes), not re-encoded JSON."""
    try:
        age = abs(time.time() - int(timestamp))
    except (TypeError, ValueError):
        raise WebhookError("Missing or invalid Mizan-Timestamp") from None
    if age > tolerance:
        raise WebhookError("The webhook is too old (possible replay)")
    expected = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        raise WebhookError("Invalid Mizan-Signature")
    return json.loads(body)
