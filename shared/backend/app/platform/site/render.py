"""Renders a published site page tree plus a theme to HTML (ADR-015 step S2,
docs/builder/page-engine.md).

Platform side only: the SDK ships the validator (app/framework/manifest.py, copied byte for
byte), not this renderer. At v0 every block renders from the platform templates here; theme HTML
templates in a sandboxed Jinja2 environment land with site themes (ADR-015 D6) at S5.

Everything the tree carries is untrusted: text is escaped, rich text and html blocks pass
through the allow-list sanitizer, and iframes exist only for video_embed's allow-listed hosts,
so this output is what the site runtime CSP (ADR-015 D7) permits. Blocks without per-device
visibility render on every device; the studio and the API validate with page_problems() before
a tree reaches this renderer.
"""
from __future__ import annotations

import html as _html
from html.parser import HTMLParser

from app.framework.manifest import PAGE_BLOCKS, PAGE_EMBED_HOSTS, color_rgb, page_problems

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
    if not isinstance(value, str) or len(value) > 2000:
        return None
    if value.startswith(("https://", "http://", "mailto:", "tel:", "/", "#")):
        return value
    return None


def _safe_src(value) -> str | None:
    if not isinstance(value, str) or len(value) > 2000:
        return None
    if value.startswith(("https://", "http://", "/")):
        return value
    return None


class _Sanitizer(HTMLParser):
    def __init__(self, extra: tuple[str, ...] = ()):
        super().__init__(convert_charrefs=True)
        self.allowed = set(SAFE_TAGS) | set(extra)
        self.out: list[str] = []
        self.dropping = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.dropping += 1
            return
        if self.dropping or tag not in self.allowed:
            return
        kept = []
        for name, value in attrs:
            if value is None or name.startswith("on"):
                continue
            if tag == "a" and name in ("href", "title"):
                if name == "href":
                    value = _safe_href(value)
                    if value is None:
                        continue
                kept.append((name, value))
            elif tag == "img" and name in ("src", "alt"):
                if name == "src":
                    value = _safe_src(value)
                    if value is None:
                        continue
                kept.append((name, value))
            elif tag in ("td", "th") and name in ("colspan", "rowspan") and value.isdigit():
                kept.append((name, value))
        rendered = "".join(f' {name}="{_html.escape(value, quote=True)}"' for name, value in kept)
        self.out.append(f"<{tag}{rendered}>")

    def handle_startendtag(self, tag, attrs):
        if tag in DROP_CONTENT:
            return  # self-closing: nothing to drop, and no dangling drop state
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self.dropping = max(0, self.dropping - 1)
            return
        if self.dropping or tag not in self.allowed or tag in VOID_TAGS:
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.dropping:
            self.out.append(_html.escape(data))


def sanitize_html(markup: str, extra: tuple[str, ...] = ()) -> str:
    """Rich text reduced to the allow list: formatting tags survive, scripts, event handlers,
    javascript: links and foreign iframes do not (page-engine.md, html block)."""
    if not isinstance(markup, str):
        return ""
    parser = _Sanitizer(extra)
    parser.feed(markup)
    parser.close()
    return "".join(parser.out)


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


def _render_node(node: dict, lang: str, device: str) -> str:
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
        host = None
        if isinstance(url, str) and url.startswith("https://"):
            host = url[len("https://"):].split("/", 1)[0].split(":", 1)[0].lower() or None
        if host not in PAGE_EMBED_HOSTS:
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
        height = s.get("height")
        px = _SPACER_PX.get(height, 32) if isinstance(height, str) else 32
        return f'<div class="mz-spacer" aria-hidden="true" style="height:{px}px"></div>'
    if ntype == "divider":
        style = s.get("style") if s.get("style") in ("solid", "dashed", "dotted") else "solid"
        return f'<hr class="mz-divider mz-divider-{style}">'
    if ntype == "html":
        return f'<div class="mz-html">{sanitize_html(c.get("html", ""), EXTRA_TAGS)}</div>'
    return ""


def render_page(tree: dict, lang: str = "ar", device: str = "desktop", validate: bool = True) -> str:
    """The page body: every visible block of the published tree, in order."""
    if validate and page_problems(tree):
        raise ValueError("render_page() takes a tree that passed page_problems()")
    return _render_node(tree, lang, device)


def _theme_style(theme: dict | None) -> str:
    """The theme's colors as CSS variables. Only values that parse as colors are emitted."""
    if not isinstance(theme, dict):
        return ""
    colors = (theme.get("colors") or {}).get("light") or {}
    variables = []
    for token, value in colors.items():
        if isinstance(token, str) and token.replace("-", "").isalnum() and color_rgb(value) is not None:
            variables.append(f"--{token}:{value}")
    if not variables:
        return ""
    return "<style>:root{" + ";".join(variables) + "}</style>"


def render_document(tree: dict, meta: dict, theme: dict | None = None, lang: str = "ar",
                    device: str = "desktop") -> str:
    """A full HTML document: SEO head (title and description per language, canonical, hreflang,
    Open Graph) plus the rendered page. `meta`: {"canonical": url, "titles": {lang: …},
    "descriptions": {lang: …}, "languages": [codes]}."""
    titles = meta.get("titles") or {}
    descriptions = meta.get("descriptions") or {}
    title = titles.get(lang) or next(iter(titles.values()), "")
    description = descriptions.get(lang) or next(iter(descriptions.values()), "")
    canonical = meta.get("canonical") if isinstance(meta.get("canonical"), str) else ""
    direction = "rtl" if lang.split("-")[0] in RTL else "ltr"

    head = [f'<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{_esc(title)}</title>"]
    if description:
        head.append(f'<meta name="description" content="{_esc(description)}">')
    if canonical:
        head.append(f'<link rel="canonical" href="{_esc(canonical)}">')
        head.append(f'<meta property="og:url" content="{_esc(canonical)}">')
    for code in meta.get("languages") or []:
        if isinstance(code, str) and canonical:
            head.append(f'<link rel="alternate" hreflang="{_esc(code)}" href="{_esc(canonical)}">')
    head.append('<meta property="og:type" content="website">')
    if title:
        head.append(f'<meta property="og:title" content="{_esc(title)}">')
    if description:
        head.append(f'<meta property="og:description" content="{_esc(description)}">')

    body = render_page(tree, lang=lang, device=device)
    return ("<!doctype html>\n"
            f'<html lang="{_esc(lang)}" dir="{direction}">\n<head>\n' + "\n".join(head)
            + _theme_style(theme) + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n")
