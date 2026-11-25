"""ERP-origin uploads readback (app.framework.uploads_readback).

The blanket StaticFiles /uploads mount is gone: current sign-in branding stays
anonymous (the public tenant-resolution bootstrap already exposes it),
everything else needs an ERP session for the same workspace plus a recorded
workspace_files row, and po_invoice needs the purchases permission. DB is
mocked; UPLOAD_DIR points at a temp tree with one real file.
"""
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('DATABASE_URL', 'postgresql+asyncpg://unused:unused@127.0.0.1/unused')
os.environ.setdefault('SECRET_KEY', 'offline-test-not-used-for-signing')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from app.core.config import settings
from app.framework import uploads_readback as ur

TID = uuid.UUID("a1b975ac-32ac-4813-9b35-e43069616c5f")
OTHER = uuid.UUID("b2b975ac-32ac-4813-9b35-e43069616c5f")
LOGO_PATH = f"t/{TID}/logo/file-abc123.png"
PO_PATH = f"t/{TID}/po_invoice/{uuid.uuid4()}-deadbeef.pdf"
IMG_PATH = f"t/{TID}/product_image/{uuid.uuid4()}-deadbeef.png"


class FakeDB:
    def __init__(self, file_row=None, branding_hit=False):
        self._file = file_row
        self._branding = branding_hit
        self.tenant_scoped_reads = 0

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        result = MagicMock()
        if "set_config" in sql:
            return result
        if "store_settings" in sql:
            result.first.return_value = (1,) if self._branding else None
            return result
        raise AssertionError("unexpected execute: " + sql[:120])

    async def scalar(self, stmt):
        self.tenant_scoped_reads += 1
        return self._file


def file_row(url):
    return MagicMock(url=url, content_type="image/png", tenant_id=TID)


def request_anon():
    req = MagicMock()
    req.cookies = {}
    req.headers = {}
    req.method = "GET"
    return req


def user_with(perms=(), tenant=TID):
    return MagicMock(tenant_id=tenant, effective_permissions=frozenset(perms))


class Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._saved = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = self._dir.name
        for rel in (LOGO_PATH, PO_PATH, IMG_PATH):
            full = os.path.join(self._dir.name, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as fh:
                fh.write(b"png-bytes")

    def tearDown(self):
        settings.UPLOAD_DIR = self._saved
        self._dir.cleanup()

    async def test_malformed_path_404(self):
        with self.assertRaises(HTTPException) as ctx:
            await ur.serve_workspace_upload("..%2f..%2fetc/passwd", request_anon(), FakeDB())
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_current_branding_logo_serves_anonymously(self):
        db = FakeDB(file_row(LOGO_PATH), branding_hit=True)
        resp = await ur.serve_workspace_upload(LOGO_PATH, request_anon(), db)
        self.assertEqual(resp.status_code, 200)

    async def test_recorded_but_not_current_branding_needs_session(self):
        db = FakeDB(file_row(LOGO_PATH), branding_hit=False)
        with self.assertRaises(HTTPException) as ctx:
            await ur.serve_workspace_upload(LOGO_PATH, request_anon(), db)
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_po_invoice_needs_session(self):
        db = FakeDB(file_row(PO_PATH))
        with self.assertRaises(HTTPException) as ctx:
            await ur.serve_workspace_upload(PO_PATH, request_anon(), db)
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_po_invoice_needs_purchases_permission(self):
        db = FakeDB(file_row(PO_PATH))
        with patch("app.dependencies.get_current_user",
                   new=AsyncMock(return_value=user_with(()))):
            with self.assertRaises(HTTPException) as ctx:
                await ur.serve_workspace_upload(PO_PATH, request_anon(), db)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_po_invoice_serves_with_purchases_permission(self):
        db = FakeDB(file_row(PO_PATH))
        with patch("app.dependencies.get_current_user",
                   new=AsyncMock(return_value=user_with(("purchases",)))):
            resp = await ur.serve_workspace_upload(PO_PATH, request_anon(), db)
        self.assertEqual(resp.status_code, 200)

    async def test_product_image_serves_to_workspace_member(self):
        db = FakeDB(file_row(IMG_PATH))
        with patch("app.dependencies.get_current_user",
                   new=AsyncMock(return_value=user_with(()))):
            resp = await ur.serve_workspace_upload(IMG_PATH, request_anon(), db)
        self.assertEqual(resp.status_code, 200)

    async def test_other_workspace_file_never_served(self):
        db = FakeDB(file_row(IMG_PATH))
        with patch("app.dependencies.get_current_user",
                   new=AsyncMock(return_value=user_with((), tenant=OTHER))):
            with self.assertRaises(HTTPException) as ctx:
                await ur.serve_workspace_upload(IMG_PATH, request_anon(), db)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_unrecorded_path_never_served(self):
        db = FakeDB(file_row=None)
        with patch("app.dependencies.get_current_user",
                   new=AsyncMock(return_value=user_with(("purchases",)))):
            with self.assertRaises(HTTPException) as ctx:
                await ur.serve_workspace_upload(IMG_PATH, request_anon(), db)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_factory_mounts_readback_not_staticfiles(self):
        src = (Path(__file__).resolve().parents[1] / "app" / "factory.py").read_text()
        self.assertNotIn('app.mount("/uploads"', src)
        self.assertIn("uploads_readback", src)


if __name__ == "__main__":
    unittest.main()
