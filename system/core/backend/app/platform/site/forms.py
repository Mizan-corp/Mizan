"""Website form submissions: the Website tab's inbox for visitor contact-form
messages.

Written by the anonymous public form endpoint (website_api public_forms.py)
under the activation gate; read here by the owning workspace only. Every route
needs site.manage and rows are workspace-scoped by the tenancy layer
(TenantScoped + RLS), the same boundary as the Website orders surface.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.auth.models.user import User
from app.platform.site.models import SiteFormSubmission, SitePage

forms_router = APIRouter(prefix="/site/forms", tags=["Site forms"])


def _submission(s: SiteFormSubmission, page_slug: str | None = None) -> dict:
    return {
        "id": str(s.id),
        "page_id": str(s.page_id),
        "page_slug": page_slug,
        "block_id": s.block_id,
        "payload": s.payload,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "read_at": s.read_at.isoformat() if s.read_at else None,
    }


@forms_router.get("/submissions")
async def list_submissions(
    page_id: uuid.UUID | None = Query(default=None),
    unread_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm("site.manage")),
):
    stmt = (select(SiteFormSubmission, SitePage.slug)
            .join(SitePage, SitePage.id == SiteFormSubmission.page_id)
            .order_by(SiteFormSubmission.created_at.desc())
            .limit(200))
    if page_id is not None:
        stmt = stmt.where(SiteFormSubmission.page_id == page_id)
    if unread_only:
        stmt = stmt.where(SiteFormSubmission.read_at.is_(None))
    rows = (await db.execute(stmt)).all()
    return {"submissions": [_submission(s, slug) for s, slug in rows]}


@forms_router.post("/submissions/{submission_id}/read")
async def mark_submission_read(
    submission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_perm("site.manage")),
):
    s = await db.get(SiteFormSubmission, submission_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Not found")
    if s.read_at is None:
        s.read_at = datetime.now(timezone.utc)
        s.read_by = user.id
        await db.commit()
    return _submission(s)
