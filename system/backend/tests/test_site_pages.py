"""The site page tree and block registry v0 (ADR-015 step S2, docs/builder/page-engine.md):
validation shared with the SDK byte for byte, and the server renderer."""
import copy
from pathlib import Path

from app.framework.manifest import PAGE_BLOCKS, PAGE_EMBED_HOSTS, page_problems
from app.platform.site.render import render_document, render_page, sanitize_html

ROOT = Path(__file__).resolve().parents[3]


def page(**over):
    tree = {
        "id": "n_root1", "type": "section",
        "settings": {"desktop": {"visible": True, "padding": "m"}},
        "content": {},
        "children": [{
            "id": "n_cols1", "type": "columns", "settings": {"desktop": {"columns": 2}, "mobile": {"stack": True}},
            "content": {},
            "children": [{
                "id": "n_col1", "type": "column", "settings": {}, "content": {},
                "children": [
                    {"id": "n_head1", "type": "heading",
                     "settings": {"desktop": {"level": 1}},
                     "content": {"ar": {"text": "أهلاً"}, "en": {"text": "Welcome"}}},
                    {"id": "n_text1", "type": "text", "settings": {},
                     "content": {"ar": {"html": "<p>نص <strong>عريض</strong></p>"}}},
                    {"id": "n_btn1", "type": "button",
                     "settings": {"desktop": {"style": "primary"}},
                     "content": {"ar": {"label": "اطلب الآن", "href": "/contact"}}},
                ]},
                {"id": "n_col2", "type": "column", "settings": {}, "content": {},
                 "children": [{"id": "n_img1", "type": "image", "settings": {"desktop": {"rounded": True}},
                               "content": {"ar": {"src": "/media/hero.jpg", "alt": "واجهة"}}}]},
            ]}],
    }
    tree.update(over)
    return tree


def test_a_well_formed_page_validates():
    assert page_problems(page()) == []
    assert page_problems(page(), languages=("ar", "en")) == []


def test_the_registry_covers_the_contract_blocks():
    assert set(PAGE_BLOCKS) == {"section", "columns", "column", "canvas", "heading", "text", "image",
                                "gallery", "video_embed", "button", "icon_list", "spacer", "divider", "html"}
    assert all(b["version"] == 1 for b in PAGE_BLOCKS.values())


def test_the_root_is_a_section():
    assert page_problems({"id": "n_x1", "type": "heading"}) == ["the root of a page is a section"]
    assert page_problems("not a tree") == ["the page tree must be a JSON object"]


def test_unknown_and_misplaced_blocks_fail():
    bad = page()
    bad["children"][0]["children"][0]["children"][0] = {"id": "n_qq01", "type": "carousel"}
    assert any("unknown block type" in p for p in page_problems(bad))
    bad = page()
    bad["children"].append({"id": "n_hd09", "type": "heading", "settings": {}, "content": {}})
    assert any("can't sit here" in p for p in page_problems(bad))
    bad = page()
    bad["children"][0]["children"][0]["children"].append(
        {"id": "n_sc09", "type": "section", "settings": {}, "content": {}, "children": []})
    assert any("can't sit here" in p for p in page_problems(bad))


def test_one_canvas_per_page():
    def canvas(nid):
        return {"id": nid, "type": "canvas", "settings": {}, "content": {}, "children": []}

    good = page()
    good["children"] = [canvas("n_cv01")]
    assert page_problems(good) == []
    bad = page()
    bad["children"] = [canvas("n_cv01"), canvas("n_cv02")]
    assert any("at most one canvas" in p for p in page_problems(bad))


def test_node_ids_are_unique_and_well_formed():
    bad = page()
    bad["children"][0]["children"][0]["id"] = "n_root1"
    assert any("already used" in p for p in page_problems(bad))
    bad = page()
    bad["children"][0]["id"] = "columns-1"
    assert any("id must look like" in p for p in page_problems(bad))


def test_settings_stay_typed_and_per_device():
    bad = page()
    bad["settings"]["desktop"]["padding"] = "huge"
    assert any("must be one of" in p for p in page_problems(bad))
    bad = page()
    bad["settings"]["desktop"]["surprise"] = True
    assert any("isn't a section setting" in p for p in page_problems(bad))
    bad = page()
    bad["settings"]["wrist"] = {"visible": True}
    assert any("isn't a device" in p for p in page_problems(bad))
    bad = page()
    bad["children"][0]["settings"]["desktop"]["columns"] = 9
    assert any("between 1 and 6" in p for p in page_problems(bad))
    bad = page()
    bad["children"][0]["settings"]["desktop"]["stack"] = "yes"
    assert any("true or false" in p for p in page_problems(bad))


def test_content_stays_in_declared_fields_and_languages():
    bad = page()
    bad["children"][0]["children"][0]["children"][0]["content"]["ar"]["novel"] = "x"
    assert any("isn't a heading content field" in p for p in page_problems(bad))
    bad = page()
    bad["children"][0]["children"][0]["children"][0]["content"]["klingon!"] = {"text": "x"}
    assert any("isn't a language code" in p for p in page_problems(bad))
    bad = page()
    assert any("has no 'en' language" in p for p in page_problems(bad, languages=("ar",)))


def test_links_and_embeds_stay_safe():
    bad = page()
    bad["children"][0]["children"][0]["children"][2]["content"]["ar"]["href"] = "javascript:alert(1)"
    assert any("permitted href link" in p for p in page_problems(bad))
    good = page()
    good["children"][0]["children"][0]["children"][2]["content"]["ar"]["href"] = "tel:+201234"
    assert page_problems(good) == []
    bad = page()
    bad["children"][0]["children"][0]["children"].append(
        {"id": "n_vd01", "type": "video_embed", "settings": {},
         "content": {"ar": {"url": "https://evil.example/track"}}})
    assert any("embed hosts" in p for p in page_problems(bad))
    good = page()
    good["children"][0]["children"][0]["children"].append(
        {"id": "n_vd01", "type": "video_embed", "settings": {},
         "content": {"ar": {"url": "https://www.youtube.com/embed/abc"}}})
    assert page_problems(good) == []
    bad = page()
    bad["children"][0]["children"][1]["children"][0]["content"]["ar"]["src"] = "javascript:x"
    assert any("permitted url" in p for p in page_problems(bad))


def test_pages_stay_within_size_limits():
    bad = page()
    bad["children"][0]["children"][0]["children"] = [
        {"id": f"n_s{i:05x}", "type": "spacer", "settings": {}, "content": {}} for i in range(501)]
    assert any("at most 500 blocks" in p for p in page_problems(bad))


def test_the_sdk_ships_this_validator_byte_for_byte():
    backend = ROOT / "shared" / "backend" / "app" / "framework" / "manifest.py"
    sdk = ROOT / "sdk" / "python" / "mizan_sdk" / "manifest.py"
    assert backend.read_bytes() == sdk.read_bytes()


def test_the_renderer_escapes_and_sanitizes():
    tree = page()
    tree["children"][0]["children"][0]["children"][0]["content"]["en"]["text"] = '<img onerror="x">'
    tree["children"][0]["children"][0]["children"][1]["content"]["ar"]["html"] = (
        '<p onclick="x">ok <a href="javascript:alert(1)">bad</a><script>alert(2)</script></p>')
    body = render_page(tree, lang="ar")
    assert "<script>" not in body and "onclick" not in body and "javascript:" not in body
    assert "bad</a></p>" in body  # the bad href and script are gone, the text stays
    en = render_page(tree, lang="en")
    assert "&lt;img onerror=" in en  # heading text is escaped, never markup


def test_sanitize_html_keeps_the_allow_list():
    out = sanitize_html('<p>a <em>b</em> <a href="https://x.test" title="t">c</a></p>'
                        '<iframe src="https://evil.example"></iframe><style>body{}</style>'
                        '<div>d</div><img src="https://x.test/i.png" alt="i" onerror="x">')
    assert "<p>a <em>b</em> " in out and 'href="https://x.test"' in out
    assert "iframe" not in out and "style" not in out and "onerror" not in out
    assert "<div>" not in out  # div needs the html block's extra list
    assert "<img" not in out
    out = sanitize_html('<div><img src="https://x.test/i.png" alt="i"></div>', ("div", "img"))
    assert out == '<div><img src="https://x.test/i.png" alt="i"></div>'


def test_the_renderer_respects_device_visibility():
    tree = page()
    tree["children"][0]["children"][0]["children"][0]["settings"] = {
        "desktop": {"level": 1, "visible": True}, "mobile": {"visible": False}}
    assert "mz-heading" in render_page(tree, device="desktop")
    assert "mz-heading" not in render_page(tree, device="mobile")
    assert "mz-stack" in render_page(tree, device="mobile")  # the mobile stack setting applies


def test_video_embeds_render_only_allow_listed_hosts():
    tree = page()
    kids = tree["children"][0]["children"][0]["children"]
    kids.append({"id": "n_vd01", "type": "video_embed", "settings": {},
                 "content": {"ar": {"url": "https://www.youtube-nocookie.com/embed/abc"}}})
    kids.append({"id": "n_vd02", "type": "video_embed", "settings": {},
                 "content": {"ar": {"url": "https://evil.example/x"}}})
    tree["children"][0]["children"][0]["children"] = [k for k in kids if k.get("type") != "video_embed"
                                                      or "youtube" in k["content"]["ar"]["url"]]
    body = render_page(tree)
    assert body.count("<iframe") == 1 and "youtube-nocookie" in body and "evil.example" not in body
    assert set(PAGE_EMBED_HOSTS)  # the registry names the hosts


def test_render_document_has_seo_basics():
    doc = render_document(page(), {"canonical": "https://shop.example/",
                                   "titles": {"ar": "الرئيسية", "en": "Home"},
                                   "descriptions": {"ar": "وصف", "en": "About us"},
                                   "alternates": {"ar": "https://shop.example/ar", "en": "https://shop.example/en"}}, lang="ar")
    assert doc.startswith("<!doctype html>") and 'lang="ar"' in doc and 'dir="rtl"' in doc
    assert "<title>الرئيسية</title>" in doc and 'name="description"' in doc
    assert 'rel="canonical" href="https://shop.example/"' in doc
    assert 'hreflang="en"' in doc and 'property="og:title"' in doc
    en = render_document(page(), {"canonical": "https://shop.example/en", "titles": {"en": "Home"},
                                  "descriptions": {"en": "About us"}}, lang="en")
    assert 'dir="ltr"' in en and "<title>Home</title>" in en


def test_render_document_styles_the_theme():
    theme = {"colors": {"light": {"background": "#FAF6F0", "primary": "#651E2C",
                                  "bad);token": "red", "injected": "red; } body {"}}}
    doc = render_document(page(), {"titles": {"ar": "ت"}}, theme=theme)
    assert "--background:#FAF6F0" in doc and "--primary:#651E2C" in doc
    assert "injected" not in doc and "bad);token" not in doc


def test_the_renderer_refuses_an_invalid_tree():
    assert page_problems({"id": "n_x1", "type": "heading"})
    try:
        render_page({"id": "n_x1", "type": "heading"})
        assert False, "an invalid tree must not render"
    except ValueError:
        pass


def test_gallery_and_icon_list_render():
    tree = page()
    tree["children"][0]["children"][0]["children"].extend([
        {"id": "n_gl01", "type": "gallery", "settings": {"desktop": {"mode": "slider"}},
         "content": {"ar": {"images": [{"src": "/media/a.jpg", "alt": "أ"}, {"src": "x", "alt": "no"},
                                       "junk"]}}},
        {"id": "n_ic01", "type": "icon_list", "settings": {},
         "content": {"ar": {"items": [{"icon": "Check", "text": "ضمان"}, {"icon": "NoSuchGlyph", "text": "س"}]}}},
        {"id": "n_dv01", "type": "divider", "settings": {}, "content": {}},
        {"id": "n_sp01", "type": "spacer", "settings": {"desktop": {"height": "l"}}, "content": {}},
    ])
    body = render_page(tree, validate=False)  # the renderer stays defensive about stored junk
    assert 'data-mode="slider"' in body and body.count("<img") == 2  # hero + one good gallery image
    assert 'data-lucide' not in body and body.count('class="mz-icon"') == 2 and "ضمان" in body
    assert '<circle cx="12" cy="12" r="5"/>' in body  # unknown stored names render as a fallback dot
    assert 'mz-divider-solid' in body and "mz-height-l" in body


def test_adversarial_urls_never_pass():
    kids = page()["children"][0]["children"][0]["children"]
    button = kids[2]["content"]["ar"]
    for href in ("javascript:alert(1)", "JAVASCRIPT:alert(1)", "  javascript:alert(1)",
                 "jav&#x61;script:alert(1)", "java\tscript:alert(1)", "java\x00script:alert(1)",
                 "data:text/html,<script>alert(1)</script>", "vbscript:x"):
        button["href"] = href
        bad = page()
        bad["children"][0]["children"][0]["children"][2]["content"]["ar"]["href"] = href
        assert any("link" in p for p in page_problems(bad)), href
    button["href"] = "/contact"

    for url in ("http://www.youtube.com/embed/x",          # plain http
                "https://evil.youtube.com/x",              # lookalike subdomain
                "https://www.youtube.com.evil.com/x",      # suffix lookalike
                "https://www.youtube.com@evil.com/x",      # userinfo trick
                "//www.youtube.com/embed/x",               # protocol-relative
                "data:text/html,<script>x</script>"):
        bad = page()
        bad["children"][0]["children"][0]["children"].append(
            {"id": "n_vd09", "type": "video_embed", "settings": {},
             "content": {"ar": {"url": url}}})
        assert any("embed" in p for p in page_problems(bad)), url
    ok = page()
    ok["children"][0]["children"][0]["children"].append(
        {"id": "n_vd09", "type": "video_embed", "settings": {},
         "content": {"ar": {"url": "https://WWW.YOUTUBE.COM/embed/x"}}})  # hosts are case-insensitive
    assert page_problems(ok) == []


def test_adversarial_markup_survives_the_sanitizer():
    # obfuscated scripts, nested drop-content, self-closing foreign tags, attribute breakouts
    out = sanitize_html('<a href="jav&#x61;script:alert(1)">x</a>'
                        '<a href="JAVASCRIPT:alert(1)">y</a>'
                        '<p><script><script>alert(1)</script></script>after</p>'
                        '<svg onload="x"/><b>keep</b>'
                        '<scr<script>ipt>alert(1)</scr<script>ipt>'
                        '<!-- comment --><p title="&quot; onmouseover=&quot;x">t</p>')
    assert "javascript" not in out.lower() and "<script" not in out and "onload" not in out
    assert "after" in out and "<b>keep</b>" in out  # self-closing svg leaves no dangling drop
    assert '" onmouseover="' not in out and "<!--" not in out
    out = sanitize_html("<p>unclosed<script>rest", ())  # an unclosed script swallows its own tail only
    assert "<p>unclosed" in out and "rest" not in out


def test_adversarial_tree_values_never_crash_the_renderer():
    tree = page()
    kids = tree["children"][0]["children"][0]["children"]
    kids[0]["content"]["en"]["text"] = '" onmouseover="x'          # quote breakout attempt
    kids[1]["content"]["ar"]["html"] = 12345                         # wrong type entirely
    kids.append({"id": "n_img09", "type": "image", "settings": {"desktop": {"width": [1]}},
                 "content": {"en": {"src": "https://x.test/\"><script>", "alt": '\" onerror="x'}}})
    tree["children"][0]["settings"]["desktop"]["columns"] = "three"  # wrong type
    body = render_page(tree, lang="en", validate=False)             # must not raise
    assert '" onmouseover="' not in body and "<script>" not in body  # no unescaped breakout
    assert 'src="https://x.test/' not in body                     # quotes are escaped in attributes
    assert "mz-columns" in body                                      # falls back to child count


def test_copy_of_page_does_not_leak_between_renders():
    tree = page()
    snapshot = copy.deepcopy(tree)
    render_page(tree)
    render_document(tree, {"titles": {"ar": "ت"}})
    assert tree == snapshot
