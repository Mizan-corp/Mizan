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

from app.framework.manifest import PAGE_BLOCKS, PAGE_LANGUAGE, PAGE_NODE_ID, page_url, page_problems

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
# Mirrored in system/erp/frontend/src/features/studio/nativeIcons.tsx (ICON_MARKUP); keep entries identical.
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


def _render_node_inner(node: dict, lang: str, device: str, link_base: str | None = None,
                       form_action_base: str | None = None, form_sent: str | None = None) -> str:
    ntype = node.get("type")
    if ntype not in PAGE_BLOCKS:
        return ""
    # Visibility is decided by the _render_node wrapper (per-device overrides
    # become CSS classes on the single-render visitor route); inner renders content.
    s = _settings(node, device)
    c = _content(node, lang)
    kids = "".join(_render_node(k, lang, device, link_base, form_action_base, form_sent)
                   for k in node.get("children") or [] if isinstance(k, dict))

    if ntype == "section":
        # The wrapper div also carries the padding class, but the inner section's
        # own default padding would still apply inside it, so the token is echoed
        # here where the generated .mz-padding-* rules override the default.
        pad = s.get("padding")
        pad_cls = f" mz-padding-{pad}" if isinstance(pad, str) and pad in _SPACER_PX else ""
        # Same echo for the section gap token: the wrapper's class would apply
        # `gap` to the block wrapper itself (a no-op), while the author means
        # the spacing BETWEEN the section's rows.
        gap = s.get("gap")
        gap_cls = f" mz-gap-{gap}" if isinstance(gap, str) and gap in _SPACER_PX else ""
        return f'<section class="mz-section{pad_cls}{gap_cls}">{kids}</section>'
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
            kids = "".join(_render_node(k, lang, device, link_base, form_action_base, form_sent)
                           for k in reversed(node.get("children") or []) if isinstance(k, dict))
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
    if ntype == "form":
        # A native POST form, wired only when a hosting runtime passes the action
        # base for this page (the public visitor route). In previews and exports
        # the block renders its fields inert so it can never post anywhere.
        align_cls = " mz-form-center" if s.get("align") == "center" else ""
        # layout "inline": one row (message input + submit), like a request band. The message
        # field becomes a single-line input; email stays unless field_email is explicitly false.
        inline = s.get("layout") == "inline"
        if inline:
            align_cls += " mz-form-inline"
        node_id = node.get("id") if isinstance(node.get("id"), str) else ""
        parts = []
        if c.get("title"):
            parts.append(f'<p class="mz-form-title">{_esc(c.get("title", ""))}</p>')
        if form_sent and form_sent == node_id:
            parts.append(f'<p class="mz-form-success" role="status">{_esc(c.get("success_message") or "Thank you.")}</p>')
        controls = []
        if s.get("field_name"):
            controls.append(("name", c.get("name_label") or "Name", "text", 120, False))
        if s.get("field_email") is not False:
            controls.append(("email", c.get("email_label") or "Email", "email", 254, True))
        if s.get("field_phone"):
            controls.append(("phone", c.get("phone_label") or "Phone", "text", 40, False))
        controls.append(("message", c.get("message_label") or "Message", "text" if inline else "textarea", 2000, True))
        for fname, flabel, fkind, fmax, frequired in controls:
            field_id = f"mz-f-{node_id}-{fname}"
            label_html = f'<label class="mz-form-label" for="{_esc(field_id)}">{_esc(flabel)}</label>'
            if fkind == "textarea":
                control = (f'<textarea class="mz-form-input" id="{_esc(field_id)}" name="{fname}" '
                           f'maxlength="{fmax}" rows="4" required></textarea>')
            else:
                req = " required" if frequired else ""
                control = (f'<input class="mz-form-input" id="{_esc(field_id)}" name="{fname}" '
                           f'type="{fkind}" maxlength="{fmax}"{req}>')
            parts.append(f'<div class="mz-form-field">{label_html}{control}</div>')
        submit = _esc(c.get("submit_label") or "Send")
        if form_action_base and PAGE_NODE_ID.fullmatch(node_id):
            # lang rides the action URL so the post-submit redirect can return
            # the visitor to the same language.
            action = f"{form_action_base.rstrip('/')}/{node_id}?lang={lang}"
            honeypot = ('<div class="mz-form-hp" aria-hidden="true"><label>Website'
                        '<input type="text" name="website" tabindex="-1" autocomplete="off"></label></div>')
            return (f'<form class="mz-form{align_cls}" method="post" action="{_esc(action)}">'
                    + "".join(parts) + honeypot
                    + f'<button class="mz-button mz-button-primary mz-form-submit" type="submit">{submit}</button></form>')
        return (f'<div class="mz-form mz-form-inert{align_cls}">'
                + "".join(parts)
                + f'<button class="mz-button mz-button-primary mz-form-submit" type="button" disabled>{submit}</button></div>')
    if ntype == "spacer":
        return '<div class="mz-spacer" aria-hidden="true"></div>'
    if ntype == "divider":
        style = s.get("style") if s.get("style") in ("solid", "dashed", "dotted") else "solid"
        return f'<hr class="mz-divider mz-divider-{style}">'
    if ntype == "html":
        return f'<div class="mz-html">{sanitize_html(c.get("html", ""), EXTRA_TAGS)}</div>'
    return ""


def _render_node(node: dict, lang: str, device: str, link_base: str | None = None,
                 form_action_base: str | None = None, form_sent: str | None = None) -> str:
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
    rendered = _render_node_inner(node, lang, device, link_base, form_action_base, form_sent)
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

"""
_BASE_CSS += """
.mz-node{--mz-duration:.6s;--mz-delay:0s}.mz-animation-fade{animation:mz-fade var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-rise{animation:mz-rise var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-slide{animation:mz-slide var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-zoom{animation:mz-zoom var(--mz-duration,.6s) ease-out var(--mz-delay,0s) both}.mz-animation-speed-quick{--mz-duration:.3s}.mz-animation-speed-normal{--mz-duration:.6s}.mz-animation-speed-slow{--mz-duration:1s}.mz-animation-delay-none{--mz-delay:0s}.mz-animation-delay-short{--mz-delay:.15s}.mz-animation-delay-long{--mz-delay:.35s}@keyframes mz-fade{from{opacity:0}to{opacity:1}}@keyframes mz-rise{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}@keyframes mz-slide{from{opacity:0;transform:translateX(-24px)}to{opacity:1;transform:none}}@keyframes mz-zoom{from{opacity:0;transform:scale(.94)}to{opacity:1;transform:none}}@media(prefers-reduced-motion:reduce){.mz-animation-fade,.mz-animation-rise,.mz-animation-slide,.mz-animation-zoom{animation:none!important;opacity:1;transform:none}}
"""
_BASE_CSS += ".mz-header-centered{flex-direction:column;text-align:center}.mz-footer-stacked{flex-direction:column;align-items:center;text-align:center}"
_BASE_CSS += ".mz-header-rich{display:block;padding:0;position:relative}.mz-header-rich .mz-header-main{display:flex;align-items:center;gap:14px;padding:10px 32px;flex-wrap:wrap}.mz-header-search{flex:1;min-width:200px;max-width:640px;margin-inline:auto;display:flex;align-items:center;gap:8px;padding:4px;padding-inline-start:16px;border-radius:999px;background:#fff;color:#00171f}.mz-header-search input{flex:1;min-width:0;border:0;background:none;font:inherit;font-size:15px;color:#00171f;outline:none}.mz-header-search input::placeholder{color:#475a64}.mz-header-search button{flex:none;width:36px;height:36px;border:0;border-radius:999px;display:grid;place-items:center;cursor:pointer;background:var(--primary,#651E2C);color:var(--primary-foreground,#FAF6F0)}.mz-header-search button svg{width:18px;height:18px}.mz-header-icons{display:flex;align-items:center;gap:2px}.mz-header-icon{width:40px;height:40px;display:grid;place-items:center;border-radius:50%;color:inherit}.mz-header-icon:hover{background:color-mix(in srgb,currentColor 10%,transparent)}.mz-header-icon svg{width:20px;height:20px}.mz-header-menu{display:none}.mz-header-bar{display:flex;align-items:center;gap:10px;padding:6px 32px;min-height:48px;border-top:1px solid color-mix(in srgb,currentColor 10%,transparent)}.mz-header-bar nav{display:flex;align-items:center;gap:2px;flex:1;min-width:0;overflow-x:auto;scrollbar-width:none}.mz-header-bar nav a{white-space:nowrap;font-size:15px;min-height:36px;display:inline-flex;align-items:center;padding:0 12px;border-radius:999px;color:color-mix(in srgb,currentColor 82%,transparent)}.mz-header-bar nav a:hover{background:color-mix(in srgb,currentColor 10%,transparent);color:inherit}.mz-header-bar nav a:first-child{background:color-mix(in srgb,currentColor 10%,transparent);color:inherit;font-weight:600}.mz-header-cta{white-space:nowrap;background:var(--primary,#651E2C);color:var(--primary-foreground,#FAF6F0);padding:8px 16px;border-radius:var(--radius,8px);font-size:14px;text-decoration:none}@media(max-width:768px){.mz-header-rich .mz-header-main{padding:8px 14px;gap:8px}.mz-header-rich .mz-site-brand{font-size:18px}.mz-header-search{order:9;flex-basis:100%;max-width:none}.mz-header-bar{display:none}.mz-header-menu{display:block;margin-inline-start:auto}.mz-header-menu summary{list-style:none;width:40px;height:40px;display:grid;place-items:center;border-radius:50%;cursor:pointer}.mz-header-menu summary::-webkit-details-marker{display:none}.mz-header-menu summary svg{width:22px;height:22px}.mz-header-menu summary .mz-menu-close{display:none}.mz-header-menu[open] summary .mz-menu-close{display:block}.mz-header-menu[open] summary .mz-menu-open{display:none}.mz-header-menu nav{position:absolute;inset-inline:0;top:100%;z-index:20;display:flex;flex-direction:column;gap:2px;padding:8px 14px 14px;background:var(--background,#FAF6F0);color:var(--foreground,#262321);border-top:1px solid color-mix(in srgb,currentColor 12%,transparent)}.mz-site-header-dark .mz-header-menu nav{background:var(--dark,#20303C);color:var(--dark-foreground,#F3EEE4)}.mz-header-menu nav a{padding:10px 12px;border-radius:8px;text-decoration:none;color:inherit}.mz-header-menu nav a:hover{background:color-mix(in srgb,currentColor 8%,transparent)}.mz-header-menu nav .mz-header-cta{margin-top:8px;text-align:center}}"
_BASE_CSS += ".mz-search-outline .mz-header-search{background:transparent;border:1px solid color-mix(in srgb,currentColor 35%,transparent);color:inherit}.mz-search-outline .mz-header-search input{color:inherit}.mz-search-outline .mz-header-search input::placeholder{color:color-mix(in srgb,currentColor 55%,transparent)}.mz-bar-plain .mz-header-bar{border-top:0}.mz-bar-plain .mz-header-bar nav a{border-radius:6px;min-height:32px}.mz-bar-plain .mz-header-bar nav a:first-child{background:none;font-weight:500;color:color-mix(in srgb,currentColor 82%,transparent)}.mz-bar-plain .mz-header-bar nav a:first-child:hover{color:inherit}.mz-density-compact .mz-header-main{padding:6px 32px;gap:10px}.mz-density-compact .mz-header-search{max-width:560px}.mz-density-compact .mz-header-search button{width:30px;height:30px}.mz-density-compact .mz-header-icon{width:34px;height:34px}.mz-density-compact .mz-header-bar{padding:4px 32px;min-height:40px}.mz-density-compact .mz-header-bar nav a{min-height:30px;font-size:14px}@media(max-width:768px){.mz-density-compact .mz-header-main{padding:4px 14px}}"
_BASE_CSS += ".mz-row-start .mz-header-main{justify-content:flex-start}.mz-row-center .mz-header-main{justify-content:center}.mz-row-end .mz-header-main{justify-content:flex-end}.mz-row-between .mz-header-main{justify-content:space-between}.mz-row-around .mz-header-main{justify-content:space-around}.mz-row-evenly .mz-header-main{justify-content:space-evenly}.mz-row-start .mz-header-search,.mz-row-center .mz-header-search,.mz-row-end .mz-header-search,.mz-row-between .mz-header-search,.mz-row-around .mz-header-search,.mz-row-evenly .mz-header-search{flex:none;min-width:0;width:min(640px,100%);margin-inline:0}.mz-gap-tight .mz-header-main{gap:8px}.mz-gap-wide .mz-header-main{gap:24px}.mz-gap-custom .mz-header-main{gap:var(--row-gap,14px)}"
_BASE_CSS += ".mz-reorder .mz-site-logo,.mz-reorder .mz-site-brand{order:var(--ord-brand,1)}.mz-reorder .mz-header-search{order:var(--ord-search,2)}.mz-reorder .mz-header-icons{order:var(--ord-icons,3)}.mz-reorder .mz-header-main>nav,.mz-reorder .mz-header-main>.mz-site-actions{order:2}.mz-reorder .mz-header-menu{order:9}"
_BASE_CSS += ".mz-header-menu nav .mz-menu-bar{display:contents}@media(min-width:769px) and (max-width:1024px){.mz-t-density-compact .mz-header-main{padding:6px 32px;gap:10px}.mz-t-density-compact .mz-header-search{max-width:560px}.mz-t-density-compact .mz-header-search button{width:30px;height:30px}.mz-t-density-compact .mz-header-icon{width:34px;height:34px}.mz-t-density-compact .mz-header-bar{padding:4px 32px;min-height:40px}.mz-t-density-compact .mz-header-bar nav a{min-height:30px;font-size:14px}.mz-t-hide-search .mz-header-search{display:none}.mz-t-hide-bar .mz-header-bar{display:none}}"
_BASE_CSS += ".mz-header-locale{display:flex;align-items:center;gap:4px}.mz-locale-switch{display:inline-flex;align-items:center;min-height:32px;padding:0 10px;border-radius:999px;font-size:13px;font-weight:650;color:inherit;text-decoration:none;border:1px solid rgba(127,127,127,.45)}"
_BASE_CSS += "@media(max-width:768px){.mz-columns-2,.mz-columns-3,.mz-columns-4,.mz-columns-5,.mz-columns-6{grid-template-columns:1fr}.mz-columns.mz-cols-custom{grid-template-columns:var(--mz-tracks-m,1fr)}.mz-columns.mz-cols-custom-m{grid-template-columns:var(--mz-tracks-m)}.mz-node.mz-minh-custom>:first-child{min-height:var(--mz-minh-m,var(--mz-minh))}.mz-columns{gap:16px}.mz-section{padding:24px 16px}.mz-width-half,.mz-width-third,.mz-width-two_thirds,.mz-width-three_fifths{width:100%}.mz-node.mz-width-custom{width:var(--mz-width-m,100%)}.mz-reorder .mz-header-search{order:9;flex-basis:100%}.mz-m-density-compact .mz-header-main{padding:4px 14px;gap:8px}.mz-m-hide-search .mz-header-search{display:none}.mz-m-hide-bar .mz-header-menu nav .mz-menu-bar{display:none}}"
_BASE_CSS += ".mz-form{display:flex;flex-direction:column;gap:14px;max-width:520px;margin:0 0 24px}.mz-form-center{margin-inline:auto;text-align:center}.mz-form-center .mz-form-field{text-align:start}.mz-form-title{font-size:clamp(21px,2.2vw,27px);font-weight:750;margin:0}.mz-form-field{display:flex;flex-direction:column;gap:6px}.mz-form-label{font-size:14px;font-weight:600}.mz-form-input{width:100%;padding:10px 12px;border:1px solid color-mix(in srgb,var(--foreground,#262321) 22%,transparent);border-radius:var(--radius,8px);background:var(--card,#fff);color:inherit;font:inherit;font-size:15px}textarea.mz-form-input{resize:vertical}.mz-form-hp{display:none}.mz-form-inline{max-width:none;flex-direction:row;flex-wrap:wrap;align-items:flex-end}.mz-form-inline .mz-form-title,.mz-form-inline .mz-form-success{flex:1 1 100%}.mz-form-inline .mz-form-field{flex:1 1 220px}.mz-form-inline .mz-form-submit{align-self:auto}.mz-form-success{padding:10px 14px;border-radius:var(--radius,8px);background:color-mix(in srgb,var(--primary,#651E2C) 12%,transparent);font-size:15px}.mz-form-submit{align-self:flex-start;border:0;cursor:pointer;font:inherit}.mz-form-center .mz-form-submit{align-self:center}.mz-form-inert .mz-form-input{pointer-events:none;opacity:.7}.mz-form-inert .mz-form-submit{opacity:.6;cursor:default}"
_BASE_CSS += ".mz-site-logo{height:32px;width:auto}.mz-site-footer a{color:inherit;text-decoration:none}.mz-footer-groups{display:flex;gap:32px;flex-wrap:wrap}.mz-footer-group{display:flex;flex-direction:column;gap:10px}.mz-footer-group-title{font-weight:650}.mz-footer-socials{display:flex;gap:14px;align-items:center}.mz-footer-social{display:inline-flex;align-items:center;min-height:44px}.mz-footer-social svg{width:20px;height:20px}"
for _token, _size in _SPACER_PX.items():
    _BASE_CSS += (f".mz-padding-{_token}{{padding:{_size}px}}.mz-gap-{_token}{{gap:{_size}px}}"
                  f".mz-height-{_token} .mz-spacer{{height:{_size}px}}"
                  f".mz-section.mz-gap-{_token}{{display:flex;flex-direction:column;gap:{_size}px}}")


def render_page(tree: dict, lang: str = "ar", device: str = "desktop", validate: bool = True,
                link_base: str | None = None, form_action_base: str | None = None,
                form_sent: str | None = None) -> str:
    """The page body: every visible block of the published tree, in order.
    `form_action_base`: per-page submission URL prefix (e.g. "/forms/studio/about");
    when set, form blocks render as live POST forms to <base>/<node_id>. `form_sent`:
    the node id of a form whose submission was just accepted, so it shows its
    success message."""
    if validate and page_problems(tree):
        raise ValueError("render_page() takes a tree that passed page_problems()")
    def unresolved(node):
        return isinstance(node, dict) and ("bindings" in node or "repeat" in node or "card" in node or any(unresolved(c) for c in node.get("children", []) or []))
    if unresolved(tree):
        raise ValueError("Dynamic content requires authorized provider resolution before rendering.")
    return _render_node(tree, lang, device, link_base, form_action_base, form_sent)


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



_LOCALE_LABELS = {"ar": "العربية", "en": "English"}


_HEADER_ICONS = {
    "whatsapp": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    "cart": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "heart": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
}


def _header_icon(name: str) -> str:
    path = _HEADER_ICONS.get(name, _HEADER_ICONS["globe"])
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')


# Footer social row: bounded brand glyphs, inline SVG only (no icon font, no
# network fetch), same stroke style as the header icon row. Mirrored
# element-for-element in the editor preview (treerender.tsx SOCIAL_ICON_MARKUP).
_SOCIAL_ICONS = {
    "whatsapp": _HEADER_ICONS["whatsapp"],
    "facebook": '<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>',
    "instagram": '<rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/>',
    "x": '<path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z"/>',
    "youtube": '<path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.33z"/><polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02"/>',
    "linkedin": '<path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4V8h4z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/>',
}


def _social_icon(name: str) -> str:
    path = _SOCIAL_ICONS.get(name)
    if path is None:
        return ""
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>')

def _theme_chrome(theme: dict | None, link_base: str | None = None, locale: dict | None = None) -> tuple[str, str]:
    """Constrained v0 site chrome: escaped brand, allow-listed links; no markup from the theme."""
    if not isinstance(theme, dict):
        return "", ""
    header = theme.get("header")
    head_html = ""
    if isinstance(header, dict):
        brand = header.get("brand")
        order_list = header.get("element_order")
        order_map = {}
        if isinstance(order_list, list) and order_list:
            for i, token in enumerate(order_list):
                order_map[token] = i + 1
            for token in ("brand", "search", "icons"):
                if token not in order_map:
                    order_map[token] = len(order_map) + 1
        brand_style = f' style="--ord-brand:{order_map["brand"]}"' if order_map else ""
        search_style_attr = f' style="--ord-search:{order_map["search"]}"' if order_map else ""
        icons_style = f' style="--ord-icons:{order_map["icons"]}"' if order_map else ""
        brand_html = f'<span class="mz-site-brand"{brand_style}>{_esc(str(brand)[:80])}</span>' if brand else ""
        logo = _safe_src(header.get("logo"))
        logo_html = f'<img class="mz-site-logo"{brand_style} src="{_esc(logo)}" alt="">' if logo else ""
        links = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(header.get("links"), link_base=link_base))
        actions = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(header.get("actions"), 4, link_base=link_base))
        nav = f"<nav>{links}</nav>" if links else ""
        act = f'<div class="mz-site-actions">{actions}</div>' if actions else ""
        search_html = ""
        if header.get("search_enabled") is True:
            target = header.get("search_target")
            if isinstance(target, str) and target.startswith("/") and page_url(target, "href"):
                placeholder = str(header.get("search_placeholder") or "")[:80]
                hidden_lang = ""
                if locale and locale.get("current") != locale.get("default"):
                    hidden_lang = f'<input type="hidden" name="lang" value="{_esc(str(locale["current"]))}">'
                search_html = (f'<form class="mz-header-search"{search_style_attr} role="search" action="{_esc(_site_link(target, link_base))}" method="get">'
                               f'<input type="search" name="q" placeholder="{_esc(placeholder)}" aria-label="{_esc(placeholder)}">{hidden_lang}'
                               f'<button type="submit" aria-label="{_esc(placeholder or "Search")}">{_header_icon("search")}</button></form>')
        icons_html = ""
        icons = header.get("icons")
        if isinstance(icons, list):
            parts = []
            for entry in icons[:6]:
                if not isinstance(entry, dict):
                    continue
                href = _safe_href(entry.get("href"))
                label = entry.get("label")
                name = entry.get("icon")
                if href is None or not isinstance(label, str) or not label.strip() or name not in _HEADER_ICONS:
                    continue
                parts.append(f'<a class="mz-header-icon" href="{_esc(_site_link(href, link_base))}" aria-label="{_esc(label.strip()[:40])}" title="{_esc(label.strip()[:40])}">{_header_icon(str(name))}</a>')
            if parts:
                icons_html = f'<div class="mz-header-icons"{icons_style}>{"".join(parts)}</div>'
        locale_html = ""
        if locale and locale.get("switches"):
            switch_links = "".join(
                f'<a class="mz-locale-switch" href="{_esc(href)}" hreflang="{_esc(code)}">{_esc(label)}</a>'
                for code, label, href in locale["switches"])
            locale_html = f'<div class="mz-header-locale">{switch_links}</div>'
        bar_html = ""
        bar_links = "".join(f'<a href="{_esc(h)}">{_esc(l)}</a>' for h, l in _theme_links(header.get("bar_links"), 12, link_base=link_base))
        cta_label = header.get("bar_cta_label")
        cta_href = _safe_href(header.get("bar_cta_href"))
        cta_html = ""
        if isinstance(cta_label, str) and cta_label.strip() and cta_href is not None:
            cta_html = f'<a class="mz-header-cta" href="{_esc(_site_link(cta_href, link_base))}">{_esc(cta_label.strip()[:40])}</a>'
        if bar_links or cta_html:
            bar_nav = f"<nav>{bar_links}</nav>" if bar_links else ""
            bar_html = f'<div class="mz-header-bar">{bar_nav}{cta_html}</div>'
        dev_t = header.get("tablet") if isinstance(header.get("tablet"), dict) else {}
        dev_m = header.get("mobile") if isinstance(header.get("mobile"), dict) else {}
        menu_bar_links = f'<span class="mz-menu-bar">{bar_links}</span>' if (bar_links and dev_m.get("hide_bar") is True) else bar_links
        menu_html = ""
        if links or bar_links or cta_html:
            menu_html = ('<details class="mz-header-menu"><summary aria-label="Menu">'
                         '<svg class="mz-menu-open" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>'
                         '<svg class="mz-menu-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>'
                         f'</summary><nav>{links}{menu_bar_links}{cta_html}</nav></details>')
        if logo_html or brand_html or nav or act or search_html or icons_html or locale_html or bar_html:
            header_class = "mz-site-header mz-header-centered" if header.get("layout") == "centered" else "mz-site-header"
            if header.get("surface") == "dark":
                header_class += " mz-site-header-dark"
            if header.get("search_style") == "outline":
                header_class += " mz-search-outline"
            if header.get("bar_style") == "plain":
                header_class += " mz-bar-plain"
            if header.get("density") == "compact":
                header_class += " mz-density-compact"
            if header.get("row_align") in ("start", "center", "end", "between", "around", "evenly"):
                header_class += " mz-row-" + header["row_align"]
            if header.get("row_gap") in ("tight", "wide"):
                header_class += " mz-gap-" + header["row_gap"]
            gap_px = header.get("gap_px")
            header_style = ""
            if type(gap_px) is int and 0 <= gap_px <= 64:
                header_class += " mz-gap-custom"
                header_style = f' style="--row-gap:{gap_px}px"'
            if order_map:
                header_class += " mz-reorder"
            for dev, prefix in ((dev_t, "mz-t-"), (dev_m, "mz-m-")):
                if dev.get("density") == "compact":
                    header_class += " " + prefix + "density-compact"
                if dev.get("hide_search") is True:
                    header_class += " " + prefix + "hide-search"
                if dev.get("hide_bar") is True:
                    header_class += " " + prefix + "hide-bar"
            if search_html or icons_html or bar_html:
                header_class += " mz-header-rich"
                head_html = f'<header class="{header_class}"{header_style}><div class="mz-header-main">{logo_html}{brand_html}{search_html}{nav}{act}{icons_html}{locale_html}{menu_html}</div>{bar_html}</header>'
            else:
                head_html = f'<header class="{header_class}"{header_style}>{logo_html}{brand_html}{nav}{act}{locale_html}</header>'
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
        socials_html = ""
        socials = footer.get("socials")
        if isinstance(socials, list):
            sparts = []
            for entry in socials[:6]:
                if not isinstance(entry, dict):
                    continue
                href = _safe_href(entry.get("href"))
                label = entry.get("label")
                name = entry.get("icon")
                if href is None or not isinstance(label, str) or not label.strip() or name not in _SOCIAL_ICONS:
                    continue
                sparts.append(f'<a class="mz-footer-social" href="{_esc(_site_link(href, link_base))}" aria-label="{_esc(label.strip()[:40])}" title="{_esc(label.strip()[:40])}">{_social_icon(str(name))}</a>')
            if sparts:
                socials_html = f'<div class="mz-footer-socials">{"".join(sparts)}</div>'
        parts = "".join(f"<span>{_esc(x)}</span>" for x in lines) + links + groups_html + socials_html
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
                    device: str = "desktop", link_base: str | None = None,
                    form_action_base: str | None = None, form_sent: str | None = None) -> str:
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

    languages = [c for c in (meta.get("languages") or []) if isinstance(c, str) and PAGE_LANGUAGE.fullmatch(c)][:4]
    default_language = meta.get("default_language")
    if default_language not in languages:
        default_language = languages[0] if languages else lang
    locale = None
    if canonical and len(languages) > 1 and lang in languages:
        def _lang_url(code: str) -> str:
            if code == default_language:
                return canonical
            return canonical + ("&" if "?" in canonical else "?") + "lang=" + code
        if not isinstance(meta.get("alternates"), dict):
            alternates = {code: _lang_url(code) for code in languages}
            for code, url in alternates.items():
                if page_url(url, "url"):
                    head.append(f'<link rel="alternate" hreflang="{_esc(code)}" href="{_esc(url)}">')
        locale = {"current": lang, "default": default_language,
                  "switches": [(code, _LOCALE_LABELS.get(code, code), _lang_url(code))
                               for code in languages if code != lang]}

    header_html, footer_html = _theme_chrome(theme, link_base=link_base, locale=locale)
    body = header_html + render_page(tree, lang=lang, device=device, link_base=link_base,
                                     form_action_base=form_action_base, form_sent=form_sent) + footer_html
    return _DOCUMENT.render(language=lang, direction=direction,
                            head="\n".join(head) + "<style>" + _BASE_CSS + "</style>" + _theme_style(theme), body=body)
