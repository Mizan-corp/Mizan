// React renderer for the S2 page tree: mirrors shared/backend/app/platform/site/render.py
// block-for-block (same mz-* classes, same settings cascade, same visibility and content
// rules) so the studio's live preview shows exactly what the durable tree holds. If a
// block cannot be represented, both renderers must grow together - never diverge.
import type { CSSProperties } from 'react';
import type { PageNode } from './pagetree';
import { IconGlyph, ICON_MARKUP } from './nativeIcons';

export type Device = 'desktop' | 'tablet' | 'mobile';

const SPACER_PX: Record<string, number> = { none: 0, xs: 8, s: 16, m: 32, l: 64, xl: 128 };

// Registry enum tokens that become mz-<key>-<value> classes (must mirror PAGE_BLOCKS).
const ENUM_SETTINGS: Record<string, string[]> = {
  padding: ['none', 'xs', 's', 'm', 'l', 'xl'],
  gap: ['none', 'xs', 's', 'm', 'l', 'xl'],
  height: ['none', 'xs', 's', 'm', 'l', 'xl'],
  background: ['background', 'card', 'primary', 'dark', 'dark_raised'],
  size: ['auto', 's', 'm', 'l'],
  wrap: ['normal', 'balance'],
  tone: ['none', 'primary', 'dark', 'card'],
  max_width: ['narrow', 'normal', 'wide', 'full'],
  width: ['auto', 'full', 'half', 'third', 'two_thirds'],
  align: ['start', 'center', 'end'],
  min_height: ['s', 'm', 'l'],
  animation: ['none','fade','rise','slide','zoom'],
  animation_speed:['quick','normal','slow'],
  animation_delay:['none','short','long'],
};

function settingsOf(node: PageNode, device: Device): Record<string, string | number | boolean> {
  const per = node.settings || {};
  return { ...(per.desktop || {}), ...(device === 'desktop' ? {} : (per[device] || {})) };
}

function contentOf(node: PageNode, lang: string): Record<string, unknown> {
  return (node.content?.[lang] || {}) as Record<string, unknown>;
}

// Language-neutral references that may fall back across languages: an image's
// src and a button's href. Fallback applies only when the active language never
// set the key; an explicit empty value is respected, so a deliberately blank
// link or image stays blank. Text fields never fall back. Mirrors render.py's
// _content_ref; keep the semantics identical.
function contentRef(node: PageNode, lang: string, key: 'src' | 'href'): unknown {
  const langs = (node.content || {}) as Record<string, Record<string, unknown>>;
  const active = langs[lang] || {};
  if (key in active) return active[key];
  for (const other of ['en', 'ar']) {
    if (other === lang) continue;
    const otherContent = langs[other] || {};
    if (key in otherContent) return otherContent[key];
  }
  return undefined;
}

const SAFE_TAGS = new Set(['p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'a', 'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'span']);
const DROP_WITH_CONTENT = new Set(['script', 'style', 'iframe', 'object', 'embed', 'template', 'svg', 'math']);

function safeUrl(value: unknown, kind: 'href' | 'url' | 'embed'): string | null {
  if (typeof value !== 'string' || !value || value.length > 2000) return null;
  if (/[\x00-\x20\x7f\\<>"']/.test(value)) return null;
  if (value.startsWith('/')) return kind !== 'embed' && !value.startsWith('//') ? value : null;
  if (value.startsWith('#')) return kind === 'href' ? value : null;
  try {
    const u = new URL(value);
    if (kind === 'href' && (u.protocol === 'mailto:' || u.protocol === 'tel:')) return u.username ? null : value;
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null;
    if (u.username || u.password) return null;
    return value;
  } catch { return null; }
}

/** Allowlist-sanitize rich text to the same shape render.py's sanitize_html produces. */
export function sanitizeHtml(markup: unknown): string {
  if (typeof markup !== 'string') return '';
  const doc = new DOMParser().parseFromString(markup, 'text/html');
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const walk = (el: Node): string => {
    if (el.nodeType === Node.TEXT_NODE) return esc(el.textContent || '');
    if (el.nodeType !== Node.ELEMENT_NODE) return '';
    const tag = (el as Element).tagName.toLowerCase();
    if (DROP_WITH_CONTENT.has(tag)) return '';
    const kids = [...el.childNodes].map(walk).join('');
    if (!SAFE_TAGS.has(tag)) return kids;
    if (tag === 'a') {
      const href = safeUrl((el as Element).getAttribute('href'), 'href');
      const title = (el as Element).getAttribute('title');
      const attrs = (href ? ` href="${esc(href)}"` : '') + (title ? ` title="${esc(title)}"` : '');
      return `<a${attrs}>${kids}</a>`;
    }
    return `<${tag}>${kids}</${tag}>`;
  };
  return [...doc.body.childNodes].map(walk).join('');
}

function enumClasses(s: Record<string, string | number | boolean>): string[] {
  const out: string[] = [];
  for (const [key, tokens] of Object.entries(ENUM_SETTINGS)) {
    const v = s[key];
    if (typeof v === 'string' && tokens.includes(v)) out.push(`mz-${key.replace('_', '-')}-${v}`);
  }
  if (s.rounded === true) out.push('mz-rounded');
  if (s.bleed === true) out.push('mz-bleed');
  if (s.background_fit === 'end_band' && typeof s.background_image === 'string' && s.background_image) out.push('mz-bg-band');
  return out;
}

// Mirrors render.py's _background_image_style: validated URL layer plus an optional
// theme-dark scrim, never arbitrary CSS from the tree.
function backgroundImageStyle(node: PageNode, s: Record<string, string | number | boolean>, lang = 'ar'): CSSProperties | undefined {
  if (node.type !== 'section' && node.type !== 'column') return undefined;
  const url = safeUrl(s.background_image, 'url');
  if (!url || /[();]/.test(url)) return undefined;
  const layers: string[] = [];
  if (s.background_dim === 'soft' || s.background_dim === 'strong') {
    const pct = s.background_dim === 'soft' ? '45%' : '72%';
    const scrim = `color-mix(in srgb, var(--dark, #20303C) ${pct}, transparent)`;
    layers.push(`linear-gradient(${scrim}, ${scrim})`);
  }
  layers.push(`url("${url}")`);
  if (s.background_fit === 'end_band') {
    // The band renders as a ::before side panel (studio.css .mz-bg-band):
    // exact 40% width, cover-cropped, direction-aware edge, hidden on mobile.
    return { ['--mz-bg' as never]: `url("${url}")` };
  }
  return { backgroundImage: layers.join(', ') };
}

function NodeView({ node, lang, device }: { node: PageNode; lang: string; device: Device }) {
  const s = settingsOf(node, device);
  if (s.visible === false) return null;
  const c = contentOf(node, lang);
  const ordered = s.reverse === true && node.type === 'columns' ? [...(node.children || [])].reverse() : (node.children || []);
  const kids = ordered.map(k => <NodeView key={k.id} node={k} lang={lang} device={device} />);
  let inner: React.ReactNode = null;
  switch (node.type) {
    case 'section': {
      // Echo the padding token on the section itself (mirrors render.py): the
      // wrapper's class cannot override the section's own default padding.
      const pad = typeof s.padding === 'string' && ['none','xs','s','m','l','xl'].includes(s.padding) ? ` mz-padding-${s.padding}` : '';
      inner = <section className={`mz-section${pad}`}>{kids}</section>; break;
    }
    case 'columns': {
      const declared = s.columns;
      const count = typeof declared === 'number' ? declared : (node.children?.length || 1);
      inner = <div className={`mz-columns mz-columns-${count}${s.stack ? ' mz-stack' : ''}`}>{kids}</div>; break;
    }
    case 'column': inner = <div className="mz-column">{kids}</div>; break;
    case 'canvas': inner = <div className="mz-canvas">{kids}</div>; break;
    case 'heading': {
      const level = typeof s.level === 'number' && s.level >= 1 && s.level <= 6 ? s.level : 2;
      const Tag = `h${level}` as 'h1';
      const iconName = typeof s.icon === 'string' && (ICON_MARKUP as Record<string, string>)[s.icon] ? s.icon : '';
      inner = <Tag className="mz-heading">{iconName && <span className="mz-heading-icon" aria-hidden="true"><IconGlyph name={iconName} /></span>}<span dangerouslySetInnerHTML={{ __html: accentHtml(String(c.text ?? '')) }} /></Tag>; break;
    }
    case 'text': {
      const variant = s.variant === 'eyebrow' || s.variant === 'note' || s.variant === 'check_list' ? ` mz-text-${s.variant}` : '';
      inner = <div className={`mz-text${variant}`} dangerouslySetInnerHTML={{ __html: sanitizeHtml(c.html) }} />; break;
    }
    case 'image': {
      const src = safeUrl(contentRef(node, lang, 'src'), 'url');
      if (!src) {
        // Registered decorative art, kept in sync with render.py's image branch.
        const art = s.art === 'sculpture' || s.art === 'sculpture_alt' ? String(s.art).replace('_', '-') : '';
        if (!art) return null;
        inner = <div className={`mz-art mz-art-${art}`} role="img" aria-label={String(c.alt ?? '')}><div className="mz-art-orb" /><div className="mz-art-plinth" /></div>; break;
      }
      inner = <img className="mz-image" src={src} alt={String(c.alt ?? '')} loading="lazy" />; break;
    }
    case 'gallery': {
      const mode = s.mode === 'slider' ? 'slider' : 'grid';
      const imgs = (Array.isArray(c.images) ? c.images : [])
        .filter((e): e is Record<string, unknown> => !!e && typeof e === 'object')
        .map((e, i) => { const src = safeUrl(e.src, 'url'); return src ? <img key={i} src={src} alt={String(e.alt ?? '')} loading="lazy" /> : null; });
      inner = <div className="mz-gallery" data-mode={mode}>{imgs}</div>; break;
    }
    case 'video_embed': {
      const url = safeUrl(c.url, 'embed');
      if (!url || !/^https:\/\/(www\.youtube(-nocookie)?\.com\/embed\/|player\.vimeo\.com\/video\/|www\.google\.com\/maps\/embed)/.test(url)) return null;
      inner = <div className="mz-embed" data-aspect={String(s.aspect ?? '16:9')}><iframe src={url} loading="lazy" allowFullScreen referrerPolicy="strict-origin-when-cross-origin" /></div>; break;
    }
    case 'button': {
      if (!c.label) return null; // labels never fall back; an untranslated button stays hidden, matching render.py
      const href = safeUrl(contentRef(node, lang, 'href'), 'href');
      if (!href) return null;
      const style = ['primary', 'secondary', 'ghost', 'soft'].includes(String(s.style)) ? String(s.style) : 'primary';
      inner = <a className={`mz-button mz-button-${style}`} href={href} onClick={e => e.preventDefault()}>{String(c.label ?? '')}</a>; break;
    }
    case 'icon_list': {
      const items = (Array.isArray(c.items) ? c.items : [])
        .filter((e): e is Record<string, unknown> => !!e && typeof e === 'object' && typeof e.icon === 'string')
        .map((e, i) => <li key={i}><IconGlyph name={String(e.icon)} /><span>{String(e.text ?? '')}</span></li>);
      inner = <ul className="mz-icon-list">{items}</ul>; break;
    }
    case 'icon': {
      const name = typeof s.icon === 'string' ? s.icon : '';
      if (!ICON_MARKUP[name]) return null;
      inner = <span className="mz-icon-badge" aria-hidden="true"><IconGlyph name={name} /></span>; break;
    }
    case 'spacer': {
      const px = SPACER_PX[String(s.height)] ?? 0;
      inner = <div className="mz-spacer" aria-hidden="true" style={{ height: px }} />; break;
    }
    case 'divider': {
      const style = ['solid', 'dashed', 'dotted'].includes(String(s.style)) ? String(s.style) : 'solid';
      inner = <hr className={`mz-divider mz-divider-${style}`} />; break;
    }
    case 'html': inner = <div className="mz-html" dangerouslySetInnerHTML={{ __html: sanitizeHtml(c.html) }} />; break;
    default: return null; // unknown block: render nothing, like render.py
  }
  const bgStyle = backgroundImageStyle(node, s, lang);
  const cls = `mz-node ${enumClasses(s).join(' ')}${bgStyle ? ' mz-bg-image' : ''}`;
  return <div id={node.id} className={cls} style={bgStyle}>{inner}</div>;
}

export interface ThemeChrome {
  layout?: 'inline'|'centered';
  surface?: 'default'|'dark';
  brand?: string;
  logo?: string;
  links?: { label: string; href: string }[];
  actions?: { label: string; href: string }[];
}

export interface ThemeSpec {
  colors?: { light?: Record<string, string> };
  typography?: { family?: string };
  shape?: { radius?: number };
  header?: ThemeChrome;
  footer?: { layout?:'split'|'stacked'; lines?: string[]; links?: { label: string; href: string }[]; groups?: { title: string; links: { label: string; href: string }[] }[] };
}

function cleanLinks(entries: ThemeChrome['links'], limit = 8) {
  return (entries || []).slice(0, limit)
    .map(e => ({ href: safeUrl(e?.href, 'href'), label: String(e?.label ?? '').trim().slice(0, 40) }))
    .filter((e): e is { href: string; label: string } => !!e.href && !!e.label);
}

const FONT_STACKS: Record<string, string> = {
  'sans-serif': 'system-ui,sans-serif',
  serif: "Georgia,'Times New Roman',serif",
  monospace: 'ui-monospace,Menlo,monospace',
};

const ACCENT = /<mark>([^<]{0,120}?)<\/mark>/g;
const escText = (v: string) => v.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// Bounded heading accent: only literal <mark>..</mark> pairs (no attributes,
// no nesting, no other markup) become accent spans; everything else escapes.
export function accentHtml(text: string): string {
  if (!text.includes('<mark>')) return escText(text);
  let out = '', pos = 0;
  for (const m of text.matchAll(ACCENT)) {
    out += escText(text.slice(pos, m.index)) + '<mark>' + escText(m[1]) + '</mark>';
    pos = m.index + m[0].length;
  }
  return out + escText(text.slice(pos));
}

export function themeStyle(theme?: ThemeSpec): CSSProperties {
  const allowed = new Set(['background', 'foreground', 'card', 'primary', 'primary-foreground', 'dark', 'dark-foreground']);
  const style: Record<string, string> = {};
  for (const [k, v] of Object.entries(theme?.colors?.light || {})) {
    if (allowed.has(k) && /^#[0-9a-fA-F]{6}$/.test(v)) style[`--${k}`] = v;
  }
  const radius = theme?.shape?.radius;
  if (typeof radius === 'number' && Number.isInteger(radius) && radius >= 0 && radius <= 64) style['--radius'] = `${radius}px`;
  const stack = FONT_STACKS[theme?.typography?.family || ''];
  if (stack) style.fontFamily = stack;
  return style as CSSProperties;
}

export function ThemeHeader({ header }: { header?: ThemeChrome }) {
  if (!header) return null;
  const links = cleanLinks(header.links);
  const actions = cleanLinks(header.actions, 4);
  const brand = header.brand ? String(header.brand).slice(0, 80) : '';
  const logo = header.logo ? safeUrl(header.logo, 'url') : null;
  if (!logo && !brand && !links.length && !actions.length) return null;
  return (
    <header className={`mz-site-header${header?.layout==='centered'?' mz-header-centered':''}${header?.surface==='dark'?' mz-site-header-dark':''}`}>
      {logo && <img className="mz-site-logo" src={logo} alt="" />}
      {brand && <span className="mz-site-brand">{brand}</span>}
      {!!links.length && <nav>{links.map((l, i) => <a key={i} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}</nav>}
      {!!actions.length && <div className="mz-site-actions">{actions.map((l, i) => <a key={i} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}</div>}
    </header>
  );
}

export function ThemeFooter({ footer }: { footer?: ThemeSpec['footer'] }) {
  if (!footer) return null;
  const lines = (footer.lines || []).slice(0, 4).filter(x => typeof x === 'string' && x.trim()).map(x => String(x).slice(0, 120));
  const links = cleanLinks(footer.links);
  const groups = (footer.groups ?? []).slice(0, 4)
    .map(g => ({ title: String(g?.title ?? '').trim().slice(0, 40), links: cleanLinks(g?.links, 6) }))
    .filter(g => g.title && g.links.length);
  if (!lines.length && !links.length && !groups.length) return null;
  return (
    <footer className={`mz-site-footer${footer?.layout==='stacked'?' mz-footer-stacked':''}`}>
      {lines.map((x, i) => <span key={i}>{x}</span>)}
      {links.map((l, i) => <a key={`l${i}`} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}
      {!!groups.length && <div className="mz-footer-groups">{groups.map((g, i) => (
        <div className="mz-footer-group" key={`g${i}`}>
          <span className="mz-footer-group-title">{g.title}</span>
          {g.links.map((l, j) => <a key={`gl${j}`} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}
        </div>
      ))}</div>}
    </footer>
  );
}

export default function TreePreview({ tree, lang, device, theme }: { tree: PageNode; lang: string; device: Device; theme?: ThemeSpec }) {
  return (
    <div className="mz-site" dir={lang.split('-')[0] === 'ar' ? 'rtl' : 'ltr'} style={themeStyle(theme)}>
      <ThemeHeader header={theme?.header} />
      <NodeView node={tree} lang={lang} device={device} />
      <ThemeFooter footer={theme?.footer} />
    </div>
  );
}
