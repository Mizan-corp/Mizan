"""Per-device visibility on the single-render visitor route (ADR-015 page engine).

The visitor page renders desktop settings once; a mobile `visible` override
becomes a media-query class instead of a second render pass, matching the
editor's per-device preview (treerender.tsx merges settings per device).
"""

from app.platform.site.render import _BASE_CSS, render_page


def _tree(mobile_visible=None, desktop_visible=None):
    settings = {"desktop": {}}
    if desktop_visible is not None:
        settings["desktop"]["visible"] = desktop_visible
    if mobile_visible is not None:
        settings["mobile"] = {"visible": mobile_visible}
    return {
        "id": "n_root0001", "type": "section", "settings": {"desktop": {}}, "content": {},
        "children": [{
            "id": "n_col00001", "type": "columns", "settings": {"desktop": {"columns": 1}}, "content": {},
            "children": [{
                "id": "n_column01", "type": "column", "settings": {"desktop": {}}, "content": {},
                "children": [{
                    "id": "n_head0001", "type": "heading",
                    "settings": settings,
                    "content": {"en": {"text": "Hello"}, "ar": {"text": "مرحبا"}},
                }],
            }],
        }],
    }


def test_mobile_hidden_node_renders_with_hide_class():
    html = render_page(_tree(mobile_visible=False), lang="en")
    assert "Hello" in html
    assert "mz-hide-mobile" in html


def test_desktop_hidden_mobile_shown_renders_with_show_class():
    html = render_page(_tree(mobile_visible=True, desktop_visible=False), lang="en")
    assert "Hello" in html
    assert "mz-show-mobile" in html


def test_hidden_everywhere_is_skipped():
    html = render_page(_tree(desktop_visible=False), lang="en")
    assert "Hello" not in html
    assert "mz-show-mobile" not in html


def test_no_override_has_no_device_class():
    html = render_page(_tree(), lang="en")
    assert "Hello" in html
    assert "mz-hide-mobile" not in html
    assert "mz-show-mobile" not in html


def test_base_css_carries_the_media_rules():
    assert ".mz-show-mobile{display:none}" in _BASE_CSS
    assert ".mz-hide-mobile{display:none}" in _BASE_CSS
    assert "@media(max-width:768px)" in _BASE_CSS


def test_non_desktop_render_keeps_direct_semantics():
    html = render_page(_tree(mobile_visible=False), lang="en", device="mobile")
    assert "Hello" not in html
