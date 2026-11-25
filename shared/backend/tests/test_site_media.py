"""Offline tests for the site media library (app/platform/site/media.py):
upload validation matches the established image rules (types, 5MB cap, empty),
storage goes through the shared files service as multi-file site_image records
(replace=False, no owner), and list/delete stay inside the bound workspace."""

import io
import os
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@127.0.0.1/unused")
os.environ.setdefault("SECRET_KEY", "offline-test-not-used-for-signing")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.models.registry import load_all_models

load_all_models()  # mapper configuration cascades across the full registry

from app.platform.site import media

TID = uuid.uuid4()


def make_upload(data: bytes, content_type: str, filename: str = "shot.png") -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename,
                      headers=Headers({"content-type": content_type}))


class UploadValidationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncMock()
        self.user = SimpleNamespace(tenant_id=TID)

    async def test_rejects_unsupported_type(self):
        with self.assertRaises(HTTPException) as ctx:
            await media.upload_media(make_upload(b"x", "image/svg+xml"), self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_oversize(self):
        with self.assertRaises(HTTPException) as ctx:
            await media.upload_media(make_upload(b"x" * (media.MAX_UPLOAD_SIZE + 1), "image/png"),
                                     self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_empty(self):
        with self.assertRaises(HTTPException) as ctx:
            await media.upload_media(make_upload(b"", "image/png"), self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_stores_as_multi_file_site_image(self):
        stored = media.WorkspaceFile(id=uuid.uuid4(), kind=media.KIND, owner_id=None,
                               url=f"/uploads/t/{TID}/site_image/file-abc.png",
                               size=3, content_type="image/png")
        result = MagicMock()
        result.scalar_one.return_value = stored
        self.db.execute.return_value = result
        with patch.object(media.files, "store", new=AsyncMock(return_value=stored.url)) as store:
            out = await media.upload_media(make_upload(b"png", "image/png"), self.db, self.user)
        kwargs = store.await_args.kwargs
        self.assertEqual(kwargs["kind"], "site_image")
        self.assertIsNone(kwargs["owner_id"])
        self.assertIs(kwargs["replace"], False)  # a library: new uploads never replace others
        self.assertEqual(kwargs["content_type"], "image/png")
        self.assertEqual(out["url"], stored.url)
        self.db.commit.assert_awaited()


class DeleteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncMock()
        self.user = SimpleNamespace(tenant_id=TID)

    async def test_missing_or_other_workspace_file_is_404(self):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        self.db.execute.return_value = result
        with self.assertRaises(HTTPException) as ctx:
            await media.delete_media(uuid.uuid4(), self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_delete_goes_through_shared_remove_by_url(self):
        stored = media.WorkspaceFile(id=uuid.uuid4(), kind=media.KIND, owner_id=None,
                               url=f"/uploads/t/{TID}/site_image/file-abc.png",
                               size=3, content_type="image/png")
        result = MagicMock()
        result.scalar_one_or_none.return_value = stored
        self.db.execute.return_value = result
        with patch.object(media.files, "remove", new=AsyncMock()) as remove:
            await media.delete_media(stored.id, self.db, self.user)
        remove.assert_awaited_once()
        self.assertEqual(remove.await_args.kwargs["url"], stored.url)
        self.db.commit.assert_awaited()


if __name__ == "__main__":
    unittest.main()
