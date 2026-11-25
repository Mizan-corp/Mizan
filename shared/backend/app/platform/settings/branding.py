"""Workspace branding: the canonical workspace logo.

The logo belongs to the workspace (StoreSetting "logo_url"), not to any one
surface: the ERP settings page, the website onboarding wizard and sites that
follow the workspace all read the same value. Upload validation matches the
site media library: declared image type, real image bytes, storage quota.
"""
from __future__ import annotations

import io
import logging

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.framework import files
from app.framework.storage import ensure_room

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB


async def read_image(db: AsyncSession, file: UploadFile):
    """An uploaded image, checked: type, size, storage quota, and that it really is an image."""
    from PIL import Image

    if (file.content_type or "").lower() not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Unsupported file type. Allowed types: JPEG, PNG, GIF, WebP.")
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "The file is empty.")
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "The file is larger than 5 MB.")
    await ensure_room(db, len(contents))  # storage quota (ADR-006 D3)
    try:
        Image.open(io.BytesIO(contents)).verify()
        img = Image.open(io.BytesIO(contents))
        img.load()
    except Exception:
        raise HTTPException(400, "The file is not a valid image.") from None
    return contents, img


async def upsert_setting(db: AsyncSession, key: str, value) -> None:
    from app.platform.settings.models import StoreSetting
    row = (await db.execute(select(StoreSetting).where(StoreSetting.key == key))).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(StoreSetting(key=key, value=value))


async def get_workspace_logo(db: AsyncSession) -> str:
    from app.platform.settings.models import StoreSetting
    row = (await db.execute(select(StoreSetting).where(StoreSetting.key == "logo_url"))).scalar_one_or_none()
    return row.value if row and isinstance(row.value, str) else ""


async def store_workspace_logo(db: AsyncSession, file: UploadFile) -> dict:
    """Store the workspace's logo and square PWA icons made from it (#114).

    Honest about partial failure: a storage outage surfaces as 503 and nothing
    is committed, so the caller can retry the same upload safely.
    """
    from PIL import Image

    contents, img = await read_image(db, file)
    try:
        logo_url = await files.store(db, contents, kind="logo", filename=file.filename,
                                     content_type=file.content_type)
    except HTTPException as exc:
        if exc.status_code == 503:
            raise HTTPException(503, "File storage is not configured on this server. Contact support.") from exc
        raise
    icons: dict[str, str] = {}
    try:
        w, h = img.size
        side = min(w, h)
        square = img.crop(((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side))
        for size in (192, 512):
            buf = io.BytesIO()
            square.resize((size, size), Image.LANCZOS).save(buf, "PNG")
            icons[str(size)] = await files.store(db, buf.getvalue(), kind="logo_icon", owner_id=str(size),
                                                 filename="icon.png", content_type="image/png")
    except Exception:
        logger.warning("could not make PWA icons from the logo", exc_info=True)
    await upsert_setting(db, "logo_url", logo_url)
    for size, url in icons.items():
        await upsert_setting(db, f"logo_icon_{size}", url)
    await db.commit()
    return {"logo_url": logo_url}
