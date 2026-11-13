"""Webhooks for community modules (ADR-007 D4).

`publish(db, event, data)` is called inside the transaction that made the change: it records a
delivery for every installed module subscribed to the event (and allowed it), so a change and its
event commit together and nothing is lost. `deliver_soon()` then tries them right away in a task
of its own; anything that fails is retried with backoff for about a day by the hourly scheduler
(`deliver_due`, .github/workflows/jobs.yml) and, on site, by the server.

A delivery is a POST of
  {"id", "event", "created_at", "workspace": {"id"}, "module", "data": {...}}
with headers Mizan-Event, Mizan-Delivery, Mizan-Timestamp and
  Mizan-Signature: sha256=<hex HMAC-SHA256 of "<timestamp>.<body>" with the webhook secret>.
Receivers should reject timestamps older than five minutes.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.community.models import WebhookDelivery

logger = logging.getLogger("mizan.community.webhooks")
BACKOFF = [timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30), timedelta(hours=2),
           timedelta(hours=6), timedelta(hours=12)]  # then it's given up (about a day in all)
TIMEOUT = 5


def _subscribed(module, event: str) -> bool:
    hooks = module.manifest.get("webhooks") or {}
    if event not in (hooks.get("events") or []) or not hooks.get("url"):
        return False
    return event.startswith("record.") or f"events:{event}" in (module.scopes or [])


async def publish(db: AsyncSession, event: str, data: dict, only_module: str | None = None) -> list[uuid.UUID]:
    """Record the event for subscribed modules (in the caller's transaction)."""
    from app.platform.community.service import installed
    from app.platform.tenancy.context import current_tenant_id

    try:
        modules = await installed(db)
    except Exception:  # never let a webhook problem break the change itself
        logger.exception("Couldn't look up community modules for %s", event)
        return []
    ids = []
    for m in modules:
        if (only_module and m.module_id != only_module) or not _subscribed(m, event):
            continue
        delivery_id = uuid.uuid4()
        payload = {"id": str(delivery_id), "event": event, "created_at": datetime.now(UTC).isoformat(),
                   "workspace": {"id": str(current_tenant_id.get())}, "module": m.module_id, "data": data}
        db.add(WebhookDelivery(id=delivery_id, module_id=m.module_id, event=event,
                               payload=json.loads(json.dumps(payload, default=str))))
        ids.append(delivery_id)
    return ids


def deliver_soon(ids: list[uuid.UUID]) -> None:
    """Try these deliveries now, after the caller's commit, without holding up its response."""
    if not ids:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def later():
        await asyncio.sleep(0.2)
        try:
            await deliver_due(ids=ids)
        except Exception:
            logger.exception("Webhook delivery failed")

    loop.create_task(later())


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def safe_url(url: str) -> bool:
    """HTTPS to a public address only (no localhost, private or link-local networks)."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


def _post(url: str, body: bytes, headers: dict) -> int:
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.status
    except urllib.error.HTTPError as e:
        return e.code


async def deliver_due(ids: list[uuid.UUID] | None = None, limit: int = 100) -> dict:
    """Send pending deliveries that are due (or the given ones), across workspaces."""
    from app.db.base import AsyncSessionLocal
    from app.platform.community.models import CommunityModule

    sent = failed = 0
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
        stmt = select(WebhookDelivery).where(WebhookDelivery.status == "pending")
        stmt = stmt.where(WebhookDelivery.id.in_(ids)) if ids else stmt.where(WebhookDelivery.next_attempt_at <= func.now())
        rows = list((await db.execute(stmt.order_by(WebhookDelivery.created_at).limit(limit))).scalars())
        for d in rows:
            m = await db.scalar(select(CommunityModule).where(CommunityModule.tenant_id == d.tenant_id,
                                                              CommunityModule.module_id == d.module_id))
            url = ((m.manifest.get("webhooks") or {}).get("url") if m else None) or ""
            d.attempts += 1
            if m is None or m.status != "active" or not m.webhook_secret:
                d.status, d.last_error = "failed", "The module was removed or has no webhook secret"
                failed += 1
                continue
            body = json.dumps(d.payload, ensure_ascii=False).encode()
            ts = str(int(time.time()))
            headers = {"Content-Type": "application/json", "User-Agent": "Mizan-Webhooks/1",
                       "Mizan-Event": d.event, "Mizan-Delivery": str(d.id), "Mizan-Timestamp": ts,
                       "Mizan-Signature": sign(m.webhook_secret, ts, body)}
            code, error = None, None
            if not await asyncio.to_thread(safe_url, url):
                error = "Webhook address must be HTTPS on a public host"
            else:
                try:
                    code = await asyncio.to_thread(_post, url, body, headers)
                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    error = str(e)[:300]
            d.last_status_code, d.last_error = code, error
            if code is not None and 200 <= code < 300:
                d.status, d.delivered_at = "delivered", datetime.now(UTC)
                sent += 1
            elif d.attempts > len(BACKOFF):
                d.status = "failed"
                failed += 1
            else:
                d.next_attempt_at = datetime.now(UTC) + BACKOFF[d.attempts - 1]
        await db.commit()
    return {"message": f"Webhooks: {sent} delivered, {failed} given up, {len(rows) - sent - failed} to retry",
            "items_processed": len(rows)}
