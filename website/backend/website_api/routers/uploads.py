"""Public file serving for visitor pages: site-asset kinds only.

The system API mounts the whole upload dir for its authenticated app. The
public host must never do that: business documents (purchase-order invoices)
share the same disk layout, and a blanket StaticFiles mount would expose them
to anonymous visitors who guess or learn a path. This route serves a file
only when a workspace_files row records the exact URL with a public
site-asset kind (logo, logo_icon, cover, product_image). Everything else -
wrong shape, non-public kind, unrecorded URL, missing file - gets the one
generic 404, like the public page route: no existence oracle.

The lookup runs under the request-local bypass because no tenant is bound
for anonymous requests; the bypass is cleared before any other work.
"""
from __future__ import annotations

import mimetypes
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import get_db

router = APIRouter()

# Kinds a public page is allowed to reference (see framework/files.py).
PUBLIC_KINDS = ("logo", "logo_icon", "cover", "product_image")

_PATH = re.compile(r"^t/[0-9a-fA-F-]{36}/[a-z_]{1,32}/[A-Za-z0-9_.-]{1,120}$")


def _not_found() -> HTTPException:
    return HTTPException(404, "Not found")


@router.get("/uploads/{path:path}")
async def public_upload(path: str, db: AsyncSession = Depends(get_db)):
    if not _PATH.fullmatch(path) or ".." in path:
        raise _not_found()
    kind = path.split("/")[2]
    if kind not in PUBLIC_KINDS:
        raise _not_found()
    url = f"/uploads/{path}"
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    try:
        row = (
            await db.execute(
                text("SELECT 1 FROM workspace_files WHERE url = :url AND kind = :kind LIMIT 1"),
                {"url": url, "kind": kind},
            )
        ).first()
    finally:
        await db.execute(text("SELECT set_config('app.bypass', 'off', true)"))
    if not row:
        raise _not_found()
    root = os.path.realpath(settings.UPLOAD_DIR)
    full = os.path.realpath(os.path.join(root, path))
    if not full.startswith(root + os.sep) or not os.path.isfile(full):
        raise _not_found()
    return FileResponse(full, media_type=mimetypes.guess_type(full)[0] or "application/octet-stream")
