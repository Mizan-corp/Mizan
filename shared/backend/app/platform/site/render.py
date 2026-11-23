"""Renders a published site page tree plus a theme to HTML (ADR-015 step S2,
docs/builder/page-engine.md).

Platform side only: the SDK ships the validator (app/framework/manifest.py, copied byte for
byte), not this renderer. At v0 every block renders from fixed platform templates. The document wrapper uses sandboxed Jinja2; arbitrary theme
templates are not supported by this experimental slice.

Everything the tree carries is untrusted: text is escaped, rich text and html blocks pass
through the allow-list sanitizer, and iframes exist only for video_embed's allow-listed hosts,
CSP response headers still belong to the future site service (ADR-015 D2), not this module. Blocks without per-device
visibility render on every device; the studio and the API validate with page_problems() before
a tree reaches this renderer.
"""
from __future__ import annotations

import html as _html
import nh3
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from app.framework.manifest import PAGE_BLOCKS, page_url, page_problems

# Rich text (the text block) may use these; the html block adds EXTRA_TAGS. No inline styles,
# no event handlers, no scripts: the runtime CSP forbids them, so the sanitizer drops them.
SAFE_TAGS = ("p", "br", "strong", "b", "em", "i", "u", "s", "a", "ul", "ol", "li",
             "blockquote", "code", "pre", "span")
EXTRA_TAGS = ("div", "img", "figure", "figcaption", "table", "thead", "tbody", "tr", "th", "td",
              "h2", "h3", "h4")
VOID_TAGS = ("br", "img", "hr")
# Tags whose whole content is dropped, not just the tag itself.
DROP_CONTENT = ("script", "style", "iframe", "object", "embed", "template", "svg", "math")

RTL = ("ar", "he", "fa", "ur")


def _safe_href(value) -> str | None:
    return value if page_url(value, "href") else None


def _safe_src(value) -> str | None:
    return value if page_url(value, "url") else None


def sanitize_html(markup: str, extra: tuple[str, ...] = ()) -> str:
    """HTML5 parser-based allow list. No styles, classes, events, SVG or frames."""
    if not isinstance(markup, str):
        return ""

    def attribute(tag, name, value):
        if name == "href" and not page_url(value, "href"):
            return None
        if name == "src" and not page_url(value, "url"):
            return None
        return value

    return nh3.clean(markup, tags=set(SAFE_TAGS) | set(extra),
                     clean_content_tags=set(DROP_CONTENT),
                     attributes={"a": {"href", "title"}, "img": {"src", "alt"},
                                 "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"}},
                     attribute_filter=attribute, url_schemes={"https", "http", "mailto", "tel"},
                     strip_comments=True)


def _esc(value) -> str:
    return _html.escape(value if isinstance(value, str) else str(value), quote=True)


def _settings(node: dict, device: str) -> dict:
    """Per-device settings: the device's own over the desktop defaults."""
    per = node.get("settings") or {}
    merged = dict(per.get("desktop") or {})
    if device != "desktop":
        merged.update(per.get(device) or {})
    return merged


def _content(node: dict, lang: str) -> dict:
    return (node.get("content") or {}).get(lang) or {}


_SPACER_PX = {"none": 0, "xs": 8, "s": 16, "m": 32, "l": 64, "xl": 128}


def _render_node_inner(node: dict, lang: str, device: str) -> str:
    ntype = node.get("type")
    if ntype not in PAGE_BLOCKS:
        return ""
    s = _settings(node, device)
    if s.get("visible") is False:
        return ""
    c = _content(node, lang)
    kids = "".join(_render_node(k, lang, device) for k in node.get("children") or [] if isinstance(k, dict))

    if ntype == "section":
        return f'<section class="mz-section">{kids}</section>'
    if ntype == "columns":
        declared = s.get("columns")
        count = declared if isinstance(declared, int) and not isinstance(declared, bool) else 0
        count = count or len(node.get("children") or []) or 1
        stack = " mz-stack" if s.get("stack") else ""
        return f'<div class="mz-columns mz-columns-{int(count)}{stack}">{kids}</div>'
    if ntype == "column":
        return f'<div class="mz-column">{kids}</div>'
    if ntype == "canvas":
        return f'<div class="mz-canvas">{kids}</div>'
    if ntype == "heading":
        level = s.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 6:
            level = 2
        return f'<h{level} class="mz-heading">{_esc(c.get("text", ""))}</h{level}>'
    if ntype == "text":
        return f'<div class="mz-text">{sanitize_html(c.get("html", ""))}</div>'
    if ntype == "image":
        src = _safe_src(c.get("src"))
        if src is None:
            return ""
        return f'<img class="mz-image" src="{_esc(src)}" alt="{_esc(c.get("alt", ""))}" loading="lazy">'
    if ntype == "gallery":
        mode = s.get("mode") if s.get("mode") in ("grid", "slider") else "grid"
        imgs = []
        for entry in c.get("images") or []:
            if not isinstance(entry, dict):
                continue
            src = _safe_src(entry.get("src"))
            if src is not None:
                imgs.append(f'<img src="{_esc(src)}" alt="{_esc(entry.get("alt", ""))}" loading="lazy">')
        return f'<div class="mz-gallery" data-mode="{mode}">{"".join(imgs)}</div>'
    if ntype == "video_embed":
        url = c.get("url")
        if not page_url(url, "embed"):
            return ""
        return (f'<div class="mz-embed" data-aspect="{_esc(s.get("aspect", "16:9"))}">'
                f'<iframe src="{_esc(url)}" loading="lazy" allowfullscreen '
                f'referrerpolicy="strict-origin-when-cross-origin"></iframe></div>')
    if ntype == "button":
        href = _safe_href(c.get("href"))
        if href is None:
            return ""
        style = s.get("style") if s.get("style") in ("primary", "secondary", "ghost") else "primary"
        return f'<a class="mz-button mz-button-{style}" href="{_esc(href)}">{_esc(c.get("label", ""))}</a>'
    if ntype == "icon_list":
        items = []
        for entry in c.get("items") or []:
            if isinstance(entry, dict) and isinstance(entry.get("icon"), str):
                items.append(f'<li><i data-lucide="{_esc(entry["icon"])}"></i> {_esc(entry.get("text", ""))}</li>')
        return f'<ul class="mz-icon-list">{"".join(items)}</ul>'
    if ntype == "spacer":
        return '<div class="mz-spacer" aria-hidden="true"></div>'
    if ntype == "divider":
        style = s.get("style") if s.get("style") in ("solid", "dashed", "dotted") else "solid"
        return f'<hr class="mz-divider mz-divider-{style}">'
    if ntype == "html":
        return f'<div class="mz-html">{sanitize_html(c.get("html", ""), EXTRA_TAGS)}</div>'
    return ""


def _render_node(node: dict, lang: str, device: str) -> str:
    if _settings(node, device).get("visible") is False:
        return ""
    rendered = _render_node_inner(node, lang, device)
    if not rendered:
        return ""
    # Only registry enum tokens become classes, never arbitrary CSS from the tree.
    settings = _settings(node, device)
    schema = PAGE_BLOCKS[node["type"]]["settings"]
    classes = []
    for key, value in settings.items():
        spec = schema.get(key)
        if isinstance(spec, tuple) and spec[0] == "choice" and value in spec[1]:
            classes.append("mz-" + key.replace("_", "-") + "-" + value)
    if settings.get("rounded") is True:
        classes.append("mz-rounded")
    class_value = _esc(" ".join(classes))
    return f'<div id="{_esc(node["id"])}" class="mz-node {class_value}">{rendered}</div>'


_BASE_CSS = """
*{box-sizing:border-box}body{margin:0;background:var(--background,#FAF6F0);color:var(--foreground,#262321);font:18px/1.6 system-ui,sans-serif}
.mz-section{padding:32px;max-width:1200px;margin:auto}.mz-columns{display:grid;gap:24px}.mz-columns-1{grid-template-columns:1fr}.mz-columns-2{grid-template-columns:repeat(2,minmax(0,1fr))}.mz-columns-3{grid-template-columns:repeat(3,minmax(0,1fr))}.mz-columns-4{grid-template-columns:repeat(4,minmax(0,1fr))}.mz-columns-5{grid-template-columns:repeat(5,minmax(0,1fr))}.mz-columns-6{grid-template-columns:repeat(6,minmax(0,1fr))}.mz-stack{grid-template-columns:1fr}
.mz-heading{line-height:1.15;margin:0 0 24px;font-weight:750}h1{font-size:clamp(32px,4.8vw,64px)}.mz-text p{margin:0 0 24px}.mz-image{display:block;width:100%;height:auto}.mz-rounded img{border-radius:16px}.mz-button{display:inline-block;padding:12px 24px;border-radius:8px;text-decoration:none;background:var(--primary,#651E2C);color:var(--primary-foreground,#FAF6F0)}.mz-button-secondary{background:var(--foreground,#262321);color:var(--background,#FAF6F0)}.mz-button-ghost{background:none;color:var(--primary,#651E2C);outline:1px solid currentColor}.mz-icon-list{padding-inline-start:24px;margin:24px 0}.mz-gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.mz-gallery img{width:100%}.mz-gallery[data-mode=slider]{display:flex;overflow:auto;scroll-snap-type:x mandatory}.mz-gallery[data-mode=slider] img{flex:0 0 85%;scroll-snap-align:start}.mz-embed iframe{width:100%;aspect-ratio:16/9;border:0}.mz-embed[data-aspect="4:3"] iframe{aspect-ratio:4/3}.mz-embed[data-aspect="1:1"] iframe{aspect-ratio:1}.mz-divider-dashed{border-style:dashed}.mz-divider-dotted{border-style:dotted}.mz-align-start{text-align:start}.mz-align-center{text-align:center}.mz-align-end{text-align:end}.mz-background-background{background:var(--background,#FAF6F0)}.mz-background-card{background:var(--card,#fff)}.mz-background-primary{background:var(--primary,#651E2C);color:var(--primary-foreground,#FAF6F0)}.mz-max-width-narrow{max-width:720px;margin:auto}.mz-max-width-normal{max-width:1000px;margin:auto}.mz-max-width-wide{max-width:1400px;margin:auto}.mz-max-width-full{max-width:none}.mz-width-auto{width:auto}.mz-width-full{width:100%}.mz-width-half{width:50%}.mz-width-third{width:33.333%}.mz-width-two_thirds{width:66.666%}.mz-min-height-s{min-height:240px}.mz-min-height-m{min-height:480px}.mz-min-height-l{min-height:720px}.mz-canvas{position:relative;display:flex;flex-wrap:wrap;gap:16px}
"""
for _token, _size in _SPACER_PX.items():
    _BASE_CSS += f".mz-padding-{_token}{{padding:{_size}px}}.mz-gap-{_token}{{gap:{_size}px}}.mz-height-{_token} .mz-spacer{{height:{_size}px}}"


def render_page(tree: dict, lang: str = "ar", device: str = "desktop", validate: bool = True) -> str:
    """The page body: every visible block of the published tree, in order."""
    if validate and page_problems(tree):
        raise ValueError("render_page() takes a tree that passed page_problems()")
    return _render_node(tree, lang, device)


def _theme_style(theme: dict | None) -> str:
    """Constrained v0 palette: known tokens with hex colors only; no CSS expressions."""
    import re

    if not isinstance(theme, dict) or not isinstance(theme.get("colors"), dict):
        return ""
    colors = theme["colors"].get("light")
    if not isinstance(colors, dict):
        return ""
    allowed = {"background", "foreground", "card", "primary", "primary-foreground"}
    variables = [f"--{token}:{value}" for token, value in colors.items()
                 if token in allowed and isinstance(value, str)
                 and re.fullmatch(r"#[0-9a-fA-F]{6}", value)]
    return "<style>:root{" + ";".join(variables) + "}</style>" if variables else ""


_DOCUMENT = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined).from_string(
    '<!doctype html>\n<html lang="{{ language }}" dir="{{ direction }}">\n'
    '<head>{{ head | safe }}</head>\n<body>{{ body | safe }}</body>\n</html>\n')


def render_document(tree: dict, meta: dict, theme: dict | None = None, lang: str = "ar",
                    device: str = "desktop") -> str:
    """A full HTML document: SEO head (title and description per language, canonical, hreflang,
    Open Graph) plus the rendered page. `meta`: {"canonical": url, "titles": {lang: …},
    "descriptions": {lang: …}, "languages": [codes]}."""
    titles = meta.get("titles") or {}
    descriptions = meta.get("descriptions") or {}
    title = titles.get(lang) or next(iter(titles.values()), "")
    description = descriptions.get(lang) or next(iter(descriptions.values()), "")
    canonical = meta.get("canonical") if page_url(meta.get("canonical"), "url") else ""
    direction = "rtl" if lang.split("-")[0] in RTL else "ltr"

    head = [f'<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{_esc(title)}</title>"]
    if description:
        head.append(f'<meta name="description" content="{_esc(description)}">')
    if canonical:
        head.append(f'<link rel="canonical" href="{_esc(canonical)}">')
        head.append(f'<meta property="og:url" content="{_esc(canonical)}">')
    alternates = meta.get("alternates")
    if isinstance(alternates, dict):
        for code, url in alternates.items():
            if isinstance(code, str) and page_url(url, "url"):
                head.append(f'<link rel="alternate" hreflang="{_esc(code)}" href="{_esc(url)}">')
    head.append('<meta property="og:type" content="website">')
    if title:
        head.append(f'<meta property="og:title" content="{_esc(title)}">')
    if description:
        head.append(f'<meta property="og:description" content="{_esc(description)}">')

    body = render_page(tree, lang=lang, device=device)
    return _DOCUMENT.render(language=lang, direction=direction,
                            head="\n".join(head) + _theme_style(theme) + "<style>" + _BASE_CSS + "</style>", body=body)
