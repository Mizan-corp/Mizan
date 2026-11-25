"""Free sizing from border drags: row track ratios and px min-height. Numeric
values only, emitted as CSS variables on bounded classes — never arbitrary CSS."""
import unittest

from app.framework.manifest import page_problems
from app.platform.site.render import render_page


def tree_with_row(row_settings, col_settings=None):
    return {
        "id": "n_root1", "type": "section",
        "settings": {"desktop": {}}, "content": {},
        "children": [{
            "id": "n_cols1", "type": "columns",
            "settings": {"desktop": row_settings}, "content": {},
            "children": [
                {"id": "n_col01", "type": "column", "settings": {"desktop": col_settings or {}}, "content": {},
                 "children": [{"id": "n_hd001", "type": "heading", "settings": {},
                               "content": {"en": {"text": "Hi"}}}]},
                {"id": "n_col02", "type": "column", "settings": {}, "content": {},
                 "children": [{"id": "n_hd002", "type": "heading", "settings": {},
                               "content": {"en": {"text": "Yo"}}}]},
            ],
        }],
    }


class TrackRatios(unittest.TestCase):
    def test_a_tracks_are_a_valid_columns_setting(self):
        self.assertEqual(page_problems(tree_with_row({"tracks": [2, 1]}), languages=("en",)), [])
        self.assertEqual(page_problems(tree_with_row({"tracks": [1.5, 1, 0.75]}), languages=("en",)), [])

    def test_b_tracks_render_as_a_css_variable_on_a_bounded_class(self):
        html = render_page(tree_with_row({"tracks": [2, 1]}), lang="en")
        self.assertIn("mz-cols-custom", html)
        self.assertIn("--mz-tracks:2fr 1fr", html)

    def test_c_invalid_tracks_are_rejected(self):
        for bad in ([99, 1], [0.1, 1], [1], [1] * 7, ["2", 1], [True, 1], "2fr 1fr"):
            self.assertNotEqual(page_problems(tree_with_row({"tracks": bad}), languages=("en",)), [], bad)

    def test_d_mismatched_track_count_renders_equal_columns(self):
        html = render_page(tree_with_row({"tracks": [2, 1, 1]}), lang="en", validate=False)
        self.assertNotIn("mz-cols-custom", html)

    def test_e_mobile_collapses_custom_tracks(self):
        from app.platform.site.render import _BASE_CSS
        self.assertIn(".mz-columns.mz-cols-custom{grid-template-columns:1fr}", _BASE_CSS)


class MinHeightPx(unittest.TestCase):
    def test_f_min_height_px_is_valid_and_renders(self):
        self.assertEqual(page_problems(tree_with_row({}, {"min_height_px": 300}), languages=("en",)), [])
        html = render_page(tree_with_row({}, {"min_height_px": 300}), lang="en")
        self.assertIn("mz-minh-custom", html)
        self.assertIn("--mz-minh:300px", html)

    def test_g_min_height_px_bounds(self):
        for bad in (39, 1201, 300.5, "300", True):
            self.assertNotEqual(page_problems(tree_with_row({}, {"min_height_px": bad}), languages=("en",)), [], bad)

    def test_h_min_height_rule_applies_to_the_inner_element(self):
        from app.platform.site.render import _BASE_CSS
        self.assertIn(".mz-node.mz-minh-custom>:first-child{min-height:var(--mz-minh)}", _BASE_CSS)


if __name__ == "__main__":
    unittest.main()
