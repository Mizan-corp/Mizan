"""Site pages: drafts, publish, revisions and rollback (ADR-015 step S2).

The studio autosaves drafts; only publish changes what the public renderer serves
(page-engine.md: "Autosave writes the draft only; nothing reaches the public site until
publish"). Every tree is validated by the one validator shared with the SDK
(app/framework/manifest.page_problems, ADR-016 D4) before it is stored.

Functions take the database session and plain values, do one business operation in one
transaction, and raise HTTPException with an Arabic message for the user
(docs/MODULE_STANDARD.md).
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework.manifest import page_problems
from app.platform.site.models import SitePage, SitePageRevision, SiteSettings
from app.platform.tenancy.context import current_tenant_id
from app.platform.tenancy.models import Tenant

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LANGUAGES = ("ar", "en")  # ADR-015 D7: Arabic and English first.
MAX_TREE_BYTES = 200_000  # the bound the studio's preview bridge enforces
MAX_REVISIONS = 50  # per page; the oldest stay (history is never rewritten)


def check_tree(tree) -> None:
    if not isinstance(tree, dict):
        raise HTTPException(422, "شجرة الصفحة غير صالحة")
    if len(json.dumps(tree, ensure_ascii=False).encode()) > MAX_TREE_BYTES:
        raise HTTPException(422, "الصفحة أكبر من الحد المسموح")
    problems = page_problems(tree, LANGUAGES)
    if problems:
        raise HTTPException(422, "شجرة الصفحة غير صالحة: " + problems[0])


async def check_bound_tree(db: AsyncSession, tree: dict) -> None:
    """Shape plus active trusted provider compatibility, before any page write."""
    check_tree(tree)
    from app.framework.activation import get_active_modules
    from app.framework.storefront_runtime import ProviderRegistry, SourceContext, SourceUnavailable
    from .storefront.registry import scalar_registry, collection_registry, item_resolver
    from .storefront.bindings import validate_tree_bindings
    try:
        context=SourceContext(current_tenant_id.get(), 'en', frozenset(await get_active_modules(db)))
        from .storefront.repeats import has_repeat, validate_repeat
        from .storefront.card_runtime import has_card, card_plan
        if has_card(tree):
            card_plan(tree, scalar_registry(db), context)
        elif has_repeat(tree):
            from app.framework.storefront_collections import CollectionRuntime
            from .storefront.collections import navigation_labels_provider
            from .storefront.composition import validate_composition
            validate_composition(tree,scalar_registry(db),collection_registry(db),context,item_resolver(db))
        else:
            validate_tree_bindings(tree,scalar_registry(db),context,lambda t:page_problems(t,LANGUAGES),item_resolver(db))
    except SourceUnavailable:
        raise HTTPException(422,"Page binding source is unavailable or incompatible.") from None


def check_titles(titles) -> dict:
    if not isinstance(titles, dict):
        raise HTTPException(422, "عناوين الصفحة غير صالحة")
    out = {}
    for lang, title in titles.items():
        if lang not in LANGUAGES or not isinstance(title, str) or not title.strip() or len(title) > 120:
            raise HTTPException(422, "عنوان الصفحة غير صالح")
        out[lang] = title.strip()
    if not out:
        raise HTTPException(422, "الصفحة تحتاج عنوانًا واحدًا على الأقل")
    return out


def check_slug(slug) -> str:
    if not isinstance(slug, str) or not SLUG.match(slug) or len(slug) > 80:
        raise HTTPException(422, "رابط الصفحة غير صالح (حروف وأرقام لاتينية صغيرة وشرطات فقط)")
    return slug


def page_token(page: SitePage) -> str:
    """Opaque snapshot token. Equality is checked only after a fresh locked read."""
    snapshot = {"id": str(page.id), "status": page.status, "titles": page.titles,
                "draft": page.draft_tree, "published": page.published_tree,
                "updated_at": page.updated_at.isoformat() if page.updated_at else None}
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


async def get_page(db: AsyncSession, page_id: uuid.UUID, *, locked: bool = False) -> SitePage:
    if locked:
        result = await db.execute(select(SitePage).where(SitePage.id == page_id)
                                  .with_for_update().execution_options(populate_existing=True))
        page = result.scalar_one_or_none()
    else:
        page = await db.get(SitePage, page_id)
    if page is None:
        raise HTTPException(404, "الصفحة غير موجودة")
    return page


async def list_pages(db: AsyncSession) -> list[SitePage]:
    res = await db.execute(select(SitePage).order_by(SitePage.created_at))
    return list(res.scalars())


async def create_page(db: AsyncSession, *, slug: str, titles: dict, tree: dict | None = None) -> SitePage:
    page = SitePage(slug=check_slug(slug), titles=check_titles(titles))
    if tree is not None:
        await check_bound_tree(db, tree)
        page.draft_tree = tree
    db.add(page)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "يوجد صفحة بهذا الرابط بالفعل") from None
    return page


async def save_draft(db: AsyncSession, page_id: uuid.UUID, *, tree: dict, titles: dict | None = None, expected_token: str | None = None) -> SitePage:
    """Autosave and explicit save: the draft only, never the published tree."""
    page = await get_page(db, page_id, locked=True)
    if expected_token is not None and expected_token != page_token(page):
        await db.rollback()
        raise HTTPException(409, "The page changed in another session. Your local edits were not saved.")
    if page.status == "archived":
        raise HTTPException(409, "الصفحة مؤرشفة؛ أعد فتحها قبل التعديل")
    await check_bound_tree(db, tree)
    page.draft_tree = tree
    if titles is not None:
        page.titles = check_titles(titles)
    await db.commit()
    # func.now() onupdate leaves updated_at expired; refresh it inside the session,
    # an expired-attribute read after commit is implicit IO and breaks under async.
    await db.refresh(page)
    return page


async def publish(db: AsyncSession, page_id: uuid.UUID, user_id: uuid.UUID | None = None) -> SitePage:
    """Copy the draft to the published tree and write an immutable revision.

    Edge-cache purge (Cloudflare, ADR-015 D6) lands with the site service that serves the
    public pages; it is not part of this storage step.
    """
    page = await get_page(db, page_id, locked=True)
    if page.draft_tree is None:
        raise HTTPException(409, "لا توجد مسودة للنشر")
    await check_bound_tree(db, page.draft_tree)
    # Bound (dynamic) trees: the visitor runtime resolves them per request under
    # an activation with allow_connected_data=True, which no current flow can
    # create (set_public_access pins False, and enabling it is a separate,
    # explicitly approved operation). A bound page therefore publishes freely
    # for authenticated preview, EXCEPT when an enabled activation already
    # covers it: the synthetic request-time boundary refuses bound trees, so
    # publishing would silently break a live public URL. Refuse that one case
    # with a readable error BEFORE any mutation, keeping the previous snapshot.
    from app.core.config import settings as _settings
    _host = (_settings.PUBLIC_SITE_HOST or "").strip().lower()
    if _host and _has_bound_node(page.draft_tree):
        row = (await db.execute(text(
            "SELECT 1 FROM site_activation"
            " WHERE host = :h AND slug = :s AND page_path = :p AND enabled IS TRUE"
        ), {"h": _host, "s": PUBLIC_SITE_SLUG, "p": page.slug})).first()
        if row is not None:
            raise HTTPException(409, "This page is public in synthetic scope, which cannot serve connected data. "
                                "Disable public access first, then publish again; the previously published page is unchanged.")
    # Synthetic-scope preflight: what publish would make publicly servable must pass
    # the visitor contract on this deployment's host. Refuses with a readable error
    # BEFORE any mutation, so a failed publish keeps the previous published snapshot.
    # Bound nodes are covered by the activation-aware check above, not here.
    if _host:
        problems = synthetic_scope_violations(page.draft_tree, _host, include_bound=False)
        if problems:
            raise HTTPException(422, "This page cannot be published for the public test host: it references "
                                + ", ".join(problems) + f". Public pages in synthetic scope only allow addresses on {_host} "
                                "or relative links. Replace or remove them and publish again; the previously published page is unchanged.")
    number = await db.scalar(
        select(func.coalesce(func.max(SitePageRevision.number), 0) + 1).where(SitePageRevision.page_id == page.id)
    )
    db.add(SitePageRevision(page_id=page.id, number=number, tree=page.draft_tree, titles=page.titles,
                            created_by=user_id))
    page.published_tree = page.draft_tree
    page.status = "published"
    await db.commit()
    # If this page is publicly activated, its activation theme is a snapshot of
    # the workspace settings; refresh it on publish so the ordinary
    # Save -> Publish flow updates content and chrome together. Enabled state,
    # the host/slug pinning and allow_connected_data=false are never touched.
    await _refresh_activation_theme(db, page)
    # func.now() onupdate leaves updated_at expired; refresh it inside the session,
    # an expired-attribute read after commit is implicit IO and breaks under async.
    await db.refresh(page)
    return page


async def list_revisions(db: AsyncSession, page_id: uuid.UUID) -> list[SitePageRevision]:
    await get_page(db, page_id)
    res = await db.execute(
        select(SitePageRevision).where(SitePageRevision.page_id == page_id).order_by(SitePageRevision.number.desc())
    )
    return list(res.scalars())


async def rollback(db: AsyncSession, page_id: uuid.UUID, revision_id: uuid.UUID) -> SitePage:
    """Copy a revision into the draft. The published tree changes only on the next publish
    (page-engine.md: "rollback copies a revision into the draft")."""
    page = await get_page(db, page_id, locked=True)
    revision = await db.get(SitePageRevision, revision_id)
    if revision is None or revision.page_id != page.id:
        raise HTTPException(404, "المراجعة غير موجودة")
    await check_bound_tree(db, revision.tree)
    page.draft_tree = revision.tree
    page.titles = dict(revision.titles or page.titles)
    await db.commit()
    # func.now() onupdate leaves updated_at expired; refresh it inside the session,
    # an expired-attribute read after commit is implicit IO and breaks under async.
    await db.refresh(page)
    return page


async def archive(db: AsyncSession, page_id: uuid.UUID) -> SitePage:
    """Archive instead of delete (docs/MODULE_STANDARD.md); the public site stops serving
    the page, the draft and the revisions stay."""
    page = await get_page(db, page_id, locked=True)
    page.status = "archived"
    await db.commit()
    # func.now() onupdate leaves updated_at expired; refresh it inside the session,
    # an expired-attribute read after commit is implicit IO and breaks under async.
    await db.refresh(page)
    return page


async def reopen(db: AsyncSession, page_id: uuid.UUID) -> SitePage:
    page = await get_page(db, page_id, locked=True)
    if page.status != "archived":
        raise HTTPException(409, "الصفحة ليست مؤرشفة")
    page.status = "published" if page.published_tree is not None else "draft"
    await db.commit()
    # func.now() onupdate leaves updated_at expired; refresh it inside the session,
    # an expired-attribute read after commit is implicit IO and breaks under async.
    await db.refresh(page)
    return page


HEX = re.compile(r"#[0-9a-fA-F]{6}")
COLOR_TOKENS = {"background", "foreground", "card", "primary", "primary-foreground"}
FONT_FAMILIES = ("sans-serif", "serif", "monospace")
MAX_SETTINGS_BYTES = 20_000


def _check_links(entries, limit: int) -> list:
    if entries is None:
        return []
    if not isinstance(entries, list) or len(entries) > limit:
        raise HTTPException(422, "روابط الموقع غير صالحة")
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise HTTPException(422, "روابط الموقع غير صالحة")
        label, href = entry.get("label"), entry.get("href")
        if (not isinstance(label, str) or not label.strip() or len(label) > 40
                or not isinstance(href, str) or not href.startswith(("#", "/", "https://")) or len(href) > 200):
            raise HTTPException(422, "روابط الموقع غير صالحة")
        out.append({"label": label.strip(), "href": href})
    return out


def check_settings(value) -> dict:
    """Validate and normalize the theme document: known keys only, same constraints the
    renderer enforces, so a stored value can never carry markup or CSS expressions."""
    if not isinstance(value, dict):
        raise HTTPException(422, "إعدادات الموقع غير صالحة")
    if len(json.dumps(value, ensure_ascii=False).encode()) > MAX_SETTINGS_BYTES:
        raise HTTPException(422, "إعدادات الموقع أكبر من الحد المسموح")
    out: dict = {}
    colors = value.get("colors")
    if colors is not None:
        if not isinstance(colors, dict) or not isinstance(colors.get("light"), dict):
            raise HTTPException(422, "ألوان الموقع غير صالحة")
        light = {k: v for k, v in colors["light"].items()
                 if k in COLOR_TOKENS and isinstance(v, str) and HEX.fullmatch(v)}
        out["colors"] = {"light": light}
    typography = value.get("typography")
    if typography is not None:
        if not isinstance(typography, dict) or typography.get("family") not in FONT_FAMILIES:
            raise HTTPException(422, "خط الموقع غير صالح")
        out["typography"] = {"family": typography["family"]}
    shape = value.get("shape")
    if shape is not None:
        radius = shape.get("radius") if isinstance(shape, dict) else None
        if not isinstance(radius, int) or isinstance(radius, bool) or not 0 <= radius <= 64:
            raise HTTPException(422, "حواف الموقع غير صالحة")
        out["shape"] = {"radius": radius}
    header = value.get("header")
    if header is not None:
        if not isinstance(header, dict):
            raise HTTPException(422, "ترويسة الموقع غير صالحة")
        brand = header.get("brand")
        if brand is not None and (not isinstance(brand, str) or len(brand.strip()) > 80):
            raise HTTPException(422, "اسم المتجر غير صالح")
        out["header"] = {"brand": (brand or "").strip(),
                         "links": _check_links(header.get("links"), 8),
                         "actions": _check_links(header.get("actions"), 4)}
        if "layout" in header:
            if header["layout"] not in ("inline", "centered"):
                raise HTTPException(422, "Invalid header layout")
            out["header"]["layout"] = header["layout"]
    footer = value.get("footer")
    if footer is not None:
        if not isinstance(footer, dict):
            raise HTTPException(422, "تذييل الموقع غير صالح")
        lines = footer.get("lines") or []
        if not isinstance(lines, list) or len(lines) > 4 or any(
                not isinstance(x, str) or not x.strip() or len(x) > 120 for x in lines):
            raise HTTPException(422, "تذييل الموقع غير صالح")
        out["footer"] = {"lines": [x.strip() for x in lines], "links": _check_links(footer.get("links"), 8)}
        if "layout" in footer:
            if footer["layout"] not in ("split", "stacked"):
                raise HTTPException(422, "Invalid footer layout")
            out["footer"]["layout"] = footer["layout"]
    unknown = set(value) - {"colors", "typography", "shape", "header", "footer"}
    if unknown:
        raise HTTPException(422, "إعدادات الموقع تحتوي مفاتيح غير معروفة")
    return out


# --- Public activation (visitor runtime, synthetic scope) ----------------------

# The anonymous visitor route serves /site/{slug}/{page_path} only when an
# enabled site_activation row exists for the exact (host, slug, page_path)
# triple (website_api/routers/public_pages.py). This is the scoped UI-driven
# form of that step: rows are pinned to the deployment's own configured host
# (PUBLIC_SITE_HOST from trusted server config, never a client header), the
# fixed synthetic test-site slug, and allow_connected_data=False. Connected
# business data exposure stays a manual, separately reviewed operation; this
# flow can never create it.
PUBLIC_SITE_SLUG = "studio"
_AUDIENCE_POLICY = "v1"
_BOUND_KEYS = ("bindings", "card", "repeat")


def _has_bound_node(node) -> bool:
    """Any data binding/provider node anywhere in the tree."""
    if isinstance(node, dict):
        if any(k in node for k in _BOUND_KEYS):
            return True
        return any(_has_bound_node(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_bound_node(v) for v in node)
    return False


_ABS_URL_RE = re.compile(r"^(https?://|mailto:|tel:)", re.IGNORECASE)


def _off_host_urls(node, host: str, out: list[str], limit: int = 3) -> None:
    """Collect absolute URLs the synthetic visitor contract refuses: mailto:/tel:
    outright, and http(s) URLs outside the activation host. Mirrors the request-time
    enforcement in website_api/routers/public_pages.py so publish/Make-public fail
    with a readable error instead of a silent public 404."""
    from urllib.parse import urlsplit
    if len(out) >= limit:
        return
    if isinstance(node, str):
        if not _ABS_URL_RE.match(node):
            return
        if not node.lower().startswith(("http://", "https://")):
            out.append(node.split(":", 1)[0] + ": links")
            return
        try:
            if urlsplit(node).hostname != host:
                out.append(node)
        except ValueError:
            out.append(node)
        return
    if isinstance(node, dict):
        for value in node.values():
            _off_host_urls(value, host, out, limit)
    elif isinstance(node, list):
        for value in node:
            _off_host_urls(value, host, out, limit)


def synthetic_scope_violations(tree, host: str, *, include_bound: bool = True) -> list[str]:
    """Readable reasons a tree cannot be publicly served in synthetic scope.

    include_bound=False is for publish(), which checks bound trees against the
    page's own activation state separately; Make-public keeps the default True.
    """
    problems: list[str] = []
    if include_bound and _has_bound_node(tree):
        problems.append("it reads business data (bound/provider nodes)")
    _off_host_urls(tree, host, problems)
    return problems


def _public_host() -> str:
    from app.core.config import settings
    host = (settings.PUBLIC_SITE_HOST or "").strip().lower()
    if not host:
        raise HTTPException(409, "This deployment has no public site host configured")
    return host


async def get_public_access(db: AsyncSession, page_id: uuid.UUID) -> dict:
    """Activation state for one page on this deployment's public host."""
    page = await get_page(db, page_id)
    from app.core.config import settings
    host = (settings.PUBLIC_SITE_HOST or "").strip().lower() or None
    enabled = False
    if host:
        row = (await db.execute(text(
            "SELECT enabled FROM site_activation"
            " WHERE host = :h AND slug = :s AND page_path = :p"
        ), {"h": host, "s": PUBLIC_SITE_SLUG, "p": page.slug})).first()
        enabled = bool(row and row.enabled)
    return {"enabled": enabled, "host": host,
            "url": f"https://{host}/site/{PUBLIC_SITE_SLUG}/{page.slug}" if host and enabled else None}


class PublicAccessIn(BaseModel):
    # Deliberately the ONLY client-controlled field: the host comes from server
    # config, the slug is the fixed synthetic site slug, and connected data
    # stays pinned off; extra body fields are ignored by pydantic.
    enabled: bool


async def set_public_access(db: AsyncSession, page_id: uuid.UUID, *, enabled: bool,
                            user_id: uuid.UUID | None = None) -> dict:
    """Enable or disable anonymous access to one published page, synthetic scope.

    Only published pages can be made reachable; disabling is always allowed.
    The activation theme snapshots the workspace's saved site settings so the
    public header/colors match what the studio's settings describe, without
    ever reading the tenant's shared settings at request time.
    """
    page = await get_page(db, page_id, locked=True)
    if enabled and (page.status != "published" or page.published_tree is None):
        raise HTTPException(409, "Publish the page before making it public")
    if enabled and _has_bound_node(page.published_tree):
        # publish() already refuses bound trees; this guards pages published
        # before that rule or through any other path. Synthetic scope serves
        # content only.
        raise HTTPException(409, "Pages that read business data cannot be made public in synthetic scope")
    host = _public_host()
    if enabled:
        # Fail-closed on managed rows (review F1): an activation row carrying
        # allow_connected_data=True can only come from a separately approved
        # operation. An ordinary availability toggle must not re-enable such a
        # row: that would expose connected data publicly without renewed scope.
        # Refuse instead of silently stripping the approved flag. Disabling is
        # unaffected and never touches the flag.
        existing = (await db.execute(text(
            "SELECT enabled, allow_connected_data FROM site_activation"
            " WHERE host = :h AND slug = :s AND page_path = :p"
        ), {"h": host, "s": PUBLIC_SITE_SLUG, "p": page.slug})).first()
        if existing is not None and existing.allow_connected_data:
            if existing.enabled:
                # Already public under the managed activation: refusing the
                # toggle changes nothing, so say exactly that - never claim
                # the page is private when it is not.
                raise HTTPException(409, "This address is public under a managed connected-data activation. "
                                    "The ordinary availability toggle cannot change a managed activation; its current state is unchanged.")
            raise HTTPException(409, "This address has a managed connected-data activation, currently disabled. "
                                "Re-enabling public access needs the separately approved operation; the ordinary toggle leaves it unchanged.")
        problems = synthetic_scope_violations(page.published_tree, host)
        if problems:
            raise HTTPException(422, "This page cannot be made public: it references " + ", ".join(problems)
                                + f". Public pages in synthetic scope only allow addresses on {host} or relative links. "
                                "Edit the page, publish it again, then make it public; it stays private meanwhile.")
    theme = await get_settings(db)
    await db.execute(text("""
        INSERT INTO site_activation (tenant_id, host, slug, page_path, enabled,
                                     allow_connected_data, theme, audience_policy_version,
                                     activated_by, created_at, updated_at)
        VALUES (:tid, :h, :s, :p, :en, false, CAST(:theme AS jsonb), :apv, :uid, now(), now())
        ON CONFLICT (host, slug, page_path) DO UPDATE
        SET enabled = :en, theme = CAST(:theme AS jsonb), audience_policy_version = :apv,
            activated_by = :uid, updated_at = now()
    """), {"tid": current_tenant_id.get(), "h": host, "s": PUBLIC_SITE_SLUG,
           "p": page.slug, "en": enabled, "theme": json.dumps(theme, ensure_ascii=False),
           "apv": _AUDIENCE_POLICY, "uid": user_id})
    await db.commit()
    return await get_public_access(db, page_id)


async def _refresh_activation_theme(db: AsyncSession, page) -> None:
    """Re-snapshot the workspace settings into this page's activation row, if
    one exists on this deployment's host. No-op without a configured host."""
    from app.core.config import settings
    host = (settings.PUBLIC_SITE_HOST or "").strip().lower()
    if not host:
        return
    theme = await get_settings(db)
    await db.execute(text(
        "UPDATE site_activation SET theme = CAST(:theme AS jsonb), updated_at = now()"
        " WHERE host = :h AND slug = :s AND page_path = :p"
    ), {"theme": json.dumps(theme, ensure_ascii=False), "h": host,
        "s": PUBLIC_SITE_SLUG, "p": page.slug})
    await db.commit()


async def get_settings(db: AsyncSession) -> dict:
    res = await db.execute(select(SiteSettings).limit(1))
    row = res.scalars().first()
    return dict(row.value) if row else {}


def settings_token(value: dict) -> str:
    """Tenant-bound content fingerprint, not a monotonic revision counter."""
    snapshot = {"tenant": str(current_tenant_id.get()), "value": value}
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


async def put_settings(db: AsyncSession, *, value: dict, expected_token: str | None = None) -> dict:
    """Serialize even first creation on the tenant row, then compare a fresh snapshot.

    Legacy callers may omit the token. Those writes are serialized but unconditional.
    Shared settings are live configuration, not a page draft or publish transaction.
    """
    clean = check_settings(value)
    tid = current_tenant_id.get()
    if tid is None:
        raise HTTPException(409, "Workspace context required for site settings")
    tenant = await db.execute(select(Tenant.id).where(Tenant.id == tid).with_for_update())
    if tenant.scalar_one_or_none() is None:
        raise HTTPException(404, "Workspace not found")
    res = await db.execute(select(SiteSettings).limit(1).with_for_update()
                           .execution_options(populate_existing=True))
    row = res.scalars().first()
    current = dict(row.value) if row else {}
    if expected_token is not None and expected_token != settings_token(current):
        raise HTTPException(409, "Shared site settings changed in another session. Local changes were not saved.")
    if row is None:
        row = SiteSettings(value=clean)
        db.add(row)
    else:
        row.value = clean
    await db.commit()
    await db.refresh(row)
    return dict(row.value)
