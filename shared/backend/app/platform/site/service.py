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
from sqlalchemy import func, select
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
    from .storefront.provider import site_provider
    from .storefront.bindings import validate_tree_bindings
    try:
        context=SourceContext(current_tenant_id.get(), 'en', frozenset(await get_active_modules(db)))
        validate_tree_bindings(tree,ProviderRegistry((site_provider(db),)),context,lambda t:page_problems(t,LANGUAGES))
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
    # Authenticated preview is implemented first. Public site-service resolution
    # is not wired yet, so do not produce published pages that cannot render.
    def has_bindings(node):
        return "bindings" in node or any(has_bindings(c) for c in node.get("children", []))
    if has_bindings(page.draft_tree):
        raise HTTPException(409,"Dynamic pages are preview-only until public provider resolution is available.")
    number = await db.scalar(
        select(func.coalesce(func.max(SitePageRevision.number), 0) + 1).where(SitePageRevision.page_id == page.id)
    )
    db.add(SitePageRevision(page_id=page.id, number=number, tree=page.draft_tree, titles=page.titles,
                            created_by=user_id))
    page.published_tree = page.draft_tree
    page.status = "published"
    await db.commit()
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
