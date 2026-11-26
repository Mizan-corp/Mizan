"""Offline tests for a workspace's independent font picks (themes/service.py):
check_font_choice keeps only families Mizan's file themes actually ship,
family_files exposes absolute public srcs, and _with_font_choice lays the
workspace's body/display over its theme pack with the matching real files."""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://unused:unused@127.0.0.1/unused")
os.environ.setdefault("SECRET_KEY", "offline-test-not-used-for-signing")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.platform.themes import service


class FamilyFilesTests(unittest.TestCase):
    def test_shipped_families_have_absolute_public_srcs(self):
        fams = service.family_files()
        for expected in ("Cairo", "Tajawal", "Almarai"):
            self.assertIn(expected, fams)
            for f in fams[expected]:
                self.assertTrue(f["src"].startswith(("/themes/assets/files/", "/themes/assets/fonts/")), f)
                self.assertIn(f["weight"], ("400", "700", "200 900"), f)

    def test_shipped_families_come_from_the_registry(self):
        """One canonical copy per family: the shared _fonts registry, not per-pack duplicates."""
        for fid, fam in service.font_registry().items():
            for fe in fam["files"]:
                self.assertTrue((__import__("pathlib").Path(fam["_dir"]) / fe["src"]).is_file(), fe)
            self.assertTrue((__import__("pathlib").Path(fam["_dir"]) / fam["license_file"]).is_file(), fam)
            self.assertTrue(fam.get("source_urls"), fam)

    def test_check_font_choice_keeps_only_shipped_families(self):
        self.assertEqual(service.check_font_choice({"body": "Tajawal", "display": "Cairo"}),
                         {"body": "Tajawal", "display": "Cairo"})
        self.assertEqual(service.check_font_choice({"body": "Comic Sans", "display": "Almarai"}),
                         {"display": "Almarai"})
        self.assertEqual(service.check_font_choice("nope"), {})
        self.assertEqual(service.check_font_choice({}), {})


class WithFontChoiceTests(unittest.TestCase):
    def tenant(self, fonts):
        return SimpleNamespace(id="t", palette={"name": "ruby", "hue": 0, **({"fonts": fonts} if fonts else {})})

    def base_theme(self):
        return {"id": "ruby", "fonts": {"body": "Tajawal", "display": "Cairo", "files": [
            {"family": "Tajawal", "src": "assets/tajawal-400.ttf", "weight": "400", "style": "normal"}]}}

    def test_no_choice_leaves_the_pack_untouched(self):
        t = self.base_theme()
        self.assertIs(service._with_font_choice(t, self.tenant(None)), t)
        self.assertIs(service._with_font_choice(t, self.tenant({"nope": 1})), t)

    def test_choice_overrides_family_and_borrows_real_files(self):
        out = service._with_font_choice(self.base_theme(), self.tenant({"body": "Almarai"}))
        self.assertEqual(out["fonts"]["body"], "Almarai")
        self.assertEqual(out["fonts"]["display"], "Cairo")  # untouched
        almarai = [f for f in out["fonts"]["files"] if f["family"] == "Almarai"]
        self.assertTrue(almarai, "borrowed Almarai files expected")
        for f in almarai:
            self.assertTrue(f["src"].startswith(("/themes/assets/files/", "/themes/assets/fonts/")), f)

    def test_unknown_family_is_ignored(self):
        out = service._with_font_choice(self.base_theme(), self.tenant({"body": "Wingdings"}))
        self.assertEqual(out["fonts"]["body"], "Tajawal")


if __name__ == "__main__":
    unittest.main()
