"""Section/column background images: a validated "url" setting rendered as a bounded
style layer (scrim + image), never arbitrary CSS (ADR-015)."""
import unittest

from app.framework.manifest import page_problems
from app.platform.site.render import render_page
from app.platform.site import render as _render_mod


def tree_with(settings):
    return {
        "id": "n_root1", "type": "section",
        "settings": {"desktop": settings["section"]}, "content": {},
        "children": [{
            "id": "n_cols1", "type": "columns", "settings": {}, "content": {},
            "children": [{
                "id": "n_col01", "type": "column",
                "settings": {"desktop": settings["column"]}, "content": {},
                "children": [{"id": "n_hd001", "type": "heading", "settings": {},
                              "content": {"en": {"text": "Hi"}}}],
            }],
        }],
    }


class BackgroundImageValidation(unittest.TestCase):
    def test_a_valid_image_and_dim_pass(self):
        tree = tree_with({"section": {}, "column": {
            "background_image": "https://assets.example/bench.webp", "background_dim": "soft"}})
        self.assertEqual(page_problems(tree, languages=("en",)), [])

    def test_a_root_relative_image_passes(self):
        tree = tree_with({"section": {}, "column": {"background_image": "/site_image/bench.webp"}})
        self.assertEqual(page_problems(tree, languages=("en",)), [])

    def test_an_empty_image_clears_the_setting(self):
        tree = tree_with({"section": {}, "column": {"background_image": ""}})
        self.assertEqual(page_problems(tree, languages=("en",)), [])

    def test_css_significant_characters_are_rejected(self):
        for bad in ("https://x.test/a).png", "https://x.test/a;b", "javascript:alert(1)",
                    "https://x.test/a(png"):
            tree = tree_with({"section": {}, "column": {"background_image": bad}})
            self.assertTrue(page_problems(tree, languages=("en",)), bad)

    def test_other_nodes_cannot_carry_a_background_image(self):
        tree = tree_with({"section": {}, "column": {}})
        tree["children"][0]["children"][0]["children"][0]["settings"] = {
            "desktop": {"background_image": "/x.webp"}}
        self.assertTrue(page_problems(tree, languages=("en",)))


class BackgroundImageRender(unittest.TestCase):
    def test_render_layers_scrim_and_image(self):
        tree = tree_with({"section": {}, "column": {
            "background_image": "https://assets.example/bench.webp", "background_dim": "strong"}})
        html = render_page(tree, lang="en", device="desktop")
        self.assertIn("mz-bg-image", html)
        self.assertIn("72%", html)
        self.assertIn("bench.webp", html)
        self.assertIn("background-image:linear-gradient(", html)

    def test_render_without_dim_is_a_single_layer(self):
        tree = tree_with({"section": {}, "column": {"background_image": "/site_image/bench.webp"}})
        html = render_page(tree, lang="en", device="desktop")
        self.assertIn('url(&quot;/site_image/bench.webp&quot;)', html)
        self.assertNotIn("linear-gradient", html)

    def test_a_bad_url_renders_no_style(self):
        tree = tree_with({"section": {}, "column": {"background_image": "https://x.test/a).png"}})
        html = render_page(tree, lang="en", device="desktop", validate=False)
        self.assertNotIn("mz-bg-image", html)


if __name__ == "__main__":
    unittest.main()


class SurfaceContrastTests(unittest.TestCase):
    """Light surfaces reset foreground to the theme foreground.

    A card or page-background surface nested inside a dark band must not
    inherit the band's light foreground, or its text renders light-on-white.
    """

    def test_card_surface_resets_foreground(self):
        self.assertIn('.mz-background-card{background:var(--card,#fff);color:var(--foreground,#262321)}', _render_mod._BASE_CSS)

    def test_page_surface_resets_foreground(self):
        self.assertIn('.mz-background-background{background:var(--background,#FAF6F0);color:var(--foreground,#262321)}', _render_mod._BASE_CSS)
