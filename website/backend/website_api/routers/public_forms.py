"""Visitor form submissions: the POST side of the form block (contact-form V1).

Same trust boundary as the visitor pages (public_pages.py): the exact host must
match the configured PUBLIC_SITE_HOST, an enabled site_activation row must exist
for the exact (host, slug, page_path) triple, and the page must be published.
On top of that the node id must resolve to an actual form block inside the
page's published tree - the URL path alone never authorizes a write - and the
posted keys must be exactly the fields that block had enabled, each length-capped
at the renderer's own limits. A hidden honeypot field ("website") answers bots
with a fake success and stores nothing.

Anonymous rate limit: a stricter fixed window than the page route, keyed per
(client IP, host, page, node). In-memory, so per-instance on serverless; it
blunts abuse, it is not a global quota.
"""
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.framework.manifest import PAGE_LANGUAGE, PAGE_NODE_ID
from app.platform.site.models import SiteFormSubmission
from app.platform.tenancy.context import bind_tenant, current_tenant_id

from .public_pages import _SLUG_RE, _activation, _configured_host, _not_found, _public_host

router = APIRouter(tags=["Public site forms"])

_FORM_RATE_WINDOW_SECONDS = 60
_FORM_RATE_MAX_REQUESTS = 10
_form_hits: dict[str, list[float]] = {}

# A rendered form posts a few short fields: under ~2.5 KB. Anything larger is
# not a visitor message; the bound is enforced on the declared length before
# the body is read at all.
_MAX_BODY_BYTES = 16384

# Server-side caps mirror the rendered maxlengths; email's is the RFC 5321
# address limit, the rest are the block schema's own content caps.
_FIELD_CAPS = {"name": 120, "email": 254, "phone": 40, "message": 2000}
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]+$")


def _form_rate_ok(key: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _form_hits.get(key, []) if now - t < _FORM_RATE_WINDOW_SECONDS]
    if len(hits) >= _FORM_RATE_MAX_REQUESTS:
        _form_hits[key] = hits
        return False
    hits.append(now)
    _form_hits[key] = hits
    return True


def _find_form(node, node_id: str):
    """The form block with this id anywhere in the published tree, or None."""
    if isinstance(node, dict):
        if node.get("type") == "form" and node.get("id") == node_id:
            return node
        for child in node.get("children") or []:
            found = _find_form(child, node_id)
            if found is not None:
                return found
    return None


def _enabled_fields(form_node: dict) -> list[str]:
    """Exactly the payload keys the rendered form can post: name/phone only when
    the block's desktop settings (the visitor route's single render) show them,
    email unless field_email is explicitly false, and message always."""
    settings = (form_node.get("settings") or {}).get("desktop") or {}
    fields = []
    if settings.get("field_name"):
        fields.append("name")
    if settings.get("field_email") is not False:
        fields.append("email")
    if settings.get("field_phone"):
        fields.append("phone")
    fields.append("message")
    return fields


@router.post("/forms/{slug}/{page_path}/{node_id}")
async def submit_form(slug: str, page_path: str, node_id: str, request: Request,
                      db: AsyncSession = Depends(get_db)):
    host = _public_host(request)
    configured = _configured_host()
    if host is None or configured is None or host != configured:
        raise _not_found()
    if not _SLUG_RE.fullmatch(slug) or not _SLUG_RE.fullmatch(page_path):
        raise _not_found()
    if not PAGE_NODE_ID.fullmatch(node_id):
        raise _not_found()
    # Cross-site POST boundary (CSP's form-action limits where OUR pages post;
    # it says nothing about who posts TO us). A browser form post always sends
    # Origin; a cross-site forgery carries the attacker's origin. Only the
    # activation host's own origin may submit. An absent Origin (curl, privacy
    # strips) still faces the rate limit, honeypot and exact-key validation.
    origin = request.headers.get("origin")
    if origin is not None and origin.strip().lower() not in (
            f"https://{configured}", f"http://{configured}"):
        raise _not_found()
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > _MAX_BODY_BYTES:
                raise _not_found()
        except ValueError:
            raise _not_found() from None
    client = request.client.host if request.client else "unknown"
    if not _form_rate_ok(f"{client}:{host}:{slug}:{page_path}:{node_id}"):
        raise _not_found()

    lang = request.query_params.get("lang")
    lang_suffix = ""
    if isinstance(lang, str) and PAGE_LANGUAGE.fullmatch(lang):
        lang_suffix = f"&lang={lang}"
    # Honeypot and malformed posts get the same redirect a real submission gets:
    # no signal back about what was rejected.
    sent_redirect = RedirectResponse(
        f"/site/{slug}/{page_path}?form_sent={node_id}{lang_suffix}", status_code=303)

    # The declared Content-Length above is only a fast pre-read rejection; it
    # can be absent (chunked) or understated. The real cap is enforced on the
    # streamed bytes themselves before the form is parsed.
    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > _MAX_BODY_BYTES:
            raise _not_found()
    request._body = bytes(received)
    try:
        posted = await request.form()
    except Exception:
        return sent_redirect
    if posted.get("website"):
        return sent_redirect

    row = await _activation(db, host, slug, page_path)
    if row is None or row.tstatus != "active":
        raise _not_found()

    try:
        await bind_tenant(db, row.tid)
        page = (await db.execute(text(
            "SELECT id, published_tree FROM site_pages"
            " WHERE slug = :p AND status = 'published' AND published_tree IS NOT NULL"
        ), {"p": page_path})).first()
        if page is None:
            raise _not_found()
        form_node = _find_form(page.published_tree, node_id)
        if form_node is None:
            raise _not_found()

        allowed = _enabled_fields(form_node)
        # Duplicated keys (email=x&email=y) are not a browser form's doing:
        # refuse them rather than guess which value the visitor meant.
        keys = [k for k, _ in posted.multi_items() if k != "website"]
        if len(set(keys)) != len(keys) or set(keys) != set(allowed):
            raise HTTPException(400, "Invalid form submission")
        payload = {}
        for key in allowed:
            value = posted.get(key)
            if not isinstance(value, str):
                raise HTTPException(400, "Invalid form submission")
            value = value.strip()[: _FIELD_CAPS[key]]
            if key in ("email", "message") and not value:
                raise HTTPException(400, "Invalid form submission")
            if key == "email" and not _EMAIL_RE.fullmatch(value):
                raise HTTPException(400, "Invalid form submission")
            payload[key] = value

        db.add(SiteFormSubmission(page_id=page.id, block_id=node_id, payload=payload))
        await db.commit()
        return sent_redirect
    finally:
        current_tenant_id.set(None)
