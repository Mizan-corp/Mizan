"""Site pages (ADR-015 S2/S3): the studio's page list, drafts, publish and revisions.

Mounted by the framework loader from this module's manifest (kind: platform, like themes).
Every route needs the workspace permission this module declares (site.manage); rows are
workspace-scoped by the tenancy layer (TenantScoped + RLS).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.platform.auth.models.user import User
from app.platform.site import service

pages_router = APIRouter(prefix="/site/pages", tags=["Site pages"])
settings_router = APIRouter(prefix="/site/settings", tags=["Site settings"])


class PageIn(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    titles: dict[str, str]
    tree: dict | None = None


class DraftIn(BaseModel):
    tree: dict
    expected_token: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    titles: dict[str, str] | None = None


def _summary(page) -> dict:
    return {
        "id": str(page.id), "slug": page.slug, "titles": page.titles, "status": page.status,
        "has_draft": page.draft_tree is not None, "published": page.published_tree is not None,
        "created_at": page.created_at.isoformat() if page.created_at else None,
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
    }


def _detail(page) -> dict:
    return {**_summary(page), "draft_tree": page.draft_tree, "published_tree": page.published_tree, "edit_token": service.page_token(page)}


def _revision(rev) -> dict:
    return {
        "id": str(rev.id), "number": rev.number, "titles": rev.titles,
        "created_by": str(rev.created_by) if rev.created_by else None,
        "created_at": rev.created_at.isoformat() if rev.created_at else None,
    }


@pages_router.get("")
async def list_pages(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("site.manage"))):
    return {"items": [_summary(p) for p in await service.list_pages(db)]}


@pages_router.post("", status_code=201)
async def create_page(data: PageIn, db: AsyncSession = Depends(get_db),
                      user: User = Depends(require_perm("site.manage"))):
    page = await service.create_page(db, slug=data.slug, titles=data.titles, tree=data.tree)
    return _detail(page)


@pages_router.get("/{page_id}")
async def get_page(page_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                   user: User = Depends(require_perm("site.manage"))):
    return _detail(await service.get_page(db, page_id))


@pages_router.put("/{page_id}/draft")
async def save_draft(page_id: uuid.UUID, data: DraftIn, db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_perm("site.manage"))):
    """Save and autosave: the draft only (page-engine.md)."""
    return _detail(await service.save_draft(db, page_id, tree=data.tree, titles=data.titles, expected_token=data.expected_token))


@pages_router.post("/{page_id}/publish")
async def publish(page_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                  user: User = Depends(require_perm("site.manage"))):
    return _detail(await service.publish(db, page_id, user.id))


@pages_router.get("/{page_id}/revisions")
async def revisions(page_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    user: User = Depends(require_perm("site.manage"))):
    return {"items": [_revision(r) for r in await service.list_revisions(db, page_id)]}


@pages_router.post("/{page_id}/rollback/{revision_id}")
async def rollback(page_id: uuid.UUID, revision_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                   user: User = Depends(require_perm("site.manage"))):
    return _detail(await service.rollback(db, page_id, revision_id))


@pages_router.post("/{page_id}/archive")
async def archive(page_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                  user: User = Depends(require_perm("site.manage"))):
    return _summary(await service.archive(db, page_id))


@pages_router.post("/{page_id}/reopen")
async def reopen(page_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                 user: User = Depends(require_perm("site.manage"))):
    return _summary(await service.reopen(db, page_id))


class SettingsIn(BaseModel):
    value: dict


@settings_router.get("")
async def get_settings(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("site.manage"))):
    """The workspace's durable theme and chrome; {} when never saved."""
    return {"value": await service.get_settings(db)}


@settings_router.put("")
async def put_settings(data: SettingsIn, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("site.manage"))):
    return {"value": await service.put_settings(db, value=data.value)}


# Combined router: mounts pages and settings routes under the same site API.
router = APIRouter()
router.include_router(pages_router)
router.include_router(settings_router)
