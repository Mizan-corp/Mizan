"""Anonymous read-only visitor pages (visitor runtime V1).

Design: docs/visitor-runtime-boundary-proposal.md + docs/visitor-runtime-v1-milestone.md.
Default disabled twice over: the server must be configured with PUBLIC_SITE_HOST
(the registered domain this deployment answers for), AND an enabled
site_activation row must exist for the exact (host, slug, page_path) triple.
Published trees only; consent and module activation are re-read on every
request; nothing is cached. No forms, search, accounts, cart, tracking or
checkout here.

Synthetic scope (allow_connected_data=false, the approved first exposure):
trees with ANY data binding/provider node (bindings/card/repeat) are refused,
every absolute URL in content must target the activation host itself, and the
theme comes from the activation row's own synthetic chrome - the tenant's
shared site_settings (business profile fields) are never read. The
private-preview consent (inventory_website_cards_v0) is not public-audience
consent and is never consulted on this route.
"""
import re
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db
from app.framework.activation import get_active_modules
from app.framework.storefront_runtime import SourceContext, SourceUnavailable, ProjectionInvalid
from app.platform.tenancy.context import current_tenant_id, bind_tenant

router = APIRouter(tags=["Public site pages"])

_HOST_RE = re.compile(r"[a-z0-9][a-z0-9.-]{0,252}")
_SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")
_ABS_URL_RE = re.compile(r"^(https?://|mailto:|tel:)", re.IGNORECASE)
_BOUND_KEYS = ("bindings", "card", "repeat")

# Anonymous rate limit: fixed window per (client IP, host). In-memory, so on
# serverless this is per-instance; it blunts abuse, it is not a global quota.
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = 60
_rate_hits: dict[str, list[float]] = {}

_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    # Renderer output verified against real render_document fixtures: escaped
    # HTML plus inline theme <style> blocks; images are https/same-origin only;
    # the only frames the manifest can emit are allow-listed YouTube/Maps embeds.
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' https:; "
        "frame-src https://www.youtube.com https://www.youtube-nocookie.com "
        "https://www.google.com https://maps.google.com; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
}


def _configured_host() -> str | None:
    """The registered public host from trusted server configuration (env), not
    from any client header. Empty means the visitor route is disabled here."""
    host = (settings.PUBLIC_SITE_HOST or "").strip().lower()
    return host if host and _HOST_RE.fullmatch(host) else None


def _public_host(request: Request) -> str | None:
    """Normalized exact host, or None when malformed. Ports, duplicates and
    odd encodings are rejected; client-supplied tenant hints
    (X-Forwarded-Host and friends) are never read."""
    host = (request.headers.get("host") or "").strip().lower()
    if not host or "," in host or ":" in host or not _HOST_RE.fullmatch(host):
        return None
    return host


def _rate_ok(key: str) -> bool:
    now = time.monotonic()
    hits = [t for t in _rate_hits.get(key, []) if now - t < _RATE_WINDOW_SECONDS]
    if len(hits) >= _RATE_MAX_REQUESTS:
        _rate_hits[key] = hits
        return False
    hits.append(now)
    _rate_hits[key] = hits
    return True


def _not_found() -> HTTPException:
    # One generic response for unknown host, unknown/disabled site, unknown,
    # draft or archived page: no existence oracle, no private reason.
    return HTTPException(404, "Not found")


def _unavailable() -> HTTPException:
    return HTTPException(503, "Unavailable")


def _has_bound_node(node) -> bool:
    """Any data binding/provider node anywhere in the tree."""
    if isinstance(node, dict):
        if any(k in node for k in _BOUND_KEYS):
            return True
        return any(_has_bound_node(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_bound_node(v) for v in node)
    return False


def _urls_stay_on_host(node, host: str) -> bool:
    """Every absolute URL in content must target the activation host itself;
    mailto/tel are refused outright. Relative paths and # anchors stay."""
    from urllib.parse import urlsplit

    if isinstance(node, str):
        if not _ABS_URL_RE.match(node):
            return True
        if not node.lower().startswith(("http://", "https://")):
            return False  # mailto: / tel:
        try:
            return urlsplit(node).hostname == host
        except ValueError:
            return False
    if isinstance(node, dict):
        return all(_urls_stay_on_host(v, host) for v in node.values())
    if isinstance(node, list):
        return all(_urls_stay_on_host(v, host) for v in node)
    return True


def _synthetic_ok(tree, host: str) -> bool:
    """The enforceable synthetic-content boundary: no data-binding/provider
    nodes and no absolute destinations outside the activation host."""
    return not _has_bound_node(tree) and _urls_stay_on_host(tree, host)


async def _activation(db: AsyncSession, host: str, slug: str, page_path: str):
    """Minimum unbound platform lookup: exactly one row keyed by the exact
    (host, slug, page_path) triple. One row per publishable page, so an
    unrelated published page in the same site is never servable through this
    route. Runs under the request-local bypass because no tenant is bound yet;
    the bypass is cleared before any tenant-scoped read."""
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    try:
        row = (await db.execute(text(
            "SELECT a.tenant_id AS tid, t.status AS tstatus, a.allow_connected_data AS allow_data,"
            " a.theme AS activation_theme"
            " FROM site_activation a JOIN tenants t ON t.id = a.tenant_id"
            " WHERE a.host = :h AND a.slug = :s AND a.page_path = :p AND a.enabled IS TRUE"
        ), {"h": host, "s": slug, "p": page_path})).first()
    finally:
        await db.execute(text("SELECT set_config('app.bypass', 'off', true)"))
    return row


async def _render_public(db: AsyncSession, page, settings_value: dict, tenant_id: uuid.UUID, canonical: str,
                         link_base: str | None = None, query: str | None = None,
                         lang_override: str | None = None) -> str:
    from app.framework.manifest import page_problems
    from app.platform.site import service
    from app.platform.site.render import render_document
    from app.platform.site.storefront.bindings import resolve_tree
    from app.platform.site.storefront.registry import scalar_registry, collection_registry
    from app.platform.site.storefront.repeats import has_repeat
    from app.platform.site.storefront.card_runtime import has_card, resolve_cards

    tree = page.published_tree
    titles = page.titles or {}
    languages = [k for k in titles.keys() if isinstance(k, str) and k] or ["en"]
    default_lang = "ar" if "ar" in languages else languages[0]
    lang = default_lang
    if isinstance(lang_override, str) and lang_override in languages:
        lang = lang_override

    await service.check_bound_tree(db, tree)
    ctx = SourceContext(tenant_id, lang, frozenset(await get_active_modules(db)), audience="public")
    if has_card(tree):
        resolved = await resolve_cards(db, tree, ctx)
    elif has_repeat(tree):
        from app.platform.site.storefront.composition import resolve_composition
        resolved = await resolve_composition(tree, scalar_registry(db), collection_registry(db), ctx, query=query)
    else:
        resolved = await resolve_tree(tree, scalar_registry(db), ctx, lambda t: page_problems(t, ("en", "ar")))
    meta = {"canonical": canonical, "titles": titles, "descriptions": {}, "languages": languages,
            "default_language": default_lang}
    return render_document(resolved, meta, settings_value if isinstance(settings_value, dict) else None,
                           lang=lang, link_base=link_base)


@router.api_route("/site/{slug}/{page_path}", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def public_page(slug: str, page_path: str, request: Request, db: AsyncSession = Depends(get_db)):
    host = _public_host(request)
    configured = _configured_host()
    # The request must have arrived through the registered domain this
    # deployment is configured for; a matching Host alone is never enough.
    if host is None or configured is None or host != configured:
        raise _not_found()
    if not _SLUG_RE.fullmatch(slug) or not _SLUG_RE.fullmatch(page_path):
        raise _not_found()
    client = request.client.host if request.client else "unknown"
    if not _rate_ok(f"{client}:{host}"):
        raise _not_found()

    row = await _activation(db, host, slug, page_path)
    if row is None or row.tstatus != "active":
        raise _not_found()

    try:
        await bind_tenant(db, row.tid)
        page = (await db.execute(text(
            "SELECT slug, titles, published_tree FROM site_pages"
            " WHERE slug = :p AND status = 'published' AND published_tree IS NOT NULL"
        ), {"p": page_path})).first()
        if page is None:
            raise _not_found()
        if row.allow_data:
            # Connected scope: same activation-snapshot theme as synthetic. The
            # approval time snapshot is the public theme; the tenant's shared
            # site_settings are never read on this anonymous route.
            theme = row.activation_theme if isinstance(row.activation_theme, dict) else {}
        else:
            # Synthetic scope: enforceable boundary - no bound/provider nodes, no
            # off-host destinations, and chrome only from the activation row's own
            # synthetic theme. Shared business profile settings are never read.
            if not _synthetic_ok(page.published_tree, host):
                raise _not_found()
            theme = row.activation_theme if isinstance(row.activation_theme, dict) else {}
        try:
            html = await _render_public(
                db, page, theme, row.tid,
                f"https://{host}/site/{slug}/{page_path}",
                link_base=f"/site/{slug}",
                query=request.query_params.get("q"),
                lang_override=request.query_params.get("lang"),
            )
        except (SourceUnavailable, ProjectionInvalid, ValueError):
            raise _unavailable() from None
        return HTMLResponse(html, headers=_HEADERS)
    finally:
        current_tenant_id.set(None)
