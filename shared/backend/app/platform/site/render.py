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


# Language-neutral references that may fall back across languages: an image's
# src and a button's href. Fallback applies only when the active language never
# set the key; an explicit empty value is respected, so a deliberately blank
# link or image stays blank. Text fields (label, alt, html, text) never fall
# back - mixing languages into copy silently would be worse than an honest gap.
def _content_ref(node: dict, lang: str, key: str):
    langs = node.get("content") or {}
    active = langs.get(lang) or {}
    if key in active:
        return active.get(key)
    for other in ("en", "ar"):
        if other == lang:
            continue
        other_content = langs.get(other) or {}
        if key in other_content:
            return other_content.get(key)
    return None


_SPACER_PX = {"none": 0, "xs": 8, "s": 16, "m": 32, "l": 64, "xl": 128}

# Bounded inline icon set for icon_list blocks: no icon font, no network fetch.
# Mirrored in system/frontend/src/features/studio/nativeIcons.tsx (ICON_MARKUP); keep entries identical.
_ICON_MARKUP = {
    "Wrench": '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.8 2.8-2-2 2.8-2.8z"/>',
    "Laptop": '<rect x="4" y="5" width="16" height="10" rx="1.5"/><path d="M2 19h20"/>',
    "Smartphone": '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18.5h2"/>',
    "ShieldCheck": '<path d="M12 3l7 3v5c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6l7-3z"/><path d="M9 12l2 2 4-4"/>',
    "Truck": '<path d="M1.5 7H14v9H1.5z"/><path d="M14 10h4l3 3v3h-7"/><circle cx="6" cy="18" r="1.6"/><circle cx="17.5" cy="18" r="1.6"/>',
    "Check": '<path d="M4 12.5l5 5L20 6.5"/>',
    "Star": '<path d="M12 3l2.7 5.6 6.1.8-4.5 4.2 1.1 6-5.4-2.9L6.6 19.6l1.1-6L3.2 9.4l6.1-.8z"/>',
    "Headphones": '<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><path d="M4 14h3v6H6a2 2 0 0 1-2-2v-4z"/><path d="M20 14h-3v6h1a2 2 0 0 0 2-2v-4z"/>',
    "Cpu": '<rect x="7" y="7" width="10" height="10" rx="1.5"/><rect x="10.5" y="10.5" width="3" height="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    "BatteryCharging": '<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/><path d="M11 9l-2.5 3.5H11l-1 3 4-4.5h-2.5L13 9z"/>',
    "Camera": '<path d="M4 7h3l2-2h6l2 2h3v12H4z"/><circle cx="12" cy="13" r="3.2"/>',
    "Home": '<path d="M3 11l9-8 9 8"/><path d="M5 9.5V20h14V9.5"/>',
    "Mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3.5 7l8.5 6 8.5-6"/>',
    "MapPin": '<path d="M12 21s-6-5.2-6-10a6 6 0 0 1 12 0c0 4.8-6 10-6 10z"/><circle cx="12" cy="11" r="2.2"/>',
    "ArrowRight": '<path d="M4 12h16"/><path d="M13 5l7 7-7 7"/>',
    "Sparkles": '<path d="M12 4l1.7 4.3L18 10l-4.3 1.7L12 16l-1.7-4.3L6 10l4.3-1.7z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
    "Clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "CreditCard": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    "Package": '<path d="M12 3l8 4v10l-8 4-8-4V7z"/><path d="M4 7l8 4 8-4"/><path d="M12 11v10"/>',
    "Heart": '<path d="M12 20s-7-4.4-9-9a5 5 0 0 1 9-3 5 5 0 0 1 9 3c-2 4.6-9 9-9 9z"/>',
    "ShoppingBag": '<path d="M16 10a4 4 0 0 1-8 0M3.103 6.034h17.794M3.4 5.467a2 2 0 0 0-.4 1.2V20a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6.667a2 2 0 0 0-.4-1.2l-2-2.667A2 2 0 0 0 17 2H7a2 2 0 0 0-1.6.8z"/>',
    "BookOpen": '<path d="M12 5v16M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z"/>',
    "Stethoscope": '<path d="M11 2v2M5 2v2M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1M8 15a6 6 0 0 0 12 0v-3"/><circle cx="20" cy="10" r="2"/>',
    "HardDriveDownload": '<path d="M12 2v8M16 6l-4 4-4-4"/><rect width="20" height="8" x="2" y="14" rx="2"/><path d="M6 18h.01M10 18h.01"/>',
    "MemoryStick": '<path d="M12 12v-2M12 18v-2M16 12v-2M16 18v-2M2 11h1.5M20 18v-2M20.5 11H22M4 18v-2M8 12v-2M8 18v-2"/><rect x="2" y="6" width="20" height="10" rx="2"/>',
    "MonitorCog": '<path d="M12 17v4M14.305 7.53l.923-.382M15.228 4.852l-.923-.383M16.852 3.228l-.383-.924M16.852 8.772l-.383.923M19.148 3.228l.383-.924M19.53 9.696l-.382-.924M20.772 4.852l.924-.383M20.772 7.148l.924.383M22 13v2a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7M8 21h8"/><circle cx="18" cy="6" r="3"/>',
    "Network": '<rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3M12 12V8"/>',
    "Globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20M2 12h20"/>',
    "Building2": '<path d="M10 12h4M10 8h4M14 21v-3a2 2 0 0 0-4 0v3M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/>',
    "MessageCircle": '<path d="M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 1 0-4.777-4.719"/>',
    "Banknote": '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
}
_ICON_FALLBACK = '<circle cx="12" cy="12" r="5"/>'


def _icon_svg(name: str) -> str:
    # Unknown stored names render as a dot; markup values are a fixed allowlist, never user input.
    inner = _ICON_MARKUP.get(name, _ICON_FALLBACK)
    return ('<svg class="mz-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f"{inner}</svg>")


def _render_node_inner(node: dict, lang: str, device: str, link_base: str | None = None) -> str:
    ntype = node.get("type")
    if ntype not in PAGE_BLOCKS:
        return ""
    # Visibility is decided by the _render_node wrapper (per-device overrides
    # become CSS classes on the single-render visitor route); inner renders content.
    s = _settings(node, device)
    c = _content(node, lang)
    kids = "".join(_render_node(k, lang, device, link_base) for k in node.get("children") or [] if isinstance(k, dict))

    if ntype == "section":
        # The wrapper div also carries the padding class, but the inner section's
        # own default padding would still apply inside it, so the token is echoed
        # here where the generated .mz-padding-* rules override the default.
        pad = s.get("padding")
        pad_cls = f" mz-padding-{pad}" if isinstance(pad, str) and pad in _SPACER_PX else ""
        return f'<section class="mz-section{pad_cls}">{kids}</section>'
    if ntype == "columns":
        declared = s.get("columns")
        count = declared if isinstance(declared, int) and not isinstance(declared, bool) else 0
        count = count or len(node.get("children") or []) or 1
        stack = " mz-stack" if s.get("stack") else ""
        # Free divider-drag ratio: numeric fr weights only, never arbitrary CSS. Mobile
        # still collapses to a single column via the .mz-cols-custom media rule.
        tracks = s.get("tracks")
        ncols = len(node.get("children") or [])
        track_cls = ""
        track_style = ""
        if (isinstance(tracks, list) and ncols >= 2 and len(tracks) == ncols
                and all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0.2 <= v <= 8 for v in tracks)):
            weights = " ".join(f"{v:g}fr" for v in tracks)
            track_cls = " mz-cols-custom"
            track_style = f' style="--mz-tracks:{weights}"'
        # A mobile-segment ratio travels as its own var; the narrow-viewport rule
        # uses it instead of collapsing (see the .mz-cols-custom media rule).
        m_tracks = ((node.get("settings") or {}).get("mobile") or {}).get("tracks")
        if (track_cls and isinstance(m_tracks, list) and len(m_tracks) == ncols
                and all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0.2 <= v <= 8 for v in m_tracks)):
            m_weights = " ".join(f"{v:g}fr" for v in m_tracks)
            track_style = f' style="--mz-tracks:{weights};--mz-tracks-m:{m_weights}"'
        elif (not track_cls and isinstance(m_tracks, list) and len(m_tracks) == ncols
                and all(isinstance(v, (int, float)) and not isinstance(v, bool) and 0.2 <= v <= 8 for v in m_tracks)):
            m_weights = " ".join(f"{v:g}fr" for v in m_tracks)
            track_cls = " mz-cols-custom-m"
            track_style = f' style="--mz-tracks-m:{m_weights}"'
        if s.get("reverse") is True:
            kids = "".join(_render_node(k, lang, device, link_base) for k in reversed(node.get("children") or []) if isinstance(k, dict))
        return f'<div class="mz-columns mz-columns-{int(count)}{stack}{track_cls}"{track_style}>{kids}</div>'
    if ntype == "column":
        return f'<div class="mz-column">{kids}</div>'
    if ntype == "canvas":
        return f'<div class="mz-canvas">{kids}</div>'
    if ntype == "heading":
        level = s.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 6:
            level = 2
        icon = s.get("icon")
        prefix = ""
        if isinstance(icon, str) and icon in _ICON_MARKUP:
            prefix = f'<span class="mz-heading-icon" aria-hidden="true">{_icon_svg(icon)}</span>'
        return f'<h{level} class="mz-heading">{prefix}{_accented(c.get("text", ""))}</h{level}>'
    if ntype == "text":
        variant = s.get("variant") if s.get("variant") in ("eyebrow", "note", "check_list") else ""
        cls = f"mz-text mz-text-{variant}" if variant else "mz-text"
        return f'<div class="{cls}">{sanitize_html(c.get("html", ""))}</div>'
    if ntype == "image":
        src = _safe_src(_content_ref(node, lang, "src"))
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
        if not c.get("label"):
            # A link with no visible label in the active language is unusable;
            # labels never fall back, so an untranslated button stays hidden.
            return ""
        href = _safe_href(_content_ref(node, lang, "href"))
        if href is None:
            return ""
        href = _site_link(href, link_base)
        style = s.get("style") if s.get("style") in ("primary", "secondary", "ghost", "soft") else "primary"
        return f'<a class="mz-button mz-button-{style}" href="{_esc(href)}">{_esc(c.get("label", ""))}</a>'
    if ntype == "icon_list":
        items = []
        for entry in c.get("items") or []:
            if isinstance(entry, dict) and isinstance(entry.get("icon"), str):
                items.append(f'<li>{_icon_svg(entry["icon"])}<span>{_esc(entry.get("text", ""))}</span></li>')
        return f'<ul class="mz-icon-list">{"".join(items)}</ul>'
    if ntype == "icon":
        name = s.get("icon")
        if not isinstance(name, str) or name not in _ICON_MARKUP:
            return ""
        return f'<span class="mz-icon-badge" aria-hidden="true">{_icon_svg(name)}</span>'
    if ntype == "spacer":
        return '<div class="mz-spacer" aria-hidden="true"></div>'
    if ntype == "divider":
        style = s.get("style") if s.get("style") in ("solid", "dashed", "dotted") else "solid"
        return f'<hr class="mz-divider mz-divider-{style}">'
    if ntype == "html":
        return f'<div class="mz-html">{sanitize_html(c.get("html", ""), EXTRA_TAGS)}</div>'
    return ""


def _render_node(node: dict, lang: str, device: str, link_base: str | None = None) -> str:
    # Per-device visibility on the single-render visitor route: the page is
    # rendered once (desktop settings) and narrow viewports adapt through media
    # queries, so a mobile `visible` override becomes a CSS class instead of a
    # second render pass. A node hidden everywhere is still skipped entirely.
    device_visibility_class = ""
    if _settings(node, device).get("visible") is False:
        if device == "desktop" and ((node.get("settings") or {}).get("mobile") or {}).get("visible") is True:
            device_visibility_class = "mz-show-mobile"
        else:
            return ""
    elif device == "desktop" and ((node.get("settings") or {}).get("mobile") or {}).get("visible") is False:
        device_visibility_class = "mz-hide-mobile"
    rendered = _render_node_inner(node, lang, device, link_base)
    if not rendered:
        return ""
    if device_visibility_class:
        classes = [device_visibility_class]
    else:
        classes = []
    # Only registry enum tokens become classes, never arbitrary CSS from the tree.
    settings = _settings(node, device)
    schema = PAGE_BLOCKS[node["type"]]["settings"]
    for key, value in settings.items():
        spec = schema.get(key)
        if isinstance(spec, tuple) and spec[0] == "choice" and value in spec[1]:
            classes.append("mz-" + key.replace("_", "-") + "-" + value)
    if settings.get("rounded") is True:
        classes.append("mz-rounded")
    if settings.get("bleed") is True and node["type"] == "columns":
        classes.append("mz-bleed")
    if settings.get("background_fit") == "end_band" and settings.get("background_image"):
        classes.append("mz-bg-band")
    mobile_seg = (node.get("settings") or {}).get("mobile") or {}
    width_pct = settings.get("width_pct")
    width_ok = isinstance(width_pct, int) and not isinstance(width_pct, bool) and 10 <= width_pct <= 100
    width_m = mobile_seg.get("width_pct")
    width_m_ok = isinstance(width_m, int) and not isinstance(width_m, bool) and 10 <= width_m <= 100
    if width_ok or width_m_ok:
        classes.append("mz-width-custom")
    min_h = settings.get("min_height_px")
    min_h_ok = isinstance(min_h, int) and not isinstance(min_h, bool) and 40 <= min_h <= 1200
    min_h_m = mobile_seg.get("min_height_px")
    min_h_m_ok = isinstance(min_h_m, int) and not isinstance(min_h_m, bool) and 40 <= min_h_m <= 1200
    if min_h_ok or min_h_m_ok:
        classes.append("mz-minh-custom")
    bg_style = _background_image_style(node["type"], settings, lang)
    if bg_style:
        classes.append("mz-bg-image")
    # Numeric px only (validated above); the class applies it to the element inside.
    style = bg_style or ""
    if min_h_ok:
        style = (style + ";" if style else "") + f"--mz-minh:{min_h}px"
    if width_ok:
        style = (style + ";" if style else "") + f"--mz-width:{width_pct}%"
    if min_h_m_ok:
        style = (style + ";" if style else "") + f"--mz-minh-m:{min_h_m}px"
    if width_m_ok:
        style = (style + ";" if style else "") + f"--mz-width-m:{width_m}%"
    class_value = _esc(" ".join(classes))
    style_attr = f' style="{style}"' if style else ""
    return f'<div id="{_esc(node["id"])}" class="mz-node {class_value}"{style_attr}>{rendered}</div>'


def _background_image_style(node_type: str, settings: dict, lang: str = "ar") -> str:
    """Validated background-image layer for section/column bands. The URL is a registry
    "url" setting (page_url rules, no CSS-significant characters), dim is a fixed choice
    layering a theme-dark scrim; the value never carries arbitrary CSS.
    background_fit "end_band" pins the image to the inline-end edge at 40% width,
    full height, no repeat - the source-composition card pattern of a content card
    with a photo occupying its end side; the edge follows the page direction."""
    if node_type not in ("section", "column"):
        return ""
    url = settings.get("background_image")
    if not isinstance(url, str) or not url:
        return ""
    if not page_url(url, "url") or any(ch in url for ch in "();"):
        return ""
    layers = []
    dim = settings.get("background_dim")
    if dim in ("soft", "strong"):
        pct = "45%" if dim == "soft" else "72%"
        scrim = f"color-mix(in srgb, var(--dark, #20303C) {pct}, transparent)"
        layers.append(f"linear-gradient({scrim}, {scrim})")
    layers.append(f'url(&quot;{_esc(url)}&quot;)')
    style = "background-image:" + ", ".join(layers)
    if settings.get("background_fit") == "end_band":
        # The band renders as a ::before side panel (see _BASE_CSS .mz-bg-band),
        # not as the element's own background: exact 40% width, cover-cropped
        # (never distorted), direction-aware edge, hidden on small viewports.
        return f'--mz-bg:url(&quot;{_esc(url)}&quot;)'
    return style


_BASE_CSS = """
*{box-sizing:border-box}body{margin:0;background:var(--background,#FAF6F0);color:var(--foreground,#262321);font:18px/1.6 system-ui,sans-serif}
.mz-section{padding:32px;max-width:1200px;margin:auto}.mz-columns{display:grid;gap:24px}.mz-columns-1{grid-template-columns:1fr}.mz-columns-2{grid-template-columns:repeat(2,minmax(0,1fr))}.mz-columns-3{grid-template-columns:repeat(3,minmax(0,1fr))}.mz-columns-4{grid-template-columns:repeat(4,minmax(0,1fr))}.mz-columns-5{grid-template-columns:repeat(5,minmax(0,1fr))}.mz-columns-6{grid-template-columns:repeat(6,minmax(0,1fr))}.mz-stack{grid-template-columns:1fr}
.mz-heading{line-height:1.15;margin:0 0 24px;font-weight:750}.mz-heading mark{background:none;color:var(--primary,#651E2C)}h1{font-size:clamp(32px,4.8vw,64px)}h2.mz-heading{font-size:clamp(26px,3vw,38px)}h3.mz-heading{font-size:clamp(21px,2.2vw,27px)}.mz-text p{margin:0 0 24px}.mz-image{display:block;width:100%;height:auto}.mz-rounded{border-radius:var(--radius,16px)}.mz-site-header nav{flex-wrap:wrap;min-width:0}.mz-site-header nav a,.mz-site-footer a{min-height:44px;display:inline-flex;align-items:center}.mz-rounded img{border-radius:var(--radius,16px)}.mz-node:has(>.mz-button){display:inline-block;vertical-align:top}.mz-node:has(>.mz-image):where(.mz-width-half,.mz-width-third,.mz-width-two_thirds){display:inline-block;vertical-align:top}.mz-button{display:inline-block;margin:0 0 24px;margin-inline-end:12px;padding:12px 24px;border-radius:var(--radius,8px);text-decoration:none;background:var(--primary,#651E2C);color:var(--primary-foreground,#FAF6F0)}.mz-button-secondary{background:var(--foreground,#262321);color:var(--background,#FAF6F0)}.mz-button-ghost{background:none;color:var(--primary,#651E2C);outline:1px solid currentColor}.mz-icon-list{list-style:none;padding-inline-start:0;margin:24px 0;display:grid;gap:12px}.mz-icon-list li{display:flex;align-items:center;gap:10px}.mz-icon-list .mz-icon{width:1.25em;height:1.25em;flex:none;color:var(--primary,#651E2C)}.mz-gallery{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.mz-gallery img{width:100%}.mz-gallery[data-mode=slider]{display:flex;overflow:auto;scroll-snap-type:x mandatory}.mz-gallery[data-mode=slider] img{flex:0 0 85%;scroll-snap-align:start}.mz-embed iframe{width:100%;aspect-ratio:16/9;border:0}.mz-embed[data-aspect="4:3"] iframe{aspect-ratio:4/3}.mz-embed[data-aspect="1:1"] iframe{aspect-ratio:1}.mz-divider-dashed{border-style:dashed}.mz-divider-dotted{border-style:dotted}.mz-align-start{text-align:start}.mz-align-center{text-align:center}.mz-align-end{text-align:end}.mz-background-background{background:var(--background,#FAF6F0);color:var(--foreground,#262321)}.mz-background-card{background:var(--card,#fff);color:var(--foreground,#262321)}.mz-background-primary{background:var(--primary,#651E2C);color:var(--primary-foreground,#FAF6F0)}.mz-background-dark{background:var(--dark,#20303C);color:var(--dark-foreground,#F3EEE4)}.mz-background-dark-raised,.mz-background-dark_raised{background:var(--dark-raised,color-mix(in srgb,var(--dark,#20303C) 88%,#fff));color:var(--dark-foreground,#F3EEE4)}.mz-background-dark .mz-button-ghost,.mz-background-dark-raised .mz-button-ghost,.mz-background-dark_raised .mz-button-ghost{color:var(--dark-foreground,#F3EEE4)}.mz-button-soft{background:var(--background,#FAF6F0);color:var(--foreground,#262321);outline:1px solid color-mix(in srgb,var(--foreground,#262321) 22%,transparent)}.mz-icon-badge{display:inline-flex;align-items:center;justify-content:center;width:44px;height:44px;border-radius:var(--radius,8px);color:var(--primary,#651E2C);margin:0 0 16px}.mz-icon-badge .mz-icon{width:55%;height:55%}.mz-size-s .mz-icon-badge{width:32px;height:32px}.mz-size-l .mz-icon-badge{width:56px;height:56px}.mz-tone-primary .mz-icon-badge{background:var(--primary,#651E2C);color:var(--primary-foreground,#FAF6F0)}.mz-tone-dark .mz-icon-badge{background:var(--dark,#20303C);color:var(--primary,#651E2C)}.mz-tone-card .mz-icon-badge{background:var(--card,#fff);color:var(--primary,#651E2C);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--foreground,#262321) 14%,transparent)}.mz-size-s .mz-heading{font-size:clamp(19px,2vw,24px)}.mz-size-m .mz-heading{font-size:clamp(26px,3.2vw,40px)}.mz-size-l .mz-heading{font-size:clamp(30px,4vw,52px)}.mz-wrap-balance .mz-heading{text-wrap:balance}.mz-heading-icon{display:inline-flex;align-items:center;justify-content:center;width:1.6em;height:1.6em;margin-inline-end:.4em;vertical-align:-.35em;color:var(--primary,#651E2C);background:color-mix(in srgb,var(--dark,#20303C) 92%,#000);border-radius:calc(var(--radius,8px)*.6)}.mz-heading-icon .mz-icon{width:62%;height:62%}.mz-max-width-narrow{max-width:720px;margin:auto}.mz-max-width-normal{max-width:1000px;margin:auto}.mz-max-width-wide{max-width:1400px;margin:auto}.mz-max-width-full{max-width:none}.mz-width-auto{width:auto}.mz-width-full{width:100%}.mz-width-half{width:50%}.mz-width-third{width:33.333%}.mz-width-two_thirds{width:66.666%}.mz-width-three_fifths{width:60%}.mz-min-height-s{min-height:240px}.mz-min-height-m{min-height:480px}.mz-min-height-l{min-height:720px}.mz-cols-custom{grid-template-columns:var(--mz-tracks)}.mz-node.mz-minh-custom>:first-child{min-height:var(--mz-minh,0)}.mz-node.mz-width-custom{width:var(--mz-width,100%);display:inline-block;vertical-align:top}.mz-node.mz-width-fit{width:fit-content;display:inline-block;vertical-align:top}
/* Visual effects: bounded theme-token treatments on the block surface (the wrapper's
   first child), registry tokens only, never arbitrary CSS from the tree. */
.mz-node.mz-shadow-s>:first-child{box-shadow:0 1px 3px rgb(0 0 0/.12),0 1px 2px rgb(0 0 0/.08)}
.mz-node.mz-shadow-m>:first-child{box-shadow:0 6px 16px rgb(0 0 0/.12),0 2px 6px rgb(0 0 0/.08)}
.mz-node.mz-shadow-l>:first-child{box-shadow:0 18px 44px rgb(0 0 0/.18),0 6px 14px rgb(0 0 0/.10)}
.mz-node.mz-gradient-soft>:first-child{background-image:linear-gradient(160deg,color-mix(in srgb,var(--card,#fff) 82%,transparent),color-mix(in srgb,var(--background,#FAF6F0) 55%,var(--card,#fff)))}
.mz-node.mz-gradient-brand>:first-child{background-image:linear-gradient(140deg,color-mix(in srgb,var(--primary,#007DA6) 16%,transparent),color-mix(in srgb,var(--primary,#007DA6) 42%,transparent))}
.mz-node.mz-gradient-dark>:first-child{background-image:linear-gradient(160deg,color-mix(in srgb,var(--dark-raised,#003459) 88%,transparent),var(--dark,#20303C))}
.mz-node.mz-hover-lift>:first-child{transition:transform .18s ease,box-shadow .18s ease}
.mz-node.mz-hover-lift:hover>:first-child{transform:translateY(-3px);box-shadow:0 10px 24px rgb(0 0 0/.14)}
.mz-node.mz-hover-glow>:first-child{transition:box-shadow .18s ease}
.mz-node.mz-hover-glow:hover>:first-child{box-shadow:0 0 0 2px color-mix(in srgb,var(--primary,#007DA6) 55%,transparent),0 8px 28px color-mix(in srgb,var(--primary,#007DA6) 35%,transparent)}
@media(prefers-reduced-motion:reduce){.mz-node.mz-hover-lift:hover>:first-child{transform:none}}.mz-canvas{position:relative;display:flex;flex-wrap:wrap;gap:16px}.mz-bg-image{background-size:cover;background-position:center}.mz-bg-band{position:relative}.mz-bg-band::before{content:"";position:absolute;inset-block:0;inset-inline-end:0;width:40%;background-image:var(--mz-bg);background-size:cover;background-position:center;border-start-end-radius:inherit;border-end-end-radius:inherit}.mz-bg-band>*{position:relative}@media(max-width:768px){.mz-bg-band::before{display:none}}.mz-content-width-three_fifths>.mz-column{width:60%}@media(max-width:768px){.mz-content-width-three_fifths>.mz-column{width:100%}}html{overflow-x:clip}.mz-site{overflow-x:clip}.mz-node.mz-bleed{margin-inline:calc(50% - 50vw);padding-inline:max(calc(50vw - 50%),16px)}.mz-show-mobile{display:none}@media(max-width:768px){.mz-show-mobile{display:block}.mz-hide-mobile{display:none}}.mz-site-header-dark{background:var(--dark,#20303C);color:var(--dark-foreground,#F3EEE4);border-bottom-color:color-mix(in srgb,var(--dark-foreground,#F3EEE4) 14%,transparent)}
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
@media(max-width:768px){.mz-columns-2,.mz-columns-3,.mz-columns-4,.mz-columns-5,.mz-columns-6{grid-template-columns:1fr}.mz-columns.mz-cols-custom{grid-template-columns:var(--mz-tracks-m,1fr)}.mz-columns.mz-cols-custom-m{grid-template-columns:var(--mz-tracks-m)}.mz-node.mz-minh-custom>:first-child{min-height:var(--mz-minh-m,var(--mz-minh))}.mz-columns{gap:16px}.mz-section{padding:24px 16px}.mz-width-half,.mz-width-third,.mz-width-two_thirds,.mz-width-three_fifths{width:100%}.mz-node.mz-width-custom{width:var(--mz-width-m,100%)}}
"""
_BASE_CSS += """
.mz-node{--mz-duration:.6s;--mz-delay:0s}.mz-animation-fade{animation:mz-fade var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-rise{animation:mz-rise var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-slide{animation:mz-slide var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-zoom{animation:mz-zoom var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-speed-quick{--mz-duration:.3s}.mz-animation-speed-normal{--mz-duration:.6s}.mz-animation-speed-slow{--mz-duration:1s}.mz-animation-delay-none{--mz-delay:0s}.mz-animation-delay-short{--mz-delay:.15s}.mz-animation-delay-long{--mz-delay:.35s}@keyframes mz-fade{from{opacity:0}to{opacity:1}}@keyframes mz-rise{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}@keyframes mz-slide{from{opacity:0;transform:translateX(-24px)}to{opacity:1;transform:none}}@keyframes mz-zoom{from{opacity:0;transform:scale(.94)}to{opacity:1;transform:none}}@media(prefers-reduced-motion:reduce){.mz-animation-fade,.mz-animation-rise,.mz-animation-slide,.mz-animation-zoom{animation:none!important;opacity:1;transform:none}}
"""
_BASE_CSS += ".mz-header-centered{flex-direction:column;text-align:center}.mz-footer-stacked{flex-direction:column;align-items:center;text-align:center}"
_BASE_CSS += ".mz-site-logo{height:32px;width:auto}.mz-site-footer a{color:inherit;text-decoration:none}.mz-footer-groups{display:flex;gap:32px;flex-wrap:wrap}.mz-footer-group{display:flex;flex-direction:column;gap:10px}.mz-footer-group-title{font-weight:650}"
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
        logo = _safe_src(header.get("logo"))
        logo_html = f'<img class="mz-site-logo" src="{_esc(logo)}" alt="">' if logo else ""
        links = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(header.get("links"), link_base=link_base))
        actions = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(header.get("actions"), 4, link_base=link_base))
        nav = f"<nav>{links}</nav>" if links else ""
        act = f'<div class="mz-site-actions">{actions}</div>' if actions else ""
        if logo_html or brand_html or nav or act:
            header_class = "mz-site-header mz-header-centered" if header.get("layout") == "centered" else "mz-site-header"
            if header.get("surface") == "dark":
                header_class += " mz-site-header-dark"
            head_html = f'<header class="{header_class}">{logo_html}{brand_html}{nav}{act}</header>'
    footer = theme.get("footer")
    foot_html = ""
    if isinstance(footer, dict):
        lines = [str(x)[:120] for x in (footer.get("lines") or [])[:4] if isinstance(x, str) and x.strip()]
        links = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(footer.get("links"), link_base=link_base))
        groups_html = ""
        groups = footer.get("groups")
        if isinstance(groups, list):
            for group in groups[:4]:
                if not isinstance(group, dict):
                    continue
                title = group.get("title")
                glinks = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(group.get("links"), 6, link_base=link_base))
                if isinstance(title, str) and title.strip() and glinks:
                    groups_html += (f'<div class="mz-footer-group"><span class="mz-footer-group-title">'
                                    f'{_esc(title.strip()[:40])}</span>{glinks}</div>')
        if groups_html:
            groups_html = f'<div class="mz-footer-groups">{groups_html}</div>'
        parts = "".join(f"<span>{_esc(x)}</span>" for x in lines) + links + groups_html
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
                   "dark", "dark-foreground", "dark-raised"}
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
