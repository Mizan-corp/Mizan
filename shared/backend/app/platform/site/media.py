"""Site media library: upload, list and delete the images a workspace uses in its
studio pages (the renderer's image/gallery blocks reference durable URLs; this is how
a tenant gets those URLs without leaving the platform).

Same storage service, allowed types and limits as product images
(app/framework/files.py): Vercel Blob when a token is configured, local disk
otherwise, and an honest 503 where neither exists. No storage provisioning is added
here. Every route needs site.manage; rows are workspace-scoped (TenantScoped + RLS),
and list/delete additionally filter the bound workspace explicitly.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.framework import files
from app.framework.files import WorkspaceFile
from app.platform.auth.models.user import User
from app.platform.site.models import SitePage, SiteSettings
from app.platform.tenancy.context import current_tenant_id

media_router = APIRouter(prefix="/site/media", tags=["Site media"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
KIND = "site_image"

# Real file signatures for the four allowed types. The declared Content-Type is a
# claim; the bytes are the evidence. Mismatch, truncation or anything else refuses.
_SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),  # + WEBP at offset 8, checked separately
}


def _signature_matches(data: bytes, content_type: str) -> bool:
    if content_type == "image/webp":
        return len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return any(data.startswith(sig) for sig in _SIGNATURES[content_type])


_PIL_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/gif": "GIF", "image/webp": "WEBP"}


def _decodes_as(data: bytes, content_type: str) -> bool:
    """Structural validation: the whole payload must parse as the declared image type,
    not only start with its signature. Truncated or appended-garbage files fail."""
    from io import BytesIO

    try:
        from PIL import Image
        with Image.open(BytesIO(data)) as img:
            img.verify()
            return img.format == _PIL_FORMATS[content_type]
    except Exception:
        return False


def _row(f: WorkspaceFile) -> dict:
    return {"id": str(f.id), "url": f.url, "size": f.size, "content_type": f.content_type,
            "name": f.name, "created_at": f.created_at.isoformat() if f.created_at else None}


@media_router.get("")
async def list_media(db: AsyncSession = Depends(get_db),
                     user: User = Depends(require_perm("site.manage"))):
    tid = current_tenant_id.get()
    rows = (await db.execute(
        select(WorkspaceFile)
        .where(WorkspaceFile.kind == KIND, WorkspaceFile.tenant_id == tid)
        .order_by(WorkspaceFile.created_at.desc()))).scalars().all()
    total = await db.scalar(
        select(func.coalesce(func.sum(WorkspaceFile.size), 0))
        .where(WorkspaceFile.tenant_id == tid))
    return {"items": [_row(r) for r in rows], "total_bytes": int(total or 0)}


@media_router.post("", status_code=201)
async def upload_media(file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("site.manage"))):
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Unsupported file type. Allowed types: JPEG, PNG, GIF, WebP.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "The file is empty.")
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "The file is larger than 5 MB.")
    if not _signature_matches(data, content_type) or not _decodes_as(data, content_type):
        raise HTTPException(400, "The file content does not match its declared type. Upload a valid image.")
    try:
        url = await files.store(db, data, kind=KIND, filename=file.filename,
                                content_type=content_type, owner_id=None, replace=False)
    except HTTPException as exc:
        if exc.status_code == 503:
            # The shared files service raises an Arabic 503 for ERP callers; the
            # studio surface reports the same honest state in English.
            raise HTTPException(503, "File storage is not configured on this server. Contact support.") from exc
        raise
    await db.commit()
    row = (await db.execute(select(WorkspaceFile).where(WorkspaceFile.url == url))).scalar_one()
    return _row(row)


@media_router.delete("/{file_id}", status_code=204)
async def delete_media(file_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("site.manage"))):
    tid = current_tenant_id.get()
    row = (await db.execute(
        select(WorkspaceFile).where(WorkspaceFile.id == file_id, WorkspaceFile.kind == KIND,
                                    WorkspaceFile.tenant_id == tid))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "File not found.")
    if await _in_use(db, tid, row.url):
        raise HTTPException(409, "This image is still used by a page or the site design. Remove that use first.")
    await files.remove(db, url=row.url)
    await db.commit()


async def _in_use(db: AsyncSession, tenant_id, url: str) -> bool:
    """True when anything durable of the workspace still references the URL: any draft
    or published page tree (every block kind and language variant, as stored JSON) or
    the site settings document (logo, theme, chrome). A deleted image must never leave
    a published page or the site chrome rendering a dead frame."""
    needle = f"%{url}%"
    pages = select(SitePage.id).where(
        SitePage.tenant_id == tenant_id,
        or_(cast(SitePage.draft_tree, Text).like(needle),
            cast(SitePage.published_tree, Text).like(needle)))
    if (await db.execute(pages)).first() is not None:
        return True
    settings_q = select(SiteSettings.id).where(
        SiteSettings.tenant_id == tenant_id,
        cast(SiteSettings.value, Text).like(needle))
    return (await db.execute(settings_q)).first() is not None
