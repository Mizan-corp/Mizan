"""Row bleed (full-viewport band) and dark header surface: bounded registry tokens
rendered as fixed classes, never arbitrary CSS (ADR-015)."""
import unittest

from app.framework.manifest import page_problems
from app.platform.site.render import render_page, _theme_chrome


def tree_with_row(row_settings):
    return {
        "id": "n_root1", "type": "section",
        "settings": {"desktop": {}}, "content": {},
        "children": [{
            "id": "n_cols1", "type": "columns",
            "settings": {"desktop": row_settings}, "content": {},
            "children": [{
                "id": "n_col01", "type": "column", "settings": {}, "content": {},
                "children": [{"id": "n_hd001", "type": "heading", "settings": {},
                              "content": {"en": {"text": "Hi"}}}],
            }],
        }],
    }


class RowBleed(unittest.TestCase):
    def test_a_bleed_is_a_valid_columns_setting(self):
        tree = tree_with_row({"background": "dark", "bleed": True})
        self.assertEqual(page_problems(tree, languages=("en",)), [])

    def test_b_bleed_row_renders_the_band_class(self):
        html = render_page(tree_with_row({"background": "dark", "bleed": True}), lang="en")
        self.assertIn("mz-bleed", html)
        self.assertIn("mz-background-dark", html)

    def test_c_bleed_is_ignored_on_non_columns_nodes(self):
        tree = tree_with_row({})
        tree["children"][0]["children"][0]["settings"] = {"desktop": {"bleed": True}}
        html = render_page(tree, lang="en", validate=False)
        self.assertNotIn("mz-bleed", html)

    def test_d_rows_without_bleed_stay_contained(self):
        html = render_page(tree_with_row({"background": "dark"}), lang="en")
        self.assertNotIn("mz-bleed", html)


class DarkHeaderSurface(unittest.TestCase):
    def test_a_dark_surface_adds_the_class(self):
        head, _ = _theme_chrome({"header": {"brand": "Wirya", "surface": "dark"}})
        self.assertIn("mz-site-header-dark", head)

    def test_b_default_surface_stays_unmarked(self):
        head, _ = _theme_chrome({"header": {"brand": "Wirya"}})
        self.assertNotIn("mz-site-header-dark", head)
        head, _ = _theme_chrome({"header": {"brand": "Wirya", "surface": "default"}})
        self.assertNotIn("mz-site-header-dark", head)


if __name__ == "__main__":
    unittest.main()
