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

import json
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework.manifest import page_problems
from app.platform.site.models import SitePage, SitePageRevision

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


async def get_page(db: AsyncSession, page_id: uuid.UUID) -> SitePage:
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
        check_tree(tree)
        page.draft_tree = tree
    db.add(page)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "يوجد صفحة بهذا الرابط بالفعل") from None
    return page


async def save_draft(db: AsyncSession, page_id: uuid.UUID, *, tree: dict, titles: dict | None = None) -> SitePage:
    """Autosave and explicit save: the draft only, never the published tree."""
    page = await get_page(db, page_id)
    if page.status == "archived":
        raise HTTPException(409, "الصفحة مؤرشفة؛ أعد فتحها قبل التعديل")
    check_tree(tree)
    page.draft_tree = tree
    if titles is not None:
        page.titles = check_titles(titles)
    await db.commit()
    return page


async def publish(db: AsyncSession, page_id: uuid.UUID, user_id: uuid.UUID | None = None) -> SitePage:
    """Copy the draft to the published tree and write an immutable revision.

    Edge-cache purge (Cloudflare, ADR-015 D6) lands with the site service that serves the
    public pages; it is not part of this storage step.
    """
    page = await get_page(db, page_id)
    if page.draft_tree is None:
        raise HTTPException(409, "لا توجد مسودة للنشر")
    check_tree(page.draft_tree)
    number = await db.scalar(
        select(func.coalesce(func.max(SitePageRevision.number), 0) + 1).where(SitePageRevision.page_id == page.id)
    )
    db.add(SitePageRevision(page_id=page.id, number=number, tree=page.draft_tree, titles=page.titles,
                            created_by=user_id))
    page.published_tree = page.draft_tree
    page.status = "published"
    await db.commit()
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
    page = await get_page(db, page_id)
    revision = await db.get(SitePageRevision, revision_id)
    if revision is None or revision.page_id != page.id:
        raise HTTPException(404, "المراجعة غير موجودة")
    page.draft_tree = revision.tree
    page.titles = dict(revision.titles or page.titles)
    await db.commit()
    return page


async def archive(db: AsyncSession, page_id: uuid.UUID) -> SitePage:
    """Archive instead of delete (docs/MODULE_STANDARD.md); the public site stops serving
    the page, the draft and the revisions stay."""
    page = await get_page(db, page_id)
    page.status = "archived"
    await db.commit()
    return page


async def reopen(db: AsyncSession, page_id: uuid.UUID) -> SitePage:
    page = await get_page(db, page_id)
    if page.status != "archived":
        raise HTTPException(409, "الصفحة ليست مؤرشفة")
    page.status = "published" if page.published_tree is not None else "draft"
    await db.commit()
    return page
