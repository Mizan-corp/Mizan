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


@pages_router.get("/{page_id}/public-access")
async def get_public_access(page_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_perm("site.manage"))):
    """Anonymous-access state for this page on the deployment's public host."""
    return await service.get_public_access(db, page_id)


@pages_router.put("/{page_id}/public-access")
async def put_public_access(page_id: uuid.UUID, data: service.PublicAccessIn,
                            db: AsyncSession = Depends(get_db),
                            user: User = Depends(require_perm("site.manage"))):
    """Synthetic scope only: pins allow_connected_data=False and the
    deployment's own configured host; see service.set_public_access."""
    return await service.set_public_access(db, page_id, enabled=data.enabled, user_id=user.id)


@pages_router.put("/{page_id}/connected-data-access")
async def put_connected_data_access(page_id: uuid.UUID, data: service.ConnectedAccessIn,
                                    db: AsyncSession = Depends(get_db),
                                    user: User = Depends(require_perm("site.manage"))):
    """The separately approved connected-data scope: dry-runs the published
    tree through the trusted registries and module consent machinery, then
    pins allow_connected_data=True with the exact approved source set. The
    ordinary availability toggle never manages these rows."""
    return await service.set_connected_data_access(db, page_id, enabled=data.enabled,
                                                   user_id=user.id,
                                                   audience_version=data.audience_version)


class SettingsIn(BaseModel):
    value: dict
    expected_token: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


@settings_router.get("")
async def get_settings(db: AsyncSession = Depends(get_db), user: User = Depends(require_perm("site.manage"))):
    """The workspace's durable theme and chrome; {} when never saved. `resolved` and
    `base` are read-only views for previews: what visitors get (the workspace theme
    base merged under the stored settings for follow-workspace sites) and the base
    alone, so the studio canvas matches the served page without editing the stored doc."""
    value = await service.get_settings(db)
    return {"value": value, "resolved": await service.resolved_settings(db),
            "base": await service.workspace_theme_base(db),
            "edit_token": service.settings_token(value)}


@settings_router.put("")
async def put_settings(data: SettingsIn, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("site.manage"))):
    value = await service.put_settings(db, value=data.value, expected_token=data.expected_token)
    return {"value": value, "resolved": await service.resolved_settings(db),
            "base": await service.workspace_theme_base(db),
            "edit_token": service.settings_token(value)}


# Combined router: mounts pages and settings routes under the same site API.
router = APIRouter()
router.include_router(pages_router)
router.include_router(settings_router)

# Experimental authenticated provider discovery and native preview.
from .storefront.router import router as storefront_data_router
router.include_router(storefront_data_router)

# Explicit reviewed website settings, each retaining its module permission.
from app.platform.core.storefront.router import router as core_website_router
from app.activities.general.modules.inventory.storefront.router import router as inventory_website_router
router.include_router(core_website_router)
router.include_router(inventory_website_router)

# Authenticated fixed first-party draft page sets.
from .page_kits_router import router as page_kits_router
router.include_router(page_kits_router)

# Site media library (studio image upload/list/delete).
from .media import media_router
router.include_router(media_router)
