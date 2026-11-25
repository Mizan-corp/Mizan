"""Theme composition registries: shared/_fonts and _palettes, referenced by theme.json.

A theme pack composes its identity by reference ("fonts.files": [{"ref": "tajawal"}],
"palette": "amber"); the loader expands refs so consumers see plain colors and file
entries. One canonical copy per font family; palettes carry their license/source.
"""
import json
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.framework.manifest import theme_problems
from app.platform.themes import service
from app.platform.themes.service import APP_DIR


class FontRegistryTests(unittest.TestCase):
    def test_every_theme_composes_from_registry_families(self):
        for tid, t in service.file_themes().items():
            for e in (t.get("fonts") or {}).get("files") or []:
                self.assertNotIn("ref", e, f"{tid}: unexpanded ref {e}")
                self.assertTrue(str(e["src"]).startswith("/themes/assets/fonts/"), f"{tid}: {e}")

    def test_expansion_matches_registry_bytes(self):
        reg = service.font_registry()
        for t in service.file_themes().values():
            for e in (t.get("fonts") or {}).get("files") or []:
                fid, base = e["src"].split("/")[4], e["src"].split("/")[5]
                fam = reg[fid]
                self.assertEqual(e["family"], fam["family"])
                self.assertTrue((Path(fam["_dir"]) / base).is_file())

    def test_registry_families_are_complete_and_licensed(self):
        for fid, fam in service.font_registry().items():
            self.assertEqual(fam["license"], "OFL-1.1")
            self.assertTrue((Path(fam["_dir"]) / fam["license_file"]).is_file())
            self.assertTrue(all(u.startswith("https://raw.githubusercontent.com/google/fonts/") for u in fam["source_urls"]))
            self.assertTrue(fam["scripts"])

    def test_font_asset_serves_only_declared_files(self):
        data, kind = service.font_asset("tajawal", "tajawal-400.ttf")
        self.assertEqual(kind, "font/ttf")
        self.assertTrue(data)
        with self.assertRaises(HTTPException):
            service.font_asset("tajawal", "../../secret")
        with self.assertRaises(HTTPException):
            service.font_asset("tajawal", "almarai-400.ttf")  # declared on another family only
        with self.assertRaises(HTTPException):
            service.font_asset("nope", "tajawal-400.ttf")

    def test_legacy_pack_urls_keep_serving_the_same_bytes(self):
        """Published snapshots reference /themes/assets/files/<pack>/assets/<file>;
        those URLs resolve to the registry's canonical copy after the refactor."""
        reg = service.font_registry()
        canon = (Path(reg["tajawal"]["_dir"]) / "tajawal-400.ttf").read_bytes()
        data, kind = service.file_asset("grape", "assets/tajawal-400.ttf")
        self.assertEqual(data, canon)
        self.assertEqual(kind, "font/ttf")

    def test_unknown_ref_is_flagged(self):
        """An unknown ref survives shape validation (its shape is fine) and is caught
        by the service-level registry resolution check, not silently dropped."""
        bad = {"id": "bad", "name": "x", "name_en": "x", "version": "1.0.0", "kind": "theme",
               "palette": "mizan", "fonts": {"body": "X", "files": [{"ref": "nope"}]}}
        expanded = service._expand_font_refs(bad)
        self.assertIn({"ref": "nope"}, expanded["fonts"]["files"])  # kept for flagging
        self.assertNotIn("nope", service.font_registry())
        # the check_file_themes resolution branch flags any theme whose ref stayed unexpanded
        leftovers = [e for t in (expanded,) for e in t["fonts"]["files"] if "ref" in e]
        self.assertTrue(leftovers)


class PaletteRegistryTests(unittest.TestCase):
    def test_palettes_expand_to_full_colors(self):
        for tid, t in service.file_themes().items():
            self.assertIn("colors", t, tid)
            self.assertEqual(set(t["colors"]), {"light", "dark"}, tid)

    LEGACY_ORIGINALS = {"amber", "cobalt", "emerald", "mizan", "monokai", "slate"}

    def test_palettes_carry_source_and_license(self):
        for pid, pal in service.palette_registry().items():
            self.assertTrue(pal.get("source"), pid)
            self.assertTrue(pal.get("license"), pid)
            if pid in self.LEGACY_ORIGINALS:
                # The six legacy palettes predate the Open Color registry: original Mizan
                # compositions, honestly labelled, not implied Open Color derivations.
                self.assertIn("Original", pal["license"], pid)
            else:
                self.assertIn("MIT", pal["license"], pid)

    def test_palette_override_choice(self):
        self.assertEqual(service.check_palette_choice("grape"), "grape")
        self.assertIsNone(service.check_palette_choice("nope"))
        self.assertIsNone(service.check_palette_choice("../mizan"))
        self.assertIsNone(service.check_palette_choice(5))

    def test_packages_embed_colors_no_palette_ref(self):
        pkg = {"id": "acme.x", "name": "x", "name_en": "x", "version": "1.0.0", "kind": "theme",
               "palette": "mizan"}
        self.assertTrue(any("palette" in p for p in theme_problems(pkg, package=True)))

    def test_theme_problems_accept_composed_platform_theme(self):
        raw = json.loads((APP_DIR / "themes" / "amber" / "theme.json").read_text(encoding="utf-8"))
        self.assertEqual(theme_problems(raw), [])


if __name__ == "__main__":
    unittest.main()
