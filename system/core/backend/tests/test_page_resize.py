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
        self.assertIn(".mz-columns.mz-cols-custom{grid-template-columns:var(--mz-tracks-m,1fr)}", _BASE_CSS)


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
        self.assertIn(".mz-node.mz-minh-custom>:first-child{min-height:var(--mz-minh,0)}", _BASE_CSS)


if __name__ == "__main__":
    unittest.main()


def tree_with_heading(heading_settings):
    return {
        "id": "n_root1", "type": "section",
        "settings": {"desktop": {}}, "content": {},
        "children": [{
            "id": "n_cols1", "type": "columns",
            "settings": {"desktop": {}}, "content": {},
            "children": [
                {"id": "n_col01", "type": "column", "settings": {}, "content": {},
                 "children": [{"id": "n_hd001", "type": "heading", "settings": {"desktop": heading_settings},
                               "content": {"en": {"text": "Hi"}}}]},
            ],
        }],
    }


class WidthPct(unittest.TestCase):
    def test_h_width_pct_is_valid_and_renders(self):
        self.assertEqual(page_problems(tree_with_heading({"width_pct": 63}), languages=("en",)), [])
        html = render_page(tree_with_heading({"width_pct": 63}), lang="en")
        self.assertIn("mz-width-custom", html)
        self.assertIn("--mz-width:63%", html)

    def test_i_width_pct_bounds(self):
        for bad in (9, 101, 63.5, "63", True):
            self.assertNotEqual(page_problems(tree_with_heading({"width_pct": bad}), languages=("en",)), [], bad)

    def test_j_mobile_collapses_custom_width(self):
        from app.platform.site.render import _BASE_CSS
        self.assertIn(".mz-node.mz-width-custom{width:var(--mz-width-m,100%)}", _BASE_CSS)


    def test_k_mobile_segment_width_renders_as_its_own_var(self):
        tree = tree_with_heading({"width_pct": 70})
        tree["children"][0]["children"][0]["children"][0]["settings"]["mobile"] = {"width_pct": 90}
        html = render_page(tree, lang="en")
        self.assertIn("--mz-width:70%", html)
        self.assertIn("--mz-width-m:90%", html)

    def test_l_mobile_segment_tracks_render_as_their_own_var(self):
        tree = tree_with_row({"tracks": [2, 1]})
        tree["children"][0]["settings"]["mobile"] = {"tracks": [1, 2]}
        html = render_page(tree, lang="en")
        self.assertIn("--mz-tracks:2fr 1fr", html)
        self.assertIn("--mz-tracks-m:1fr 2fr", html)

    def test_m_fit_width_choice_renders_bounded_class(self):
        self.assertEqual(page_problems(tree_with_heading({"width": "fit"}), languages=("en",)), [])
        html = render_page(tree_with_heading({"width": "fit"}), lang="en")
        self.assertIn("mz-width-fit", html)
        from app.platform.site.render import _BASE_CSS
        self.assertIn(".mz-node.mz-width-fit{width:fit-content", _BASE_CSS)

    def test_n_mobile_only_width_still_emits_the_bounded_class(self):
        tree = tree_with_heading({})
        tree["children"][0]["children"][0]["children"][0]["settings"] = {"mobile": {"width_pct": 55}}
        html = render_page(tree, lang="en")
        self.assertIn("mz-width-custom", html)
        self.assertIn("--mz-width-m:55%", html)
        self.assertNotIn("--mz-width:", html)

    def test_o_mobile_only_tracks_emit_the_mobile_class(self):
        tree = tree_with_row({})
        tree["children"][0]["settings"]["mobile"] = {"tracks": [1, 2]}
        html = render_page(tree, lang="en")
        self.assertIn("mz-cols-custom-m", html)
        self.assertIn("--mz-tracks-m:1fr 2fr", html)
        from app.platform.site.render import _BASE_CSS
        self.assertIn(".mz-columns.mz-cols-custom-m{grid-template-columns:var(--mz-tracks-m)}", _BASE_CSS)
