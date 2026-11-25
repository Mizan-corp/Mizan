"""The site page-tree validator is part of the SDK's manifest.py byte copy (ADR-016 D4):
`mizan site-theme` packages exactly what the platform accepts."""
from mizan_sdk.manifest import PAGE_BLOCKS, page_problems


def test_the_page_validator_ships_with_the_sdk():
    assert "section" in PAGE_BLOCKS and "html" in PAGE_BLOCKS
    assert page_problems({"id": "n_x1", "type": "heading"}) == ["the root of a page is a section"]


def test_a_minimal_page_round_trips():
    tree = {"id": "n_root1", "type": "section", "settings": {}, "content": {},
            "children": [{"id": "n_cv01", "type": "canvas", "settings": {}, "content": {},
                          "children": [{"id": "n_hd01", "type": "heading", "settings": {},
                                        "content": {"en": {"text": "Hi"}}}]}]}
    assert page_problems(tree, languages=("ar", "en")) == []


def test_background_image_url_setting():
    column = {"id": "n_col01", "type": "column",
              "settings": {"desktop": {"background_image": "/site_image/bench.webp", "background_dim": "soft"}},
              "content": {}}
    tree = {"id": "n_root1", "type": "section", "settings": {}, "content": {},
            "children": [{"id": "n_cols1", "type": "columns", "settings": {}, "content": {},
                          "children": [column]}]}
    assert page_problems(tree, languages=("en",)) == []
    column["settings"]["desktop"]["background_image"] = "https://x.test/a).png"
    assert page_problems(tree, languages=("en",))
