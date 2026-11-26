"""Authenticated readback for workspace uploads on the ERP origin.

The blanket StaticFiles /uploads mount made every recorded file - including
business documents (po_invoice) - anonymously fetchable by anyone who could
reach the ERP origin, protected only by unguessable random filenames. This
route replaces that mount:

- The workspace's CURRENT sign-in branding (the logo/cover the public
  /tenants/resolve bootstrap already hands out) stays anonymous, because the
  pre-login page legitimately embeds it. An old or unreferenced branding file
  no longer qualifies.
- Everything else requires an ERP session for the SAME workspace, a recorded
  workspace_files row, and - for business-document kinds - the owning
  module's permission (po_invoice needs `purchases`, like the records).

Unknown, unrecorded, non-current or cross-workspace paths all get the one
generic 404: no existence oracle. The website origin keeps its own anonymous
reference-policy router (website_api.routers.uploads); this route serves the
signed-in ERP and the pre-login sign-in page only.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.framework import files
from app.framework.files import WorkspaceFile

router = APIRouter(tags=["Workspace uploads"])

# t/{tenant uuid}/{kind}/{filename}; one level each, matching what the local
# backend writes (framework.files._prefix + random suffix).
_PATH = re.compile(r"^t/([0-9a-fA-F-]{36})/([a-z0-9_]{1,32})/([^/]{1,300})$")

# Sign-in page display kinds: anonymous ONLY while the file is the workspace's
# current sign-in branding (a StoreSetting value the public tenant-resolution
# bootstrap already exposes). Anything recorded but no longer current needs a
# session like every other file.
_BRANDING_KINDS = ("logo", "logo_icon", "cover")
_BRANDING_KEYS = ("logo_url", "logo_icon_192", "logo_icon_512", "login_cover_url")

# Business documents are not display assets: reading one needs the owning
# module's permission, like the records themselves.
_KIND_PERM = {"po_invoice": ("purchases",)}

_URL_PREFIX = "/uploads/"


async def _recorded_file(db: AsyncSession, tenant_id: str, url: str):
    """Unbound read of the one workspace_files row; bypass cleared immediately."""
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    try:
        return await db.scalar(select(WorkspaceFile).where(
            WorkspaceFile.tenant_id == tenant_id, WorkspaceFile.url == url))
    finally:
        await db.execute(text("SELECT set_config('app.bypass', 'off', true)"))


async def _is_current_branding(db: AsyncSession, tenant_id: str, url: str) -> bool:
    await db.execute(text("SELECT set_config('app.bypass', 'on', true)"))
    try:
        row = (await db.execute(text(
            "SELECT 1 FROM store_settings WHERE tenant_id = :t"
            " AND key = ANY(:keys) AND value = :u LIMIT 1"
        ), {"t": tenant_id, "keys": list(_BRANDING_KEYS), "u": url})).first()
        return row is not None
    finally:
        await db.execute(text("SELECT set_config('app.bypass', 'off', true)"))


async def _serve(db: AsyncSession, url: str, content_type: str | None):
    """The stored bytes whichever backend holds them (disk on site, database rows on serverless);
    reached only after the route's access gate. One generic 404 when absent."""
    res = await files.serve_file(db, url, content_type)
    if res is None:
        raise HTTPException(404, "Not found")
    return res


@router.get("/uploads/{path:path}")
async def serve_workspace_upload(path: str, request: Request, db: AsyncSession = Depends(get_db)):
    match = _PATH.match(path)
    if not match:
        raise HTTPException(404, "Not found")
    tenant_id, kind, _filename = match.groups()
    url = _URL_PREFIX + path
    row = await _recorded_file(db, tenant_id, url)
    if row is not None and kind in _BRANDING_KINDS and await _is_current_branding(db, tenant_id, url):
        return await _serve(db, url, row.content_type)

    # Everything else: an ERP session for the same workspace is required.
    from app.dependencies import get_current_user
    user = await get_current_user(request, None, db)  # 401 when there is no live session
    if user.tenant_id is None or str(user.tenant_id).lower() != tenant_id.lower():
        raise HTTPException(404, "Not found")  # never an oracle into another workspace
    perms = _KIND_PERM.get(kind)
    if perms:
        from app.platform.permissions.access import can
        if not can(user, *perms):
            raise HTTPException(404, "Not found")
    if row is None:
        raise HTTPException(404, "Not found")
    return await _serve(db, url, row.content_type)
