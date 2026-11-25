"""Public upload serving (website_api.routers.uploads).

The public host serves an uploaded file only when a workspace_files row
records the exact URL with a public site-asset kind. Covers: kind allowlist
(po_invoice never served even when recorded and on disk), unrecorded URLs,
cross-tenant path guessing, traversal and malformed paths, symlink escape,
missing files, and the bypass cleanup on the anonymous lookup.
"""
import os
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.responses import FileResponse

from website_api.routers import uploads as up

TID = uuid.UUID("a1b975ac-32ac-4813-9b35-e43069616c5f")
TID2 = uuid.UUID("b2b975ac-32ac-4813-9b35-e43069616c5f")


def db_for(row):
    """Three execute calls: bypass on, the lookup (returns row), bypass off."""
    db = AsyncMock()
    results = iter([None, row, None])
    statements = []

    async def _exec(stmt, params=None):
        statements.append(str(stmt))
        r = MagicMock()
        r.first.return_value = next(results)
        return r

    db.execute.side_effect = _exec
    db._statements = statements
    return db


class PublicUploadTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        root = self._tmp.name
        self.root = root
        # A recorded public logo and a recorded business document, both on disk.
        for kind in ("logo", "po_invoice"):
            d = os.path.join(root, "t", str(TID), kind)
            os.makedirs(d)
            with open(os.path.join(d, "file-abc123.png"), "wb") as f:
                f.write(b"\x89PNG")
        self._patch = patch.object(up.settings, "UPLOAD_DIR", root)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    async def test_recorded_public_logo_is_served(self):
        path = f"t/{TID}/logo/file-abc123.png"
        db = db_for(row=(1,))
        res = await up.public_upload(path, db)
        self.assertIsInstance(res, FileResponse)
        self.assertTrue(res.path.endswith(os.path.join("logo", "file-abc123.png")))
        self.assertEqual(res.media_type, "image/png")

    async def test_bypass_is_cleared_after_lookup(self):
        db = db_for(row=(1,))
        await up.public_upload(f"t/{TID}/logo/file-abc123.png", db)
        joined = " ".join(db._statements)
        self.assertIn("app.bypass", joined)
        self.assertEqual(db._statements[-1].count("'off'"), 1)

    async def test_po_invoice_never_served_even_when_recorded_and_on_disk(self):
        # The kind allowlist rejects before any DB lookup.
        db = db_for(row=(1,))
        with self.assertRaises(HTTPException) as ctx:
            await up.public_upload(f"t/{TID}/po_invoice/file-abc123.png", db)
        self.assertEqual(ctx.exception.status_code, 404)
        db.execute.assert_not_called()

    async def test_unrecorded_url_is_404(self):
        db = db_for(row=None)
        with self.assertRaises(HTTPException) as ctx:
            await up.public_upload(f"t/{TID}/logo/file-abc123.png", db)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_cross_tenant_path_guess_is_404(self):
        # Tenant B's path for tenant A's file: no row records that exact URL.
        db = db_for(row=None)
        with self.assertRaises(HTTPException) as ctx:
            await up.public_upload(f"t/{TID2}/logo/file-abc123.png", db)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_recorded_but_missing_file_is_404(self):
        os.remove(os.path.join(self.root, "t", str(TID), "logo", "file-abc123.png"))
        db = db_for(row=(1,))
        with self.assertRaises(HTTPException) as ctx:
            await up.public_upload(f"t/{TID}/logo/file-abc123.png", db)
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_malformed_and_traversal_paths_are_404(self):
        db = db_for(row=(1,))
        for bad in (
            f"t/{TID}/logo/../po_invoice/file-abc123.png",
            f"t/not-a-uuid/logo/file-abc123.png",
            f"t/{TID}/logo/sub/dir.png",
            f"t/{TID}/LOGO/file-abc123.png",
            f"x/{TID}/logo/file-abc123.png",
            f"t/{TID}/logo/file abc.png",
            "",
        ):
            with self.assertRaises(HTTPException, msg=bad) as ctx:
                await up.public_upload(bad, db)
            self.assertEqual(ctx.exception.status_code, 404)
        db.execute.assert_not_called()

    async def test_symlink_escape_is_404(self):
        import tempfile

        with tempfile.TemporaryDirectory() as other:
            outside = os.path.join(other, "outside.png")
            with open(outside, "wb") as f:
                f.write(b"\x89PNG")
            link = os.path.join(self.root, "t", str(TID), "logo", "file-abc123.png")
            os.remove(link)
            os.symlink(outside, link)
            db = db_for(row=(1,))
            with self.assertRaises(HTTPException) as ctx:
                await up.public_upload(f"t/{TID}/logo/file-abc123.png", db)
            self.assertEqual(ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
