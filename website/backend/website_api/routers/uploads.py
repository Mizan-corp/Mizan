"""Public file serving for visitor pages: referenced public assets only.

The system API mounts the whole upload dir for its authenticated app. The
public host must never do that: business documents (purchase-order invoices)
share the same disk layout, and a blanket StaticFiles mount would expose them
to anonymous visitors who guess or learn a path.

Kind alone is not proof of public intent either: a workspace can hold a logo
it never published or a product image no listing consents to show. So this
route serves a file only when ALL of these hold:

1. the path is a well-formed tenant/kind/file triple;
2. a workspace_files row records the exact URL with a public site-asset kind
   (logo, logo_icon, cover, site_image, product_image);
3. the asset is referenced by the workspace's CURRENT public surface:
   - logo / logo_icon / cover: an enabled site_activation theme contains the
     URL on this deployment's configured host;
   - site_image: the published tree of a page with an enabled activation on
     this host contains the URL (drafts and settings do not publish it);
   - product_image: the inventory storefront's own exposure rules would show
     it right now - a v1+ display consent with show_image for the owning
     product, the product selected for website publication and active, and
     its stored image_url matching exactly.

Everything else - wrong shape, non-public kind, unrecorded URL, unreferenced
asset, missing file - gets the one generic 404: no existence oracle.

The lookups run under the request-local bypass because no tenant is bound
for anonymous requests; the bypass is cleared before any other work.
"""
from __future__ import annotations

import mimetypes
import os
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db

router = APIRouter()

# Kinds a public page is allowed to reference (see framework/files.py and
# platform/site/media.py), each still subject to the reference rule.
PUBLIC_KINDS = ("logo", "logo_icon", "cover", "site_image", "product_image")

_PATH = re.compile(r"^t/[0-9a-fA-F-]{36}/[a-z_]{1,32}/[A-Za-z0-9_.-]{1,120}$")


def _not_found() -> HTTPException:
    return HTTPException(404, "Not found")


async def _site_asset_referenced(db: AsyncSession, tid: str, host: str, url: str) -> bool:
    row = (
        await db.execute(
            text(
                "SELECT 1 FROM site_activation"
                " WHERE tenant_id = :t AND host = :h AND enabled IS TRUE"
                " AND strpos(theme::text, :u) > 0 LIMIT 1"
            ),
            {"t": tid, "h": host, "u": url},
        )
    ).first()
    return row is not None


async def _site_image_referenced(db: AsyncSession, tid: str, host: str, url: str) -> bool:
    row = (
        await db.execute(
            text(
                "SELECT 1 FROM site_pages p"
                " JOIN site_activation a ON a.tenant_id = p.tenant_id"
                "  AND a.host = :h AND a.page_path = p.slug AND a.enabled IS TRUE"
                " WHERE p.tenant_id = :t AND strpos(p.published_tree::text, :u) > 0 LIMIT 1"
            ),
            {"t": tid, "h": host, "u": url},
        )
    ).first()
    return row is not None


async def _product_image_public(db: AsyncSession, tid: str, owner_id: str | None, url: str) -> bool:
    """Mirrors the inventory storefront provider's exposure conditions."""
    try:
        owner = uuid.UUID(str(owner_id or ""))
    except (ValueError, TypeError):
        return False
    from app.activities.general.modules.inventory.models.product import Product
    from app.activities.general.modules.inventory.storefront import cards, provider
    from app.framework.activation import get_active_modules
    from app.framework.storefront_runtime import SourceContext
    from app.platform.settings.models import StoreSetting
    from sqlalchemy import select

    ctx = SourceContext(uuid.UUID(tid), "en", frozenset(await get_active_modules(db)))
    consent = await cards.display_consent(db, ctx)
    if consent is None or not consent["show_image"] or owner not in consent["products"]:
        return False
    raw = await db.scalar(
        select(StoreSetting.value).where(
            StoreSetting.tenant_id == uuid.UUID(tid), StoreSetting.key == provider.SETTING_KEY
        )
    )
    if owner not in provider.publication_ids(raw)["products"]:
        return False
    image_url = await db.scalar(
        select(Product.image_url).where(
            Product.tenant_id == uuid.UUID(tid), Product.id == owner, Product.is_active.is_(True)
        )
    )
    return image_url == url


async def _referenced_publicly(db: AsyncSession, tid: str, kind: str, owner_id: str | None, url: str) -> bool:
    host = (settings.PUBLIC_SITE_HOST or "").strip().lower()
    if not host:
        return False
    if kind in ("logo", "logo_icon", "cover"):
        return await _site_asset_referenced(db, tid, host, url)
    if kind == "site_image":
        return await _site_image_referenced(db, tid, host, url)
    if kind == "product_image":
        return await _product_image_public(db, tid, owner_id, url)
    return False


@router.get("/uploads/{path:path}")
async def public_upload(path: str, db: AsyncSession = Depends(get_db)):
    if not _PATH.fullmatch(path) or ".." in path:
        raise _not_found()
    tid, kind = path.split("/")[1], path.split("/")[2]
    if kind not in PUBLIC_KINDS:
        raise _not_found()
    url = f"/uploads/{path}"
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    try:
        row = (
            await db.execute(
                text("SELECT owner_id FROM workspace_files WHERE url = :url AND kind = :kind LIMIT 1"),
                {"url": url, "kind": kind},
            )
        ).first()
        referenced = (
            row is not None and await _referenced_publicly(db, tid, kind, row[0] if row else None, url)
        )
    finally:
        await db.execute(text("SELECT set_config('app.bypass', 'off', true)"))
    if not referenced:
        raise _not_found()
    root = os.path.realpath(settings.UPLOAD_DIR)
    full = os.path.realpath(os.path.join(root, path))
    if not full.startswith(root + os.sep) or not os.path.isfile(full):
        raise _not_found()
    return FileResponse(full, media_type=mimetypes.guess_type(full)[0] or "application/octet-stream")
