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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.dependencies import require_perm
from app.framework import files
from app.framework.files import WorkspaceFile
from app.platform.auth.models.user import User
from app.platform.tenancy.context import current_tenant_id

media_router = APIRouter(prefix="/site/media", tags=["Site media"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024
KIND = "site_image"


def _row(f: WorkspaceFile) -> dict:
    return {"id": str(f.id), "url": f.url, "size": f.size, "content_type": f.content_type,
            "created_at": f.created_at.isoformat() if f.created_at else None}


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
        raise HTTPException(400, "نوع الملف غير مدعوم. الأنواع المسموحة: JPEG, PNG, GIF, WebP")
    data = await file.read()
    if not data:
        raise HTTPException(400, "الملف فارغ")
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "حجم الملف يتجاوز 5 ميجابايت")
    url = await files.store(db, data, kind=KIND, filename=file.filename,
                            content_type=content_type, owner_id=None, replace=False)
    await db.commit()
    row = (await db.execute(select(WorkspaceFile).where(WorkspaceFile.url == url))).scalar_one()
    return _row(row)


@media_router.delete("/{file_id}", status_code=204)
async def delete_media(file_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       user: User = Depends(require_perm("site.manage"))):
    row = (await db.execute(
        select(WorkspaceFile).where(WorkspaceFile.id == file_id, WorkspaceFile.kind == KIND,
                                    WorkspaceFile.tenant_id == current_tenant_id.get()))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "الملف غير موجود")
    await files.remove(db, url=row.url)
    await db.commit()
