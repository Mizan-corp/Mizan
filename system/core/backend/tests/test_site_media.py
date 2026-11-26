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


def make_png(w: int = 8, h: int = 8) -> bytes:
    import struct
    import zlib

    def chunk(typ, payload):
        return (struct.pack(">I", len(payload)) + typ + payload
                + struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xbe\x1e\x1e" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


VALID_PNG = make_png()


class UploadValidationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncMock()
        self.user = SimpleNamespace(tenant_id=TID)

    async def test_rejects_unsupported_type(self):
        with self.assertRaises(HTTPException) as ctx:
            await media.upload_media(make_upload(b"x", "image/svg+xml"), self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_declared_type_without_matching_signature(self):
        # HTML polyglot claiming to be a PNG: declared type alone must not pass
        with self.assertRaises(HTTPException) as ctx:
            await media.upload_media(make_upload(b"<html><script>alert(1)</script>", "image/png"),
                                     self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 400)
        # wrong signature for the declared type
        with self.assertRaises(HTTPException) as ctx:
            await media.upload_media(make_upload(b"\x89PNG\r\n\x1a\nrest", "image/jpeg"),
                                     self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_truncated_file_with_valid_signature(self):
        # signature passes but the payload does not structurally decode as a PNG
        with self.assertRaises(HTTPException) as ctx:
            await media.upload_media(make_upload(b"\x89PNG\r\n\x1a\n" + b"junk" * 10, "image/png"),
                                     self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_signature_checks_per_type(self):
        ok = media._signature_matches
        self.assertTrue(ok(b"\x89PNG\r\n\x1a\n...", "image/png"))
        self.assertTrue(ok(b"\xff\xd8\xff\xe0....", "image/jpeg"))
        self.assertTrue(ok(b"GIF89a....", "image/gif"))
        self.assertTrue(ok(b"RIFF\x00\x00\x00\x00WEBPvp8", "image/webp"))
        self.assertFalse(ok(b"RIFF\x00\x00\x00\x00WAVE", "image/webp"))  # RIFF but not WebP
        self.assertFalse(ok(b"", "image/png"))

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
            out = await media.upload_media(make_upload(VALID_PNG, "image/png"), self.db, self.user)
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

    async def test_in_use_file_is_refused_with_409(self):
        stored = media.WorkspaceFile(id=uuid.uuid4(), kind=media.KIND, owner_id=None,
                               url=f"/uploads/t/{TID}/site_image/file-abc.png",
                               size=3, content_type="image/png")
        found = MagicMock()
        found.scalar_one_or_none.return_value = stored
        in_use = MagicMock()
        in_use.first.return_value = (uuid.uuid4(),)  # a page tree references the URL
        self.db.execute.side_effect = [found, in_use]
        with patch.object(media.files, "remove", new=AsyncMock()) as remove:
            with self.assertRaises(HTTPException) as ctx:
                await media.delete_media(stored.id, self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 409)
        remove.assert_not_awaited()  # an in-use image is never deleted

    async def test_file_referenced_by_site_settings_is_refused_with_409(self):
        stored = media.WorkspaceFile(id=uuid.uuid4(), kind=media.KIND, owner_id=None,
                               url=f"/uploads/t/{TID}/site_image/file-logo.png",
                               size=3, content_type="image/png")
        found = MagicMock()
        found.scalar_one_or_none.return_value = stored
        pages_miss = MagicMock()
        pages_miss.first.return_value = None
        settings_hit = MagicMock()
        settings_hit.first.return_value = (uuid.uuid4(),)  # logo/theme references the URL
        self.db.execute.side_effect = [found, pages_miss, settings_hit]
        with patch.object(media.files, "remove", new=AsyncMock()) as remove:
            with self.assertRaises(HTTPException) as ctx:
                await media.delete_media(stored.id, self.db, self.user)
        self.assertEqual(ctx.exception.status_code, 409)
        remove.assert_not_awaited()

    async def test_delete_goes_through_shared_remove_by_url(self):
        stored = media.WorkspaceFile(id=uuid.uuid4(), kind=media.KIND, owner_id=None,
                               url=f"/uploads/t/{TID}/site_image/file-abc.png",
                               size=3, content_type="image/png")
        found = MagicMock()
        found.scalar_one_or_none.return_value = stored
        not_in_use = MagicMock()
        not_in_use.first.return_value = None
        # pages miss, then site-settings miss: both durable references are checked
        self.db.execute.side_effect = [found, not_in_use, not_in_use]
        with patch.object(media.files, "remove", new=AsyncMock()) as remove:
            await media.delete_media(stored.id, self.db, self.user)
        remove.assert_awaited_once()
        self.assertEqual(remove.await_args.kwargs["url"], stored.url)
        self.db.commit.assert_awaited()


if __name__ == "__main__":
    unittest.main()
