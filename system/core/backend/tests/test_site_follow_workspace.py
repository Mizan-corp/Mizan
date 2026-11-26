"""Offline tests for site follow-workspace branding (site/service.py):
check_settings accepts the follow_workspace flag, the pack radius maps to the
renderer px, and explicit site settings win over the workspace base per token.
The opt-in rule itself (absent flag = raw settings, untouched) is covered by
resolved_settings' early return, exercised live against the dev database."""

import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@127.0.0.1/unused")
os.environ.setdefault("SECRET_KEY", "offline-test-not-used-for-signing")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.models.registry import load_all_models

load_all_models()  # mapper configuration cascades across the full registry

from app.platform.site import service
from app.platform.settings import branding


class CheckSettingsFollowTests(unittest.TestCase):
    def test_follow_workspace_flag_accepted(self):
        self.assertEqual(service.check_settings({"follow_workspace": True}), {"follow_workspace": True})
        self.assertEqual(service.check_settings({"follow_workspace": False}), {"follow_workspace": False})

    def test_follow_workspace_rejects_non_bool(self):
        for bad in ("true", 1, {"on": True}):
            with self.assertRaises(HTTPException):
                service.check_settings({"follow_workspace": bad})

    def test_unknown_keys_still_rejected(self):
        with self.assertRaises(HTTPException):
            service.check_settings({"follow_workspace": True, "surprise": 1})

    def test_existing_documents_unchanged(self):
        doc = {"colors": {"light": {"primary": "#f03e3e"}}, "shape": {"radius": 8}}
        self.assertEqual(service.check_settings(doc), doc)


class RadiusTests(unittest.TestCase):
    def test_rem_and_px_to_int(self):
        self.assertEqual(service._radius_px("0.625rem"), 10)
        self.assertEqual(service._radius_px("0rem"), 0)
        self.assertEqual(service._radius_px("12px"), 12)

    def test_clamped_and_garbage(self):
        self.assertEqual(service._radius_px("9rem"), 64)
        self.assertIsNone(service._radius_px("wide"))
        self.assertIsNone(service._radius_px(12))
        self.assertIsNone(service._radius_px(None))


class MergeTests(unittest.TestCase):
    def base(self):
        return {"colors": {"light": {"background": "#fff5f5", "primary": "#f03e3e"}},
                "typography": {"family": "sans-serif"}, "shape": {"radius": 10},
                "header": {"brand": "", "links": [], "actions": [], "logo": "/files/logo.png"}}

    def test_explicit_color_token_wins_per_token(self):
        merged = service._merge_site_settings(self.base(), {"colors": {"light": {"primary": "#111111"}}})
        self.assertEqual(merged["colors"]["light"]["primary"], "#111111")
        self.assertEqual(merged["colors"]["light"]["background"], "#fff5f5")

    def test_explicit_sections_win_wholesale(self):
        merged = service._merge_site_settings(
            self.base(), {"typography": {"family": "serif"}, "shape": {"radius": 0}})
        self.assertEqual(merged["typography"], {"family": "serif"})
        self.assertEqual(merged["shape"], {"radius": 0})

    def test_site_without_logo_inherits_workspace_logo(self):
        merged = service._merge_site_settings(
            self.base(), {"header": {"brand": "متجري", "links": [], "actions": []}})
        self.assertEqual(merged["header"]["brand"], "متجري")
        self.assertEqual(merged["header"]["logo"], "/files/logo.png")

    def test_site_logo_wins_over_workspace_logo(self):
        merged = service._merge_site_settings(
            self.base(), {"header": {"brand": "", "links": [], "actions": [], "logo": "/files/mine.png"}})
        self.assertEqual(merged["header"]["logo"], "/files/mine.png")

    def test_no_workspace_base_leaves_explicit_alone(self):
        explicit = {"colors": {"light": {"primary": "#111111"}}}
        merged = service._merge_site_settings({}, explicit)
        self.assertEqual(merged, explicit)


class RefreshActivationTests(unittest.IsolatedAsyncioTestCase):
    def host(self):
        from app.core.config import settings as cfg
        return patch.object(cfg, "PUBLIC_SITE_HOST", "sites.example.com")

    async def test_non_following_site_snapshots_stay_untouched(self):
        db = AsyncMock()
        with self.host(), \
             patch.object(service, "get_settings", new=AsyncMock(return_value={})), \
             patch.object(service, "resolved_settings", new=AsyncMock(side_effect=AssertionError("must not resolve"))):
            await service.refresh_activation_themes(db)
        db.execute.assert_not_called()

    async def test_following_site_snapshots_refresh(self):
        db = AsyncMock()
        with self.host(), \
             patch.object(service, "get_settings", new=AsyncMock(return_value={"follow_workspace": True})), \
             patch.object(service, "resolved_settings", new=AsyncMock(return_value={"colors": {"light": {"primary": "#e8590c"}}})):
            await service.refresh_activation_themes(db)
        self.assertEqual(db.execute.await_count, 1)
        sql = db.execute.await_args.args[0].text
        self.assertIn("UPDATE site_activation", sql)
        db.commit.assert_awaited()

    async def test_no_host_is_noop(self):
        from app.core.config import settings as cfg
        db = AsyncMock()
        with patch.object(cfg, "PUBLIC_SITE_HOST", ""), \
             patch.object(service, "get_settings", new=AsyncMock(side_effect=AssertionError("must not read"))):
            await service.refresh_activation_themes(db)
        db.execute.assert_not_called()


def _png() -> bytes:
    import struct
    import zlib

    def chunk(typ, payload):
        return (struct.pack(">I", len(payload)) + typ + payload
                + struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xbe\x1e\x1e" * 8 for _ in range(8))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class LogoPropagationTests(unittest.IsolatedAsyncioTestCase):
    async def test_logo_upload_refreshes_following_site_activations(self):
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result
        upload = UploadFile(file=io.BytesIO(_png()), filename="logo.png",
                            headers=Headers({"content-type": "image/png"}))
        with patch("app.platform.settings.branding.ensure_room", new=AsyncMock()), \
             patch("app.framework.files.store", new=AsyncMock(return_value="/uploads/t/x/logo/logo.png")), \
             patch("app.platform.site.service.refresh_activation_themes", new=AsyncMock()) as refresh:
            out = await branding.store_workspace_logo(db, upload)
        self.assertEqual(out, {"logo_url": "/uploads/t/x/logo/logo.png"})
        refresh.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
