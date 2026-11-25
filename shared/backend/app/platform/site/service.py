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
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework.manifest import page_problems, page_url
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
    from app.framework.storefront_runtime import SourceContext, SourceUnavailable
    from .storefront.registry import scalar_registry, collection_registry, item_resolver
    from .storefront.bindings import validate_tree_bindings
    try:
        context=SourceContext(current_tenant_id.get(), 'en', frozenset(await get_active_modules(db)))
        from .storefront.repeats import has_repeat
        from .storefront.card_runtime import has_card, card_plan
        if has_card(tree):
            card_plan(tree, scalar_registry(db), context, item_resolver(db))
        elif has_repeat(tree):
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
            "SELECT allow_connected_data, approved_sources FROM site_activation"
            " WHERE host = :h AND slug = :s AND page_path = :p AND enabled IS TRUE"
        ), {"h": _host, "s": PUBLIC_SITE_SLUG, "p": page.slug})).first()
        if row is not None and not row.allow_connected_data:
            raise HTTPException(409, "This page is public in synthetic scope, which cannot serve connected data. "
                                "Disable public access first, then publish again; the previously published page is unchanged.")
        if row is not None and row.allow_connected_data:
            # Managed connected activation: republishing is fine while the new
            # tree stays inside the owner-approved source set. Widening what
            # anonymous visitors can read needs a fresh explicit approval, so
            # the publish is refused BEFORE any mutation.
            approved = set(row.approved_sources or [])
            widened = sorted(set(bound_sources(page.draft_tree)) - approved)
            if widened:
                raise HTTPException(409, "The edited page reads data sources beyond the approved public set ("
                                + ", ".join(widened) + "). Re-approve connected-data access to widen it; "
                                "the previously published page is unchanged.")
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
COLOR_TOKENS = {"background", "foreground", "card", "primary", "primary-foreground", "dark", "dark-foreground", "dark-raised"}
HEADER_ICON_NAMES = ("whatsapp", "cart", "heart", "user", "phone", "globe", "search")
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
        logo = header.get("logo")
        if logo is not None and logo != "":
            if (not isinstance(logo, str) or logo != logo.strip() or len(logo) > 300
                    or not logo.startswith(("/", "https://")) or not page_url(logo, "url")):
                raise HTTPException(422, "شعار الموقع غير صالح")
        out["header"] = {"brand": (brand or "").strip(),
                         "links": _check_links(header.get("links"), 8),
                         "actions": _check_links(header.get("actions"), 4)}
        if logo:
            out["header"]["logo"] = logo
        if "layout" in header:
            if header["layout"] not in ("inline", "centered"):
                raise HTTPException(422, "Invalid header layout")
            out["header"]["layout"] = header["layout"]
        if "surface" in header:
            if header["surface"] not in ("default", "dark"):
                raise HTTPException(422, "Invalid header surface")
            out["header"]["surface"] = header["surface"]
        if "search_enabled" in header:
            if not isinstance(header["search_enabled"], bool):
                raise HTTPException(422, "بحث الترويسة غير صالح")
            out["header"]["search_enabled"] = header["search_enabled"]
        search_target = header.get("search_target")
        if search_target is not None and search_target != "":
            if (not isinstance(search_target, str) or len(search_target) > 200
                    or not search_target.startswith("/") or not page_url(search_target, "href")):
                raise HTTPException(422, "وجهة بحث الترويسة غير صالحة")
            out["header"]["search_target"] = search_target
        search_placeholder = header.get("search_placeholder")
        if search_placeholder is not None:
            if not isinstance(search_placeholder, str) or len(search_placeholder.strip()) > 80:
                raise HTTPException(422, "نص بحث الترويسة غير صالح")
            out["header"]["search_placeholder"] = search_placeholder.strip()
        for field, allowed in (("search_style", ("filled", "outline")),
                               ("bar_style", ("pills", "plain")),
                               ("density", ("comfortable", "compact")),
                               ("row_align", ("start", "center", "end", "between", "around", "evenly")),
                               ("row_gap", ("tight", "wide"))):
            chosen = header.get(field)
            if chosen is not None:
                if chosen not in allowed:
                    raise HTTPException(422, "شكل الترويسة غير صالح")
                out["header"][field] = chosen
        gap_px = header.get("gap_px")
        if gap_px is not None:
            if type(gap_px) is not int or not 0 <= gap_px <= 64:
                raise HTTPException(422, "شكل الترويسة غير صالح")
            out["header"]["gap_px"] = gap_px
        for dev in ("tablet", "mobile"):
            sub = header.get(dev)
            if sub is None:
                continue
            if not isinstance(sub, dict) or any(k not in ("density", "hide_search", "hide_bar") for k in sub):
                raise HTTPException(422, "شكل الترويسة غير صالح")
            cleaned = {}
            d = sub.get("density")
            if d is not None:
                if d not in ("comfortable", "compact"):
                    raise HTTPException(422, "شكل الترويسة غير صالح")
                cleaned["density"] = d
            for key in ("hide_search", "hide_bar"):
                v = sub.get(key)
                if v is not None:
                    if type(v) is not bool:
                        raise HTTPException(422, "شكل الترويسة غير صالح")
                    if v:
                        cleaned[key] = True
            if cleaned:
                out["header"][dev] = cleaned
        order = header.get("element_order")
        if order is not None:
            if (not isinstance(order, list) or len(order) > 3
                    or any(t not in ("brand", "search", "icons") for t in order)
                    or len(set(order)) != len(order)):
                raise HTTPException(422, "ترتيب الترويسة غير صالح")
            if order:
                out["header"]["element_order"] = list(order)
        icons = header.get("icons")
        if icons is not None:
            if not isinstance(icons, list) or len(icons) > 6:
                raise HTTPException(422, "أيقونات الترويسة غير صالحة")
            checked_icons = []
            for entry in icons:
                if not isinstance(entry, dict) or entry.get("icon") not in HEADER_ICON_NAMES:
                    raise HTTPException(422, "أيقونات الترويسة غير صالحة")
                pair = _check_links([{"label": entry.get("label"), "href": entry.get("href")}], 1)
                if not pair:
                    raise HTTPException(422, "أيقونات الترويسة غير صالحة")
                checked_icons.append({"icon": entry["icon"], "label": pair[0]["label"], "href": pair[0]["href"]})
            out["header"]["icons"] = checked_icons
        if "bar_links" in header:
            out["header"]["bar_links"] = _check_links(header.get("bar_links"), 12)
        cta_label = header.get("bar_cta_label")
        if cta_label is not None:
            if not isinstance(cta_label, str) or len(cta_label.strip()) > 40:
                raise HTTPException(422, "زر شريط الترويسة غير صالح")
            if cta_label.strip():
                out["header"]["bar_cta_label"] = cta_label.strip()
        cta_href = header.get("bar_cta_href")
        if cta_href is not None and cta_href != "":
            if not isinstance(cta_href, str) or not page_url(cta_href, "href"):
                raise HTTPException(422, "رابط زر شريط الترويسة غير صالح")
            out["header"]["bar_cta_href"] = cta_href
    footer = value.get("footer")
    if footer is not None:
        if not isinstance(footer, dict):
            raise HTTPException(422, "تذييل الموقع غير صالح")
        lines = footer.get("lines") or []
        if not isinstance(lines, list) or len(lines) > 4 or any(
                not isinstance(x, str) or not x.strip() or len(x) > 120 for x in lines):
            raise HTTPException(422, "تذييل الموقع غير صالح")
        out["footer"] = {"lines": [x.strip() for x in lines], "links": _check_links(footer.get("links"), 8)}
        groups = footer.get("groups")
        if groups is not None:
            if not isinstance(groups, list) or len(groups) > 4:
                raise HTTPException(422, "تذييل الموقع غير صالح")
            checked_groups = []
            for group in groups:
                if not isinstance(group, dict):
                    raise HTTPException(422, "تذييل الموقع غير صالح")
                title = group.get("title")
                if (not isinstance(title, str) or not title.strip()
                        or len(title) > 40 or title != title.strip()):
                    raise HTTPException(422, "تذييل الموقع غير صالح")
                checked_groups.append({"title": title, "links": _check_links(group.get("links"), 6)})
            if checked_groups:
                out["footer"]["groups"] = checked_groups
        if "layout" in footer:
            if footer["layout"] not in ("split", "stacked"):
                raise HTTPException(422, "Invalid footer layout")
            out["footer"]["layout"] = footer["layout"]
    follow = value.get("follow_workspace")
    if follow is not None:
        if not isinstance(follow, bool):
            raise HTTPException(422, "إعدادات الموقع غير صالحة")
        out["follow_workspace"] = follow
    unknown = set(value) - {"colors", "typography", "shape", "header", "footer", "follow_workspace"}
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
    connected = False
    sources: list = []
    if host:
        row = (await db.execute(text(
            "SELECT enabled, allow_connected_data, approved_sources FROM site_activation"
            " WHERE host = :h AND slug = :s AND page_path = :p"
        ), {"h": host, "s": PUBLIC_SITE_SLUG, "p": page.slug})).first()
        enabled = bool(row and row.enabled)
        connected = bool(row and row.allow_connected_data)
        if connected and isinstance(row.approved_sources, list):
            sources = [s for s in row.approved_sources if isinstance(s, str)]
    return {"enabled": enabled, "host": host,
            "url": f"https://{host}/site/{PUBLIC_SITE_SLUG}/{page.slug}" if host and enabled else None,
            "connected_data": connected, "sources": sources}


class PublicAccessIn(BaseModel):
    # Deliberately the ONLY client-controlled field: the host comes from server
    # config, the slug is the fixed synthetic site slug, and connected data
    # stays pinned off; extra body fields are ignored by pydantic.
    enabled: bool


class ConnectedAccessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    # Explicit acknowledgement of the audience wording the client showed. The
    # writer only accepts the CURRENT wording version: a stale cached client
    # (older or missing acknowledgement) is refused, never silently upgraded.
    audience_version: str


# Current public-audience wording version for connected-data activation. Bump
# when the wording changes; clients acknowledging older text are refused.
AUDIENCE_POLICY_CONNECTED = "mizan.site-audience.connected-data.v1"


def _route_references(tree) -> dict[str, set[tuple[str, str]]]:
    """Route-parameterized reads a published tree performs, by URL segment kind.

    'p': v2 route item bindings (mode "route"), the URL item segment selects
    the record. 'c': v2 category card-repeat plans (category "route"), the URL
    category segment filters the list. Defensive shape handling matches
    bound_sources: anything unrecognized yields no reference; validation of
    the binding or plan itself happens in check_bound_tree / the dry-run."""
    found: dict[str, set[tuple[str, str]]] = {"p": set(), "c": set()}

    def visit(node) -> None:
        if isinstance(node, dict):
            bindings = node.get("bindings")
            if isinstance(bindings, dict):
                content = bindings.get("content")
                if isinstance(content, dict):
                    for fields in content.values():
                        if isinstance(fields, dict):
                            for binding in fields.values():
                                if isinstance(binding, dict) and binding.get("mode") == "route":
                                    module, source = binding.get("module"), binding.get("source")
                                    if isinstance(module, str) and isinstance(source, str):
                                        found["p"].add((module, source))
            for key in ("repeat", "card"):
                payload = node.get(key)
                if isinstance(payload, dict):
                    content = payload.get("content")
                    if isinstance(content, dict):
                        for plan in content.values():
                            if isinstance(plan, dict) and plan.get("category") == "route":
                                module, source = plan.get("module"), plan.get("source")
                                if isinstance(module, str) and isinstance(source, str):
                                    found["c"].add((module, source))
            for child in node.get("children") or []:
                visit(child)

    visit(tree)
    return found


# Public alias: the visitor router needs the same route-reference detection to
# decide whether a missing URL record warrants the generic unavailable notice.
route_references = _route_references


def bound_sources(tree) -> list[str]:
    """The sorted module.source pairs a tree reads, from scalar bindings, item
    bindings, repeat plans and card plans, in every language. Defensive shape
    handling: anything unrecognized simply yields no pair; validation of the
    binding itself happens in check_bound_tree / the resolve dry-run."""
    found: set[str] = set()

    def collect(payload) -> None:
        if isinstance(payload, dict):
            module, source = payload.get("module"), payload.get("source")
            if isinstance(module, str) and isinstance(source, str):
                found.add(f"{module}.{source}")

    def visit(node) -> None:
        if isinstance(node, dict):
            bindings = node.get("bindings")
            if isinstance(bindings, dict):
                content = bindings.get("content")
                if isinstance(content, dict):
                    for fields in content.values():
                        if isinstance(fields, dict):
                            for binding in fields.values():
                                collect(binding)
            for key in ("repeat", "card"):
                payload = node.get(key)
                if isinstance(payload, dict):
                    collect(payload)
                    content = payload.get("content")
                    if isinstance(content, dict):
                        for plan in content.values():
                            collect(plan)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(tree)
    return sorted(found)


async def set_connected_data_access(db: AsyncSession, page_id: uuid.UUID, *, enabled: bool,
                                    user_id: uuid.UUID | None = None,
                                    audience_version: str) -> dict:
    """The separately approved operation: anonymous access WITH connected data.

    Enabling requires a published page that actually reads business data and
    pins the exact module.source set being approved. The whole published tree
    is dry-run through the same trusted registries and module consent
    machinery the visitor runtime uses: any source that is not currently
    exposable (missing/revoked consent, inactive module, unpublished record)
    refuses the activation with the source's own reason. No bypass is
    introduced: allowlisting is the trusted registry plus each module's
    enforced consent. Disabling always works on a managed row and keeps the
    approved set for audit; re-enabling is a fresh approval here, never the
    ordinary toggle.
    """
    if audience_version != AUDIENCE_POLICY_CONNECTED:
        raise HTTPException(409, "Connected-data audience wording changed. Reload before continuing.")
    page = await get_page(db, page_id, locked=True)
    if page.status != "published" or page.published_tree is None:
        raise HTTPException(409, "Publish the page before changing connected-data access")
    host = _public_host()
    if enabled:
        if not _has_bound_node(page.published_tree):
            raise HTTPException(409, "This page reads no business data; use ordinary public access")
        sources = bound_sources(page.published_tree)
        problems = synthetic_scope_violations(page.published_tree, host, include_bound=False)
        if problems:
            raise HTTPException(422, "This page cannot be made public: it references " + ", ".join(problems))
        from app.framework.activation import get_active_modules
        from app.framework.storefront_runtime import SourceContext, SourceUnavailable
        from .storefront.registry import scalar_registry, collection_registry, item_resolver
        from .storefront.bindings import resolve_tree
        from .storefront.repeats import has_repeat
        from .storefront.card_runtime import has_card, resolve_cards
        await check_bound_tree(db, page.published_tree)
        ctx = SourceContext(current_tenant_id.get(), "en", frozenset(await get_active_modules(db)), audience="public")
        try:
            if has_card(page.published_tree):
                await resolve_cards(db, page.published_tree, ctx)
            elif has_repeat(page.published_tree):
                from .storefront.composition import resolve_composition
                await resolve_composition(page.published_tree, scalar_registry(db), collection_registry(db), ctx,
                                          item_resolver(db))
            else:
                await resolve_tree(page.published_tree, scalar_registry(db), ctx,
                                   lambda t: page_problems(t, LANGUAGES), item_resolver(db))
        except SourceUnavailable as exc:
            raise HTTPException(422, "A data source on this page is not currently exposable to the public: "
                                f"{exc}. Fix the module's website consent and selection, then approve again.") from None
        # Route-parameterized probe (gap register item 16): v2 route reads
        # resolve empty without a route item, so the dry-run above never
        # exercises them and their first real read used to happen at visitor
        # request time (this is how the over-full-row expansion failure
        # reached the visitor). Re-resolve the published tree once per real
        # currently-exposable record the route segment could name, so
        # record-driven failures refuse the approval here. A source with
        # nothing exposable is skipped: the visitor render is empty/hidden
        # by design then and there is nothing to probe.
        refs = _route_references(page.published_tree)
        if refs["p"] or refs["c"]:
            from .storefront.registry import route_probe
            sample = route_probe(db)
        for kind in ("p", "c"):
            keys: list[str] = []
            for module, source in sorted(refs[kind]):
                keys.extend(await sample(ctx, kind, module, source))
            for key in sorted(set(keys)):
                probe_ctx = SourceContext(current_tenant_id.get(), "en", ctx.active_modules,
                                          audience="public", route_item=key)
                try:
                    if has_card(page.published_tree):
                        await resolve_cards(db, page.published_tree, probe_ctx)
                    elif has_repeat(page.published_tree):
                        from .storefront.composition import resolve_composition
                        await resolve_composition(page.published_tree, scalar_registry(db), collection_registry(db),
                                                  probe_ctx, item_resolver(db))
                    else:
                        await resolve_tree(page.published_tree, scalar_registry(db), probe_ctx,
                                           lambda t: page_problems(t, LANGUAGES), item_resolver(db))
                except SourceUnavailable as exc:
                    raise HTTPException(422, "This page's dynamic template fails when a real published record "
                                        f"loads through its URL: {exc}. Fix the template or the module's website "
                                        "consent and selection, then approve again.") from None
        theme = await resolved_settings(db)
        await db.execute(text("""
            INSERT INTO site_activation (tenant_id, host, slug, page_path, enabled,
                                         allow_connected_data, theme, audience_policy_version,
                                         approved_sources, activated_by, created_at, updated_at)
            VALUES (:tid, :h, :s, :p, true, true, CAST(:theme AS jsonb), :apv,
                    CAST(:src AS jsonb), :uid, now(), now())
            ON CONFLICT (host, slug, page_path) DO UPDATE
            SET enabled = true, allow_connected_data = true, theme = CAST(:theme AS jsonb),
                audience_policy_version = :apv, approved_sources = CAST(:src AS jsonb),
                activated_by = :uid, updated_at = now()
        """), {"tid": current_tenant_id.get(), "h": host, "s": PUBLIC_SITE_SLUG,
               "p": page.slug, "theme": json.dumps(theme, ensure_ascii=False),
               "apv": AUDIENCE_POLICY_CONNECTED, "src": json.dumps(sources), "uid": user_id})
        await db.commit()
    else:
        await db.execute(text(
            "UPDATE site_activation SET enabled = false, updated_at = now()"
            " WHERE host = :h AND slug = :s AND page_path = :p AND allow_connected_data IS TRUE"
        ), {"h": host, "s": PUBLIC_SITE_SLUG, "p": page.slug})
        await db.commit()
    return await get_public_access(db, page_id)


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
    theme = await resolved_settings(db)
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
    theme = await resolved_settings(db)
    await db.execute(text(
        "UPDATE site_activation SET theme = CAST(:theme AS jsonb), updated_at = now()"
        " WHERE host = :h AND slug = :s AND page_path = :p"
    ), {"theme": json.dumps(theme, ensure_ascii=False), "h": host,
        "s": PUBLIC_SITE_SLUG, "p": page.slug})
    await db.commit()


async def refresh_activation_themes(db: AsyncSession) -> None:
    """Re-snapshot this workspace's settings into its activation rows on this
    deployment's host after the workspace theme or logo changes. Only sites that
    follow the workspace are touched: any other site's activation snapshot stays
    byte-identical until its own settings are saved. No-op without a configured host."""
    from app.core.config import settings
    host = (settings.PUBLIC_SITE_HOST or "").strip().lower()
    if not host:
        return
    if (await get_settings(db)).get("follow_workspace") is not True:
        return
    theme = await resolved_settings(db)
    await db.execute(text(
        "UPDATE site_activation SET theme = CAST(:theme AS jsonb), updated_at = now()"
        " WHERE host = :h AND slug = :s"
    ), {"theme": json.dumps(theme, ensure_ascii=False), "h": host, "s": PUBLIC_SITE_SLUG})
    await db.commit()


async def get_settings(db: AsyncSession) -> dict:
    res = await db.execute(select(SiteSettings).limit(1))
    row = res.scalars().first()
    return dict(row.value) if row else {}


def _radius_px(value) -> int | None:
    """Pack radius (\"0.625rem\") to the renderer's integer px, or None to omit."""
    if isinstance(value, str):
        try:
            if value.endswith("rem"):
                return max(0, min(64, round(float(value[:-3]) * 16)))
            if value.endswith("px"):
                return max(0, min(64, round(float(value[:-2]))))
        except ValueError:
            return None
    return None


async def _workspace_logo(db: AsyncSession) -> str:
    from app.platform.settings.branding import get_workspace_logo
    return await get_workspace_logo(db)


async def workspace_theme_base(db: AsyncSession) -> dict:
    """The workspace's resolved theme pack mapped onto the site renderer's v0 tokens,
    plus the workspace logo. Base layer for sites that follow the workspace."""
    from app.platform.themes import service as themes
    tid = current_tenant_id.get()
    tenant = await db.get(Tenant, tid) if tid else None
    if tenant is None:
        return {}
    pack = await themes.resolved(db, tenant)
    light = (pack.get("colors") or {}).get("light") or {}
    base: dict = {"colors": {"light": {t: light[t] for t in COLOR_TOKENS
                                        if isinstance(light.get(t), str) and HEX.fullmatch(light[t])}},
                  "typography": {"family": "sans-serif"}}
    radius = _radius_px(pack.get("radius"))
    if radius is not None:
        base["shape"] = {"radius": radius}
    logo = await _workspace_logo(db)
    if logo:
        base["header"] = {"brand": "", "links": [], "actions": [], "logo": logo}
    return base


def _merge_site_settings(base: dict, explicit: dict) -> dict:
    """Explicit site settings win over the workspace base, per token for colors and
    per key for the header (a site with no logo of its own inherits the workspace's)."""
    out = dict(base)
    if "colors" in explicit:
        light = {**(base.get("colors") or {}).get("light", {}),
                 **(explicit["colors"].get("light") or {})}
        out["colors"] = {"light": light}
    for key in ("typography", "shape"):
        if key in explicit:
            out[key] = explicit[key]
    if "header" in explicit:
        out["header"] = {**(base.get("header") or {}), **explicit["header"]}
    if "footer" in explicit:
        out["footer"] = explicit["footer"]
    return out


async def resolved_settings(db: AsyncSession) -> dict:
    """What visitors get. Sites that follow the workspace (the new-workspace default,
    opt-in otherwise) render the workspace theme and logo under their own overrides;
    other sites keep exactly their stored settings."""
    raw = await get_settings(db)
    if raw.get("follow_workspace") is not True:
        return raw
    return _merge_site_settings(await workspace_theme_base(db), raw)


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
