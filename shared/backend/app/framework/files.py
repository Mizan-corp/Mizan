"""Uploaded files (#114): one place that stores them, whatever the deployment.

- Cloud (Vercel): Vercel Blob, a public store; each file gets a random suffix, so its URL can't be
  guessed. The function's own disk isn't kept between requests, so without BLOB_READ_WRITE_TOKEN
  uploads are refused rather than silently lost.
- On-site installs and development: the local disk (UPLOAD_DIR), served at /uploads.

Private files (store_private/read_private; clinical images and signatures, #43/#44) are never
served by URL: on disk they go to PRIVATE_UPLOAD_DIR, which nothing mounts, and a route reads them
back after its own access checks. On Vercel Blob (a public store) they get an unguessable random
pathname that is never sent to a client.

Every file is recorded in workspace_files (its kind, what it belongs to, its size): the storage
quota counts real sizes, a replaced file is deleted, and a deleted workspace's files can be removed.
Kinds: logo, logo_icon (the PWA icons made from the logo), cover, product_image, po_invoice.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import BigInteger, DateTime, String, func, select, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.platform.tenancy.context import TenantScoped, current_tenant_id

log = logging.getLogger("files")

BLOB_API = "https://vercel.com/api/blob"
BLOB_API_VERSION = "11"
EXT = re.compile(r"^\.[a-z0-9]{1,8}$")


class WorkspaceFile(TenantScoped, Base):
    __tablename__ = "workspace_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # the product, order… it belongs to
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Backends ──────────────────────────────────────────────────────────────────────────────────

def _blob_token() -> str | None:
    return os.environ.get("BLOB_READ_WRITE_TOKEN") or None


def _blob_request(method: str, path: str, *, body: bytes | None = None, headers: dict | None = None) -> dict:
    token = _blob_token()
    req = urllib.request.Request(f"{BLOB_API}{path}", data=body, method=method, headers={
        "authorization": f"Bearer {token}", "x-api-version": BLOB_API_VERSION, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        log.error("blob %s %s failed: %s %s", method, path, e.code, detail)
        raise HTTPException(502, "تعذر حفظ الملف في التخزين. حاول مرة أخرى.") from None
    except urllib.error.URLError as e:
        log.error("blob %s %s unreachable: %s", method, path, e)
        raise HTTPException(502, "تعذر الوصول إلى تخزين الملفات. حاول مرة أخرى.") from None


class _Blob:
    async def put(self, pathname: str, data: bytes, content_type: str) -> str:
        query = urllib.parse.urlencode({"pathname": pathname})
        out = await asyncio.to_thread(_blob_request, "PUT", f"/?{query}", body=data, headers={
            "x-vercel-blob-access": "public", "x-add-random-suffix": "1", "x-content-type": content_type,
            "x-cache-control-max-age": str(60 * 60 * 24 * 365)})
        return out["url"]

    async def delete(self, urls: list[str]) -> None:
        if urls:
            await asyncio.to_thread(_blob_request, "POST", "/delete", body=json.dumps({"urls": urls}).encode(),
                                    headers={"content-type": "application/json"})

    async def delete_prefix(self, prefix: str) -> int:
        removed, cursor = 0, None
        while True:
            q = {"prefix": prefix, "limit": "1000", **({"cursor": cursor} if cursor else {})}
            page = await asyncio.to_thread(_blob_request, "GET", f"/?{urllib.parse.urlencode(q)}")
            urls = [b["url"] for b in page.get("blobs", [])]
            await self.delete(urls)
            removed += len(urls)
            cursor = page.get("cursor")
            if not page.get("hasMore") or not cursor:
                return removed


class _Disk:
    def _root(self) -> str:
        from app.core.config import settings

        return settings.UPLOAD_DIR

    async def put(self, pathname: str, data: bytes, content_type: str) -> str:
        stem, ext = os.path.splitext(pathname)
        name = f"{stem}-{uuid.uuid4().hex[:12]}{ext}"  # like Blob's random suffix: never overwrite, not guessable
        path = os.path.join(self._root(), name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        await asyncio.to_thread(_write, path, data)
        return f"/uploads/{name}"

    async def delete(self, urls: list[str]) -> None:
        for url in urls:
            if url.startswith("/uploads/") and ".." not in url:
                path = os.path.join(self._root(), url.removeprefix("/uploads/"))
                if os.path.isfile(path):
                    os.remove(path)

    async def delete_prefix(self, prefix: str) -> int:
        path = os.path.join(self._root(), prefix.rstrip("/"))
        if ".." in prefix or not os.path.isdir(path):
            return 0
        count = sum(len(f) for _, _, f in os.walk(path))
        shutil.rmtree(path, ignore_errors=True)
        return count


def _write(path: str, data: bytes) -> None:
    with open(path, "wb") as f:
        f.write(data)


PRIVATE = "private:"
_PRIVATE_KEY = re.compile(r"^private:(t/[0-9a-f-]{36}|platform)/[a-z_]{1,32}/[A-Za-z0-9_-]{1,80}\.[a-z0-9]{1,8}$")
_private_root: str | None = None


def _private_dir() -> str:
    """PRIVATE_UPLOAD_DIR, or a mirror under the temp dir where it isn't writable (like UPLOAD_DIR)."""
    global _private_root
    if _private_root is None:
        import tempfile

        from app.core.config import settings

        path = settings.PRIVATE_UPLOAD_DIR
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".wprobe")
            with open(probe, "w") as f:
                f.write("")
            os.remove(probe)
        except OSError:
            path = os.path.join(tempfile.gettempdir(), "mizan-private-uploads")
            os.makedirs(path, exist_ok=True)
        _private_root = path
    return _private_root


def _private_path(key: str) -> str:
    if not _PRIVATE_KEY.match(key):
        raise HTTPException(404, "الملف غير موجود")
    return os.path.join(_private_dir(), key.removeprefix(PRIVATE))


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def backend() -> _Blob | _Disk:
    if _blob_token():
        return _Blob()
    if os.environ.get("VERCEL"):
        # The function's disk is thrown away: a file written there would be lost.
        raise HTTPException(503, "تخزين الملفات غير مهيأ على الخادم. تواصل مع الدعم.")
    return _Disk()


def backend_name() -> str:
    return "blob" if _blob_token() else "disk"


# ── The service ───────────────────────────────────────────────────────────────────────────────

def _prefix(tenant_id) -> str:
    return f"t/{tenant_id}/" if tenant_id else "platform/"


async def store(db: AsyncSession, data: bytes, *, kind: str, filename: str | None, content_type: str,
                owner_id: str | None = None, replace: bool = True) -> str:
    """Save a file for the bound workspace and return its URL. With `replace`, the workspace's
    previous file of this kind for the same owner is deleted (a new logo replaces the old)."""
    tenant_id = current_tenant_id.get()
    ext = os.path.splitext((filename or "").lower())[1]
    if not EXT.match(ext):
        ext = ".bin"
    pathname = f"{_prefix(tenant_id)}{kind}/{owner_id or 'file'}{ext}"
    url = await backend().put(pathname, data, content_type)
    if replace:
        await remove(db, kind=kind, owner_id=owner_id)
    db.add(WorkspaceFile(kind=kind, owner_id=owner_id, url=url, size=len(data), content_type=content_type))
    return url


async def store_private(db: AsyncSession, data: bytes, *, kind: str, filename: str | None, content_type: str,
                        owner_id: str) -> str:
    """Save a file only an authenticated route will serve; returns its key (keep it in the record,
    never send it to a client). Read it back with read_private."""
    tenant_id = current_tenant_id.get()
    ext = os.path.splitext((filename or "").lower())[1]
    if not EXT.match(ext):
        ext = ".bin"
    stem = f"{_prefix(tenant_id)}{kind}/{re.sub(r'[^A-Za-z0-9_-]', '', owner_id)[:40]}-{uuid.uuid4().hex}"
    if _blob_token():
        url = await _Blob().put(f"private/{stem}{ext}", data, content_type)
        key = url  # an unguessable public-store URL; served only through the route
    else:
        if os.environ.get("VERCEL"):
            raise HTTPException(503, "تخزين الملفات غير مهيأ على الخادم. تواصل مع الدعم.")
        key = f"{PRIVATE}{stem}{ext}"
        path = _private_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        await asyncio.to_thread(_write, path, data)
    db.add(WorkspaceFile(kind=kind, owner_id=owner_id, url=key, size=len(data), content_type=content_type))
    return key


async def read_private(key: str) -> bytes:
    if key.startswith(PRIVATE):
        path = _private_path(key)
        if not os.path.isfile(path):
            raise HTTPException(404, "الملف غير موجود في التخزين")
        return await asyncio.to_thread(_read, path)
    if key.startswith("https://") and _blob_token():
        def fetch() -> bytes:
            with urllib.request.urlopen(key, timeout=60) as res:
                return res.read()
        try:
            return await asyncio.to_thread(fetch)
        except urllib.error.URLError:
            raise HTTPException(502, "تعذر قراءة الملف من التخزين. حاول مرة أخرى.") from None
    raise HTTPException(404, "الملف غير موجود")


async def remove(db: AsyncSession, *, kind: str | None = None, owner_id: str | None = None, url: str | None = None) -> None:
    """Delete the workspace's files of a kind (and owner), or one by URL. Files from before this
    service (not recorded) are left alone."""
    q = select(WorkspaceFile)
    if url:
        q = q.where(WorkspaceFile.url == url)
    else:
        q = q.where(WorkspaceFile.kind == kind)
        q = q.where(WorkspaceFile.owner_id == owner_id) if owner_id else q.where(WorkspaceFile.owner_id.is_(None))
    rows = (await db.execute(q)).scalars().all()
    if not rows:
        return
    for r in rows:
        if r.url.startswith(PRIVATE) and _PRIVATE_KEY.match(r.url) and os.path.isfile(_private_path(r.url)):
            os.remove(_private_path(r.url))
    try:
        await backend().delete([r.url for r in rows if not r.url.startswith(PRIVATE)])
    except HTTPException:
        log.warning("could not delete %d stored file(s); their records are removed anyway", len(rows))
    for r in rows:
        await db.delete(r)


async def total_bytes(db: AsyncSession) -> int:
    return int(await db.scalar(text("SELECT COALESCE(sum(size), 0) FROM workspace_files")) or 0)


async def purge_workspace(tenant_id) -> int:
    """Delete every stored file of a workspace (it is being deleted; its rows go with it)."""
    if not tenant_id:
        return 0
    private = os.path.join(_private_dir(), _prefix(tenant_id).rstrip("/"))
    if os.path.isdir(private):
        shutil.rmtree(private, ignore_errors=True)
    try:
        if _blob_token():
            await _Blob().delete_prefix(f"private/{_prefix(tenant_id)}")
        return await backend().delete_prefix(_prefix(tenant_id))
    except HTTPException as e:
        log.warning("could not purge files of workspace %s: %s", tenant_id, e.detail)
        return 0
