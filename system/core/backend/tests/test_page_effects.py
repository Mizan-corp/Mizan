"""Visual effects: shadow/gradient/hover registry tokens render as bounded classes
with theme-token CSS; arbitrary tokens are rejected by the manifest."""
import unittest

from app.framework.manifest import page_problems
from app.platform.site.render import render_page, _BASE_CSS


def tree_with(node_type, settings):
    leaf = {"id": "n_leaf01", "type": node_type, "settings": {"desktop": settings}, "content": {}}
    if node_type == "heading":
        leaf["content"] = {"en": {"text": "Hi"}}
    if node_type == "button":
        leaf["content"] = {"en": {"label": "Go", "href": "/x"}}
    return {
        "id": "n_root1", "type": "section", "settings": {"desktop": {}}, "content": {},
        "children": [{
            "id": "n_cols1", "type": "columns", "settings": {"desktop": {}}, "content": {},
            "children": [{"id": "n_col01", "type": "column", "settings": {"desktop": {}}, "content": {}, "children": [leaf]}],
        }],
    }


def tree_section(settings):
    t = tree_with("heading", {})
    t["settings"]["desktop"] = settings
    return t


class Effects(unittest.TestCase):
    def test_a_section_shadow_and_gradient_render(self):
        self.assertEqual(page_problems(tree_section({"shadow": "m", "gradient": "soft"}), languages=("en",)), [])
        html = render_page(tree_section({"shadow": "m", "gradient": "soft"}), lang="en")
        self.assertIn("mz-shadow-m", html)
        self.assertIn("mz-gradient-soft", html)

    def test_b_column_hover_renders(self):
        t = tree_with("heading", {})
        t["children"][0]["children"][0]["settings"]["desktop"] = {"hover": "lift", "shadow": "s"}
        self.assertEqual(page_problems(t, languages=("en",)), [])
        html = render_page(t, lang="en")
        self.assertIn("mz-hover-lift", html)
        self.assertIn("mz-shadow-s", html)

    def test_c_invalid_effect_tokens_rejected(self):
        self.assertNotEqual(page_problems(tree_section({"shadow": "huge"}), languages=("en",)), [])
        self.assertNotEqual(page_problems(tree_section({"gradient": "rainbow"}), languages=("en",)), [])
        t = tree_with("heading", {"hover": "lift"})  # hover not allowed on heading
        self.assertNotEqual(page_problems(t, languages=("en",)), [])

    def test_d_effects_css_is_bounded_to_first_child_and_theme_tokens(self):
        for token in (".mz-node.mz-shadow-s>:first-child{box-shadow:",
                      ".mz-node.mz-shadow-m>:first-child{box-shadow:",
                      ".mz-node.mz-shadow-l>:first-child{box-shadow:",
                      ".mz-node.mz-gradient-soft>:first-child{background-image:linear-gradient(",
                      ".mz-node.mz-gradient-brand>:first-child{background-image:linear-gradient(",
                      ".mz-node.mz-gradient-dark>:first-child{background-image:linear-gradient(",
                      ".mz-node.mz-hover-lift:hover>:first-child{transform:translateY(-3px)",
                      ".mz-node.mz-hover-glow:hover>:first-child{box-shadow:"):
            self.assertIn(token, _BASE_CSS, token)
        self.assertIn("@media(prefers-reduced-motion:reduce){.mz-node.mz-hover-lift:hover>:first-child{transform:none}}", _BASE_CSS)

    def test_e_button_hover_renders(self):
        t = tree_with("button", {"hover": "glow"})
        self.assertEqual(page_problems(t, languages=("en",)), [])
        html = render_page(t, lang="en")
        self.assertIn("mz-hover-glow", html)
