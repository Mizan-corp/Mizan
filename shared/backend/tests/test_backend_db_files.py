"""Offline tests for the database file backend (app/framework/files.py, v122):

- backend selection: serverless without a blob token stores bytes in
  workspace_file_blobs instead of refusing; disk and blob stay as before.
- the URL keeps the disk shape with an unguessable random suffix, so serving
  routes and reference checks work unchanged.
- serve_file hands the bytes back on the database backend (after the calling
  route's access gate) and keeps the disk behaviour, including traversal 404.
- the site media upload enforces the plan's aggregate quota (ensure_room)."""

import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@127.0.0.1/unused")
os.environ.setdefault("SECRET_KEY", "offline-test-not-used-for-signing")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.responses import FileResponse, Response

from app.models.registry import load_all_models

load_all_models()

from app.framework import files
from app.platform.site import media

TID = uuid.uuid4()
SERVERLESS = {"VERCEL": "1", "BLOB_READ_WRITE_TOKEN": ""}
ON_SITE = {"VERCEL": "", "BLOB_READ_WRITE_TOKEN": ""}


class BackendSelectionTests(unittest.TestCase):
    def test_serverless_without_token_uses_database(self):
        with patch.dict(os.environ, SERVERLESS):
            self.assertIsInstance(files.backend(), files._DB)
            self.assertEqual(files.backend_name(), "db")

    def test_blob_token_wins_everywhere(self):
        with patch.dict(os.environ, {"VERCEL": "1", "BLOB_READ_WRITE_TOKEN": "tok"}):
            self.assertIsInstance(files.backend(), files._Blob)
            self.assertEqual(files.backend_name(), "blob")

    def test_on_site_uses_disk(self):
        with patch.dict(os.environ, ON_SITE):
            self.assertIsInstance(files.backend(), files._Disk)
            self.assertEqual(files.backend_name(), "disk")


class DbBackendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncMock()

    def added_blobs(self):
        return [c.args[0] for c in self.db.add.call_args_list
                if isinstance(c.args[0], files.WorkspaceFileBlob)]

    async def test_put_records_bytes_under_disk_shaped_url(self):
        with patch.dict(os.environ, SERVERLESS):
            url = await files.backend().put(f"t/{TID}/site_image/file.png", b"PNGDATA", "image/png", db=self.db)
        self.assertTrue(url.startswith(f"/uploads/t/{TID}/site_image/file-"))
        self.assertTrue(url.endswith(".png"))
        blob = self.added_blobs()[0]
        self.assertEqual(blob.url, url)
        self.assertEqual(bytes(blob.data), b"PNGDATA")

    async def test_put_never_overwrites(self):
        with patch.dict(os.environ, SERVERLESS):
            a = await files.backend().put(f"t/{TID}/site_image/file.png", b"A", "image/png", db=self.db)
            b = await files.backend().put(f"t/{TID}/site_image/file.png", b"B", "image/png", db=self.db)
        self.assertNotEqual(a, b)  # random suffix, like Blob and disk

    async def test_delete_only_upload_urls(self):
        with patch.dict(os.environ, SERVERLESS):
            await files.backend().delete(["/uploads/t/x/site_image/a.png", "https://blob.example/x"], db=self.db)
        stmt = str(self.db.execute.await_args.args[0])
        self.assertIn("DELETE FROM workspace_file_blobs", stmt)
        self.assertEqual(self.db.execute.await_args.args[1]["urls"], ["/uploads/t/x/site_image/a.png"])

    async def test_read_returns_bytes_and_clears_bypass(self):
        result = MagicMock()
        result.first.return_value = (b"IMG", "image/png")
        self.db.execute = AsyncMock(side_effect=[MagicMock(), result, MagicMock()])
        with patch.dict(os.environ, SERVERLESS):
            found = await files._DB().read(self.db, "/uploads/t/x/site_image/a.png")
        self.assertEqual(found, (b"IMG", "image/png"))
        calls = [str(c.args[0]) for c in self.db.execute.await_args_list]  # bypass on, select, bypass off
        self.assertTrue(any("app.bypass', 'on'" in c for c in calls))
        self.assertTrue(any("app.bypass', 'off'" in c for c in calls))

    async def test_read_missing_is_none(self):
        result = MagicMock()
        result.first.return_value = None
        self.db.execute = AsyncMock(side_effect=[MagicMock(), result, MagicMock()])
        with patch.dict(os.environ, SERVERLESS):
            self.assertIsNone(await files._DB().read(self.db, "/uploads/t/x/site_image/none.png"))


class ServeFileTests(unittest.IsolatedAsyncioTestCase):
    async def test_db_backend_serves_bytes_with_immutable_cache(self):
        db = AsyncMock()
        result = MagicMock()
        result.first.return_value = (b"IMG", "image/png")
        db.execute = AsyncMock(side_effect=[MagicMock(), result, MagicMock()])
        with patch.dict(os.environ, SERVERLESS):
            res = await files.serve_file(db, "/uploads/t/x/site_image/a.png", "image/png")
        self.assertIsInstance(res, Response)
        self.assertEqual(res.body, b"IMG")
        self.assertEqual(res.media_type, "image/png")
        self.assertIn("immutable", res.headers["cache-control"])

    async def test_db_backend_missing_is_none(self):
        db = AsyncMock()
        result = MagicMock()
        result.first.return_value = None
        db.execute = AsyncMock(side_effect=[MagicMock(), result, MagicMock()])
        with patch.dict(os.environ, SERVERLESS):
            self.assertIsNone(await files.serve_file(db, "/uploads/t/x/site_image/none.png"))

    async def test_disk_backend_serves_real_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, ON_SITE):
            from app.core.config import settings
            saved = settings.UPLOAD_DIR
            settings.UPLOAD_DIR = d
            try:
                os.makedirs(os.path.join(d, "t", "x", "site_image"))
                p = os.path.join(d, "t", "x", "site_image", "a.png")
                Path(p).write_bytes(b"IMG")
                res = await files.serve_file(AsyncMock(), "/uploads/t/x/site_image/a.png", "image/png")
                self.assertIsInstance(res, FileResponse)
            finally:
                settings.UPLOAD_DIR = saved

    async def test_disk_backend_traversal_and_missing_are_none(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, ON_SITE):
            from app.core.config import settings
            saved = settings.UPLOAD_DIR
            settings.UPLOAD_DIR = d
            try:
                self.assertIsNone(await files.serve_file(AsyncMock(), "/uploads/../secret", None))
                self.assertIsNone(await files.serve_file(AsyncMock(), "/uploads/t/x/site_image/none.png", None))
            finally:
                settings.UPLOAD_DIR = saved


class StoreThroughDbBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_store_puts_bytes_and_metadata_in_one_transaction(self):
        db = AsyncMock()
        token = files.current_tenant_id.set(TID)
        try:
            with patch.dict(os.environ, SERVERLESS):
                url = await files.store(db, b"IMG", kind="site_image", filename="shot.png",
                                        content_type="image/png", owner_id=None, replace=False)
        finally:
            files.current_tenant_id.reset(token)
        self.assertTrue(url.startswith(f"/uploads/t/{TID}/site_image/file-"))  # stem is owner or 'file'
        added = [c.args[0] for c in db.add.call_args_list]
        blob = next(o for o in added if isinstance(o, files.WorkspaceFileBlob))
        meta = next(o for o in added if isinstance(o, files.WorkspaceFile))
        self.assertEqual(blob.url, url)
        self.assertEqual(meta.url, url)
        self.assertEqual(meta.size, 3)


class MediaQuotaTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_enforces_aggregate_quota(self):
        import io
        from fastapi import UploadFile
        from starlette.datastructures import Headers
        import struct, zlib

        def chunk(typ, payload):
            return (struct.pack(">I", len(payload)) + typ + payload
                    + struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF))
        ihdr = struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)
        raw = b"".join(b"\x00" + b"\xbe\x1e\x1e" * 4 for _ in range(4))
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
               + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

        db = AsyncMock()
        from types import SimpleNamespace
        stored = SimpleNamespace(id=uuid.uuid4(), kind=media.KIND, owner_id=None,
                                 url=f"/uploads/t/{TID}/site_image/f-abc.png",
                                 size=len(png), content_type="image/png", name="f.png",
                                 created_at=None)
        result = MagicMock()
        result.scalar_one.return_value = stored
        db.execute.return_value = result
        upload = UploadFile(file=io.BytesIO(png), filename="f.png",
                            headers=Headers({"content-type": "image/png"}))
        with patch.object(media.files, "store", new=AsyncMock(return_value=stored.url)), \
             patch("app.framework.storage.ensure_room", new=AsyncMock()) as room:
            await media.upload_media(upload, db, type("U", (), {"tenant_id": TID})())
        room.assert_awaited_once()
        self.assertEqual(room.await_args.args[1], len(png))


if __name__ == "__main__":
    unittest.main()
