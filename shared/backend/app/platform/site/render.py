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
import re

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


_ACCENT = re.compile(r"<mark>([^<]{0,120}?)</mark>")


def _accented(text: str) -> str:
    """Bounded heading accent: only literal <mark>..</mark> pairs (no attributes,
    no nesting, no other markup) become accent spans; everything else escapes."""
    if "<mark>" not in text:
        return _esc(text)
    out, pos = [], 0
    for m in _ACCENT.finditer(text):
        out.append(_esc(text[pos:m.start()]))
        out.append("<mark>" + _esc(m.group(1)) + "</mark>")
        pos = m.end()
    out.append(_esc(text[pos:]))
    return "".join(out)


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


def _render_node_inner(node: dict, lang: str, device: str, link_base: str | None = None) -> str:
    ntype = node.get("type")
    if ntype not in PAGE_BLOCKS:
        return ""
    s = _settings(node, device)
    if s.get("visible") is False:
        return ""
    c = _content(node, lang)
    kids = "".join(_render_node(k, lang, device, link_base) for k in node.get("children") or [] if isinstance(k, dict))

    if ntype == "section":
        return f'<section class="mz-section">{kids}</section>'
    if ntype == "columns":
        declared = s.get("columns")
        count = declared if isinstance(declared, int) and not isinstance(declared, bool) else 0
        count = count or len(node.get("children") or []) or 1
        stack = " mz-stack" if s.get("stack") else ""
        if s.get("reverse") is True:
            kids = "".join(_render_node(k, lang, device, link_base) for k in reversed(node.get("children") or []) if isinstance(k, dict))
        return f'<div class="mz-columns mz-columns-{int(count)}{stack}">{kids}</div>'
    if ntype == "column":
        return f'<div class="mz-column">{kids}</div>'
    if ntype == "canvas":
        return f'<div class="mz-canvas">{kids}</div>'
    if ntype == "heading":
        level = s.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 6:
            level = 2
        return f'<h{level} class="mz-heading">{_accented(c.get("text", ""))}</h{level}>'
    if ntype == "text":
        variant = s.get("variant") if s.get("variant") in ("eyebrow", "note", "check_list") else ""
        cls = f"mz-text mz-text-{variant}" if variant else "mz-text"
        return f'<div class="{cls}">{sanitize_html(c.get("html", ""))}</div>'
    if ntype == "image":
        src = _safe_src(c.get("src"))
        if src is None:
            # Registered decorative art, a durable settings token in the tree - never
            # silently dropped media. "none" renders nothing, as before.
            art = s.get("art") if s.get("art") in ("sculpture", "sculpture_alt") else ""
            if not art:
                return ""
            cls = "mz-art mz-art-" + art.replace("_", "-")
            return (f'<div class="{cls}" role="img" aria-label="{_esc(c.get("alt", ""))}">'
                    f'<div class="mz-art-orb"></div><div class="mz-art-plinth"></div></div>')
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
        href = _site_link(href, link_base)
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


def _render_node(node: dict, lang: str, device: str, link_base: str | None = None) -> str:
    if _settings(node, device).get("visible") is False:
        return ""
    rendered = _render_node_inner(node, lang, device, link_base)
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
.mz-heading{line-height:1.15;margin:0 0 24px;font-weight:750}.mz-heading mark{background:none;color:var(--primary,#651E2C)}h1{font-size:clamp(32px,4.8vw,64px)}h2.mz-heading{font-size:clamp(26px,3vw,38px)}h3.mz-heading{font-size:clamp(21px,2.2vw,27px)}.mz-text p{margin:0 0 24px}.mz-image{display:block;width:100%;height:auto}.mz-rounded{border-radius:var(--radius,16px)}.mz-site-header nav{flex-wrap:wrap;min-width:0}.mz-site-header nav a,.mz-site-footer a{min-height:44px;display:inline-flex;align-items:center}.mz-rounded img{border-radius:var(--radius,16px)}.mz-button{display:inline-block;padding:12px 24px;border-radius:var(--radius,8px);text-decoration:none;background:var(--primary,#651E2C);color:var(--primary-foreground,#FAF6F0)}.mz-button-secondary{background:var(--foreground,#262321);color:var(--background,#FAF6F0)}.mz-button-ghost{background:none;color:var(--primary,#651E2C);outline:1px solid currentColor}.mz-icon-list{padding-inline-start:24px;margin:24px 0}.mz-gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.mz-gallery img{width:100%}.mz-gallery[data-mode=slider]{display:flex;overflow:auto;scroll-snap-type:x mandatory}.mz-gallery[data-mode=slider] img{flex:0 0 85%;scroll-snap-align:start}.mz-embed iframe{width:100%;aspect-ratio:16/9;border:0}.mz-embed[data-aspect="4:3"] iframe{aspect-ratio:4/3}.mz-embed[data-aspect="1:1"] iframe{aspect-ratio:1}.mz-divider-dashed{border-style:dashed}.mz-divider-dotted{border-style:dotted}.mz-align-start{text-align:start}.mz-align-center{text-align:center}.mz-align-end{text-align:end}.mz-background-background{background:var(--background,#FAF6F0)}.mz-background-card{background:var(--card,#fff)}.mz-background-primary{background:var(--primary,#651E2C);color:var(--primary-foreground,#FAF6F0)}.mz-background-dark{background:var(--dark,#20303C);color:var(--dark-foreground,#F3EEE4)}.mz-max-width-narrow{max-width:720px;margin:auto}.mz-max-width-normal{max-width:1000px;margin:auto}.mz-max-width-wide{max-width:1400px;margin:auto}.mz-max-width-full{max-width:none}.mz-width-auto{width:auto}.mz-width-full{width:100%}.mz-width-half{width:50%}.mz-width-third{width:33.333%}.mz-width-two_thirds{width:66.666%}.mz-min-height-s{min-height:240px}.mz-min-height-m{min-height:480px}.mz-min-height-l{min-height:720px}.mz-canvas{position:relative;display:flex;flex-wrap:wrap;gap:16px}
.mz-art{min-height:320px;height:100%;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;background:radial-gradient(ellipse at 45% 25%,#f2f4e8,transparent 65%),#d9e3d5}.mz-art-orb{width:150px;height:195px;border-radius:48% 48% 38% 38%;background:linear-gradient(115deg,#c0caac,#718463 75%,#516a50);box-shadow:inset -18px -10px 30px #344a3229,20px 25px 30px #40543f30;position:relative;z-index:2;transform:rotate(-12deg) translateY(-20px)}.mz-art-orb:before{content:'';display:block;width:60px;height:14px;background:#536b49;border-radius:50%;margin:15px auto;box-shadow:inset 0 5px 8px #182d1b66}.mz-art-plinth{position:absolute;width:220px;height:120px;background:linear-gradient(90deg,#ececdb,#b9c4ae);bottom:35px;border-radius:50% 50% 8% 8%;box-shadow:0 20px 30px #6879602a}.mz-art-sculpture-alt{background:radial-gradient(ellipse at 45% 25%,#f2f4e8,transparent 65%),#d8d4c7}.mz-art-sculpture-alt .mz-art-orb{border-radius:50%;width:185px;height:185px;background:linear-gradient(115deg,#e5d1a8,#ad8f60);transform:rotate(15deg) translateY(-20px)}
.mz-text-eyebrow p{text-transform:uppercase;letter-spacing:.14em;font-size:13px;opacity:.75}.mz-text-check_list ul{list-style:none;padding-inline-start:0}.mz-text-check_list li{position:relative;padding-inline-start:30px;margin-bottom:10px}.mz-text-check_list li::before{content:"";position:absolute;inset-inline-start:2px;top:4px;width:17px;height:17px;background:var(--primary,#651E2C);-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M9.6 15.6 4.8 10.8l1.4-1.4 3.4 3.4 8.2-8.2 1.4 1.4z'/%3E%3C/svg%3E") center/contain no-repeat;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M9.6 15.6 4.8 10.8l1.4-1.4 3.4 3.4 8.2-8.2 1.4 1.4z'/%3E%3C/svg%3E") center/contain no-repeat}.mz-text-note p{text-transform:uppercase;letter-spacing:.1em;font-size:12px;opacity:.55}
.mz-site-header{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:16px 32px;border-bottom:1px solid color-mix(in srgb,currentColor 12%,transparent)}.mz-site-header nav{display:flex;gap:20px}.mz-site-header a{color:inherit;text-decoration:none}.mz-site-brand{font-weight:750;font-size:20px}.mz-site-header .mz-site-actions{display:flex;gap:16px;font-size:15px}
.mz-site-footer{padding:32px;border-top:1px solid color-mix(in srgb,currentColor 12%,transparent);display:flex;gap:24px;flex-wrap:wrap;justify-content:space-between;font-size:15px;opacity:.8}
@media (max-width:768px){.mz-site-header{flex-wrap:wrap;gap:12px;padding:12px 16px}.mz-site-header nav{order:3;width:100%;justify-content:space-between}}

@media(max-width:768px){.mz-site-header nav{gap:8px}.mz-site-header nav a{font-size:15px}}

.mz-background-primary .mz-button-primary{background:var(--primary-foreground,#fff);color:var(--primary,#007DA6)}
/* Responsive collapse: the visitor route renders the desktop settings once, so
   narrow-viewport stacking and gutter tightening live in real media queries
   instead of device-rendered classes. Mirrors the editor's own mobile intent
   (toPageTree sets stack on multi-column blocks for mobile). */
@media(max-width:1024px){.mz-columns-4,.mz-columns-5,.mz-columns-6{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:768px){.mz-columns-2,.mz-columns-3,.mz-columns-4,.mz-columns-5,.mz-columns-6{grid-template-columns:1fr}.mz-columns{gap:16px}.mz-section{padding:24px 16px}.mz-width-half,.mz-width-third,.mz-width-two_thirds{width:100%}}
"""
_BASE_CSS += """
.mz-node{--mz-duration:.6s;--mz-delay:0s}.mz-animation-fade{animation:mz-fade var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-rise{animation:mz-rise var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-slide{animation:mz-slide var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-zoom{animation:mz-zoom var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-speed-quick{--mz-duration:.3s}.mz-animation-speed-normal{--mz-duration:.6s}.mz-animation-speed-slow{--mz-duration:1s}.mz-animation-delay-none{--mz-delay:0s}.mz-animation-delay-short{--mz-delay:.15s}.mz-animation-delay-long{--mz-delay:.35s}@keyframes mz-fade{from{opacity:0}to{opacity:1}}@keyframes mz-rise{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}@keyframes mz-slide{from{opacity:0;transform:translateX(-24px)}to{opacity:1;transform:none}}@keyframes mz-zoom{from{opacity:0;transform:scale(.94)}to{opacity:1;transform:none}}@media(prefers-reduced-motion:reduce){.mz-animation-fade,.mz-animation-rise,.mz-animation-slide,.mz-animation-zoom{animation:none!important;opacity:1;transform:none}}
"""
_BASE_CSS += ".mz-header-centered{flex-direction:column;text-align:center}.mz-footer-stacked{flex-direction:column;align-items:center;text-align:center}"
for _token, _size in _SPACER_PX.items():
    _BASE_CSS += f".mz-padding-{_token}{{padding:{_size}px}}.mz-gap-{_token}{{gap:{_size}px}}.mz-height-{_token} .mz-spacer{{height:{_size}px}}"


def render_page(tree: dict, lang: str = "ar", device: str = "desktop", validate: bool = True,
                link_base: str | None = None) -> str:
    """The page body: every visible block of the published tree, in order."""
    if validate and page_problems(tree):
        raise ValueError("render_page() takes a tree that passed page_problems()")
    def unresolved(node):
        return isinstance(node, dict) and ("bindings" in node or "repeat" in node or "card" in node or any(unresolved(c) for c in node.get("children", []) or []))
    if unresolved(tree):
        raise ValueError("Dynamic content requires authorized provider resolution before rendering.")
    return _render_node(tree, lang, device, link_base)


def _site_link(href: str, link_base: str | None) -> str:
    """Root-relative theme links (\"/about\") only resolve when the page is served
    under a mounted site base (e.g. \"/site/studio\"). Anchors, protocol-relative
    and absolute URLs are returned unchanged."""
    if link_base and href.startswith("/") and not href.startswith("//"):
        return link_base.rstrip("/") + href
    return href


def _theme_links(entries, limit: int = 8, link_base: str | None = None) -> list:
    links = []
    for entry in (entries or [])[:limit]:
        if not isinstance(entry, dict):
            continue
        href = _safe_href(entry.get("href"))
        label = entry.get("label")
        if href is None or not isinstance(label, str) or not label.strip():
            continue
        links.append((_site_link(href, link_base), label.strip()[:40]))
    return links


def _theme_chrome(theme: dict | None, link_base: str | None = None) -> tuple[str, str]:
    """Constrained v0 site chrome: escaped brand, allow-listed links; no markup from the theme."""
    if not isinstance(theme, dict):
        return "", ""
    header = theme.get("header")
    head_html = ""
    if isinstance(header, dict):
        brand = header.get("brand")
        brand_html = f'<span class="mz-site-brand">{_esc(str(brand)[:80])}</span>' if brand else ""
        links = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(header.get("links"), link_base=link_base))
        actions = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(header.get("actions"), 4, link_base=link_base))
        nav = f"<nav>{links}</nav>" if links else ""
        act = f'<div class="mz-site-actions">{actions}</div>' if actions else ""
        if brand_html or nav or act:
            header_class = "mz-site-header mz-header-centered" if header.get("layout") == "centered" else "mz-site-header"
            head_html = f'<header class="{header_class}">{brand_html}{nav}{act}</header>'
    footer = theme.get("footer")
    foot_html = ""
    if isinstance(footer, dict):
        lines = [str(x)[:120] for x in (footer.get("lines") or [])[:4] if isinstance(x, str) and x.strip()]
        links = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(footer.get("links"), link_base=link_base))
        parts = "".join(f"<span>{_esc(x)}</span>" for x in lines) + links
        if parts:
            footer_class = "mz-site-footer mz-footer-stacked" if footer.get("layout") == "stacked" else "mz-site-footer"
            foot_html = f'<footer class="{footer_class}">{parts}</footer>'
    return head_html, foot_html


_FONT_STACKS = {
    "sans-serif": "system-ui,sans-serif",
    "serif": "Georgia,'Times New Roman',serif",
    "monospace": "ui-monospace,Menlo,monospace",
}


def _theme_style(theme: dict | None) -> str:
    """Constrained v0 theme: known palette tokens with hex colors only, an allow-listed
    typeface family, and an integer corner radius. No CSS expressions, ever."""
    import re

    if not isinstance(theme, dict):
        return ""
    rules = []
    variables = []
    colors = theme.get("colors")
    if isinstance(colors, dict) and isinstance(colors.get("light"), dict):
        allowed = {"background", "foreground", "card", "primary", "primary-foreground",
                   "dark", "dark-foreground"}
        variables += [f"--{token}:{value}" for token, value in colors["light"].items()
                      if token in allowed and isinstance(value, str)
                      and re.fullmatch(r"#[0-9a-fA-F]{6}", value)]
    shape = theme.get("shape")
    if isinstance(shape, dict):
        radius = shape.get("radius")
        if isinstance(radius, int) and not isinstance(radius, bool) and 0 <= radius <= 64:
            variables.append(f"--radius:{radius}px")
    if variables:
        rules.append(":root{" + ";".join(variables) + "}")
    typography = theme.get("typography")
    if isinstance(typography, dict):
        stack = _FONT_STACKS.get(typography.get("family"))
        if stack:
            rules.append(f"body{{font-family:{stack}}}")
    return "<style>" + "".join(rules) + "</style>" if rules else ""


_DOCUMENT = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined).from_string(
    '<!doctype html>\n<html lang="{{ language }}" dir="{{ direction }}">\n'
    '<head>{{ head | safe }}</head>\n<body>{{ body | safe }}</body>\n</html>\n')


def render_document(tree: dict, meta: dict, theme: dict | None = None, lang: str = "ar",
                    device: str = "desktop", link_base: str | None = None) -> str:
    """A full HTML document: SEO head (title and description per language, canonical, hreflang,
    Open Graph) plus the rendered page. `meta`: {"canonical": url, "titles": {lang: …},
    "descriptions": {lang: …}, "languages": [codes]}. `link_base`: when the page is served
    under a mounted site path (e.g. \"/site/studio\"), root-relative theme links are prefixed
    with it so site navigation resolves for visitors."""
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

    header_html, footer_html = _theme_chrome(theme, link_base=link_base)
    body = header_html + render_page(tree, lang=lang, device=device, link_base=link_base) + footer_html
    return _DOCUMENT.render(language=lang, direction=direction,
                            head="\n".join(head) + "<style>" + _BASE_CSS + "</style>" + _theme_style(theme), body=body)
