"""Wizard branding recommendations: the per-key fallback merge. An activity whose
branding dict exists but lacks a key (e.g. "palettes") inherits general's value for
that key only - its own declared keys always win. Runs offline: branding_options
reads the activity manifests, not the database."""
import asyncio
import json
import os


def test_palette_recommendations_merge_per_key(monkeypatch):
    if not os.environ.get("DATABASE_URL"):
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://unused:unused@127.0.0.1/unused")
    if not os.environ.get("SECRET_KEY"):
        monkeypatch.setenv("SECRET_KEY", "offline-test-not-used-for-signing")
    from app.framework.variants import ACTIVITIES
    from website_api.routers.signup import branding_options

    raw = {}
    for f in sorted(ACTIVITIES.glob("*/activity.json")):
        a = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(a.get("branding"), dict):
            raw[a["id"]] = a["branding"]
    assert "palettes" in raw.get("general", {}), "general declares the fallback palettes"
    lacking = [k for k, v in raw.items() if k != "general" and "palettes" not in v]
    assert lacking, "fixture expectation: some activities declare branding without a palettes key"

    out = asyncio.run(branding_options())
    for k in lacking:  # the missing key is filled from general
        assert out["activities"][k]["palettes"] == raw["general"]["palettes"], k
    for k, v in raw.items():  # every declared key wins over the fallback
        for key, val in v.items():
            assert out["activities"][k][key] == val, (k, key)
