// React renderer for the S2 page tree: mirrors shared/backend/app/platform/site/render.py
// block-for-block (same mz-* classes, same settings cascade, same visibility and content
// rules) so the studio's live preview shows exactly what the durable tree holds. If a
// block cannot be represented, both renderers must grow together - never diverge.
import type { CSSProperties, ReactNode } from 'react';
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
  width: ['auto', 'full', 'half', 'third', 'two_thirds', 'three_fifths', 'fit'],
  align: ['start', 'center', 'end'],
  shadow: ['s', 'm', 'l'],
  gradient: ['soft', 'brand', 'dark'],
  hover: ['lift', 'glow'],
  min_height: ['s', 'm', 'l'],
  animation: ['none','fade','rise','slide','zoom'],
  animation_speed:['quick','normal','slow'],
  animation_delay:['none','short','long'],
};

function settingsOf(node: PageNode, device: Device): Record<string, string | number | boolean | number[]> {
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

function enumClasses(s: Record<string, string | number | boolean | number[]>): string[] {
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
function backgroundImageStyle(node: PageNode, s: Record<string, string | number | boolean | number[]>, _lang = 'ar'): CSSProperties | undefined {
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
      // Gap token echoed like padding (mirrors render.py): spacing between the section's rows.
      const gap = typeof s.gap === 'string' && ['none','xs','s','m','l','xl'].includes(s.gap) ? ` mz-gap-${s.gap}` : '';
      inner = <section className={`mz-section${pad}${gap}`}>{kids}</section>; break;
    }
    case 'columns': {
      const declared = s.columns;
      const count = typeof declared === 'number' ? declared : (node.children?.length || 1);
      // Free divider-drag ratio (mirrors render.py): numeric fr weights only.
      const tracksD = ((node.settings?.desktop ?? {}) as Record<string, unknown>).tracks;
      const tracks = Array.isArray(tracksD) ? tracksD : null;
      const okTracks = tracks && tracks.length === (node.children?.length ?? 0) && tracks.length >= 2
        && tracks.every(v => typeof v === 'number' && Number.isFinite(v) && v >= 0.2 && v <= 8);
      const rawTracksM = ((node.settings?.mobile ?? {}) as Record<string, unknown>).tracks;
      const okTracksM = Array.isArray(rawTracksM) && rawTracksM.length === kids.length && rawTracksM.every(v => typeof v === 'number' && Number.isFinite(v) && v >= 0.2 && v <= 8);
      const trackStyle = okTracks ? { ['--mz-tracks' as string]: (tracks as number[]).map(v => `${v}fr`).join(' '), ...(okTracksM ? { ['--mz-tracks-m' as string]: (rawTracksM as number[]).map(v => `${v}fr`).join(' ') } : {}) } as React.CSSProperties
        : okTracksM ? { ['--mz-tracks-m' as string]: (rawTracksM as number[]).map(v => `${v}fr`).join(' ') } as React.CSSProperties : undefined;
      inner = <div className={`mz-columns mz-columns-${count}${s.stack ? ' mz-stack' : ''}${okTracks ? ' mz-cols-custom' : ''}${!okTracks && okTracksM ? ' mz-cols-custom-m' : ''}`} style={trackStyle}>{kids}</div>; break;
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
    case 'form': {
      // Studio always renders the inert variant (mirrors render.py without a
      // form_action_base): fields are visible but the block can never post.
      const title = typeof c.title === 'string' ? c.title : '';
      const controls: [string, string, string, boolean][] = [];
      if (s.field_name === true) controls.push(['name', String(c.name_label ?? 'Name'), 'text', false]);
      if (s.field_email !== false) controls.push(['email', String(c.email_label ?? 'Email'), 'email', true]);
      if (s.field_phone === true) controls.push(['phone', String(c.phone_label ?? 'Phone'), 'text', false]);
      const inline = s.layout === 'inline';
      controls.push(['message', String(c.message_label ?? 'Message'), inline ? 'text' : 'textarea', true]);
      inner = (
        <div className={`mz-form mz-form-inert${s.align === 'center' ? ' mz-form-center' : ''}${inline ? ' mz-form-inline' : ''}`}>
          {title && <p className="mz-form-title">{title}</p>}
          {controls.map(([name, label, kind, required]) => (
            <div className="mz-form-field" key={name}>
              <label className="mz-form-label">{label}</label>
              {kind === 'textarea'
                ? <textarea className="mz-form-input" rows={4} maxLength={2000} required={required} readOnly />
                : <input className="mz-form-input" type={kind} maxLength={name === 'email' ? 254 : name === 'name' ? 120 : name === 'message' ? 2000 : 40} required={required} readOnly />}
            </div>
          ))}
          <button className="mz-button mz-button-primary mz-form-submit" type="button" disabled>{String(c.submit_label ?? 'Send')}</button>
        </div>
      ); break;
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
  const rawDesktop = (node.settings?.desktop ?? {}) as Record<string, unknown>;
  const rawMobile = (node.settings?.mobile ?? {}) as Record<string, unknown>;
  const pickMinH = (v: unknown) => typeof v === 'number' && Number.isInteger(v) && v >= 40 && v <= 1200 ? v : null;
  const pickWidth = (v: unknown) => typeof v === 'number' && Number.isInteger(v) && v >= 10 && v <= 100 ? v : null;
  // Free sizing vars come from the raw segments, not the merged active-device
  // settings, so the .mobile rules fall back exactly like the visitor media rules.
  const minH = pickMinH(rawDesktop.min_height_px);
  const minHM = pickMinH(rawMobile.min_height_px);
  const widthPct = pickWidth(rawDesktop.width_pct);
  const widthPctM = pickWidth(rawMobile.width_pct);
  const cls = `mz-node ${enumClasses(s).join(' ')}${bgStyle ? ' mz-bg-image' : ''}${(minH || minHM) ? ' mz-minh-custom' : ''}${(widthPct || widthPctM) ? ' mz-width-custom' : ''}`;
  const nodeStyle = { ...(bgStyle ?? {}), ...(minH ? { ['--mz-minh' as string]: `${minH}px` } : {}), ...(minHM ? { ['--mz-minh-m' as string]: `${minHM}px` } : {}), ...(widthPct ? { ['--mz-width' as string]: `${widthPct}%` } : {}), ...(widthPctM ? { ['--mz-width-m' as string]: `${widthPctM}%` } : {}) } as React.CSSProperties;
  return <div id={node.id} className={cls} style={Object.keys(nodeStyle).length ? nodeStyle : undefined}>{inner}</div>;
}

export type HeaderIconName = 'whatsapp'|'cart'|'heart'|'user'|'phone'|'globe'|'search';

export interface ThemeChrome {
  layout?: 'inline'|'centered';
  surface?: 'default'|'dark';
  brand?: string;
  logo?: string;
  links?: { label: string; href: string }[];
  actions?: { label: string; href: string }[];
  search_enabled?: boolean;
  search_target?: string;
  search_placeholder?: string;
  search_style?: 'filled'|'outline';
  bar_style?: 'pills'|'plain';
  density?: 'comfortable'|'compact';
  row_align?: 'start'|'center'|'end'|'between'|'around'|'evenly';
  row_gap?: 'tight'|'wide';
  gap_px?: number;
  tablet?: { density?: 'comfortable'|'compact'; hide_search?: boolean; hide_bar?: boolean };
  mobile?: { density?: 'comfortable'|'compact'; hide_search?: boolean; hide_bar?: boolean };
  element_order?: ('brand'|'search'|'icons')[];
  icons?: { icon: HeaderIconName; label: string; href: string }[];
  bar_links?: { label: string; href: string }[];
  bar_cta_label?: string;
  bar_cta_href?: string;
}

// Icon markup mirrors render.py's _HEADER_ICONS element-for-element (circles as
// circle elements, identical path data) so the editor preview and the visitor
// render the same glyphs.
export const HEADER_ICON_MARKUP: Record<HeaderIconName, ReactNode> = {
  whatsapp: <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>,
  cart: <><circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/></>,
  heart: <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>,
  user: <><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></>,
  phone: <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>,
  globe: <><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></>,
  search: <><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></>,
};
export const HEADER_ICON_PATHS: Record<HeaderIconName, string> = {
  whatsapp: 'whatsapp', cart: 'cart', heart: 'heart', user: 'user', phone: 'phone', globe: 'globe', search: 'search',
};

export function HeaderIcon({ name }: { name: string }) {
  const markup = HEADER_ICON_MARKUP[(name as HeaderIconName)] ?? HEADER_ICON_MARKUP.globe;
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{markup}</svg>;
}

export type SocialIconName = 'whatsapp' | 'facebook' | 'instagram' | 'x' | 'youtube' | 'linkedin';

// Mirrors render.py's _SOCIAL_ICONS element-for-element so the editor preview
// and the visitor render the same glyphs.
export const SOCIAL_ICON_MARKUP: Record<SocialIconName, ReactNode> = {
  whatsapp: <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>,
  facebook: <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>,
  instagram: <><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></>,
  x: <path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z"/>,
  youtube: <><path d="M22.54 6.42a2.78 2.78 0 0 0-1.94-2C18.88 4 12 4 12 4s-6.88 0-8.6.46a2.78 2.78 0 0 0-1.94 2A29 29 0 0 0 1 11.75a29 29 0 0 0 .46 5.33A2.78 2.78 0 0 0 3.4 19c1.72.46 8.6.46 8.6.46s6.88 0 8.6-.46a2.78 2.78 0 0 0 1.94-2 29 29 0 0 0 .46-5.25 29 29 0 0 0-.46-5.33z"/><polygon points="9.75 15.02 15.5 11.75 9.75 8.48 9.75 15.02"/></>,
  linkedin: <><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4V8h4z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></>,
};
export const SOCIAL_ICON_PATHS: Record<SocialIconName, string> = {
  whatsapp: 'whatsapp', facebook: 'facebook', instagram: 'instagram', x: 'x', youtube: 'youtube', linkedin: 'linkedin',
};

export function SocialIcon({ name }: { name: string }) {
  const markup = SOCIAL_ICON_MARKUP[(name as SocialIconName)] ?? null;
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{markup}</svg>;
}

export interface ThemeSpec {
  colors?: { light?: Record<string, string> };
  typography?: { family?: string };
  shape?: { radius?: number };
  header?: ThemeChrome;
  footer?: { layout?:'split'|'stacked'; lines?: string[]; links?: { label: string; href: string }[]; groups?: { title: string; links: { label: string; href: string }[] }[]; socials?: { icon: string; label: string; href: string }[] };
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

export function ThemeHeader({ header, device }: { header?: ThemeChrome; device?: Device }) {
  if (!header) return null;
  const devOver = device && device !== 'desktop' ? header[device] : undefined;
  const links = cleanLinks(header.links);
  const actions = cleanLinks(header.actions, 4);
  const brand = header.brand ? String(header.brand).slice(0, 80) : '';
  const logo = header.logo ? safeUrl(header.logo, 'url') : null;
  const searchTarget = !devOver?.hide_search && header.search_enabled && header.search_target ? safeUrl(header.search_target, 'href') : null;
  const searchPlaceholder = String(header.search_placeholder ?? '').slice(0, 80);
  const icons = (header.icons ?? []).slice(0, 6)
    .map(e => ({ icon: String(e?.icon ?? ''), href: safeUrl(e?.href, 'href'), label: String(e?.label ?? '').trim().slice(0, 40) }))
    .filter((e): e is { icon: string; href: string; label: string } => !!e.href && !!e.label && e.icon in HEADER_ICON_PATHS);
  const barLinks = devOver?.hide_bar ? [] : cleanLinks(header.bar_links, 12);
  const ctaLabel = String(header.bar_cta_label ?? '').trim().slice(0, 40);
  const ctaHref = header.bar_cta_href ? safeUrl(header.bar_cta_href, 'href') : null;
  const rich = !!(searchTarget || icons.length || barLinks.length || (ctaLabel && ctaHref));
  const orderMap: Record<string, number> = {};
  if (header.element_order?.length) {
    header.element_order.forEach((tok, i) => { orderMap[tok] = i + 1; });
    for (const tok of ['brand', 'search', 'icons']) if (!(tok in orderMap)) orderMap[tok] = Object.keys(orderMap).length + 1;
  }
  const brandStyle = header.element_order?.length ? ({ '--ord-brand': orderMap.brand } as CSSProperties) : undefined;
  const searchStyle = header.element_order?.length ? ({ '--ord-search': orderMap.search } as CSSProperties) : undefined;
  const iconsStyle = header.element_order?.length ? ({ '--ord-icons': orderMap.icons } as CSSProperties) : undefined;
  if (!logo && !brand && !links.length && !actions.length && !rich) return null;
  if (!rich) {
    return (
      <header className={`mz-site-header${header?.layout==='centered'?' mz-header-centered':''}${header?.surface==='dark'?' mz-site-header-dark':''}`}>
        {logo && <img className="mz-site-logo" src={logo} alt="" />}
        {brand && <span className="mz-site-brand">{brand}</span>}
        {!!links.length && <nav>{links.map((l, i) => <a key={i} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}</nav>}
        {!!actions.length && <div className="mz-site-actions">{actions.map((l, i) => <a key={i} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}</div>}
      </header>
    );
  }
  return (
    <header className={`mz-site-header mz-header-rich${header?.surface==='dark'?' mz-site-header-dark':''}${header?.search_style==='outline'?' mz-search-outline':''}${header?.bar_style==='plain'?' mz-bar-plain':''}${(devOver?.density ?? header?.density)==='compact'?' mz-density-compact':''}${header?.row_align?` mz-row-${header.row_align}`:''}${header?.row_gap?` mz-gap-${header.row_gap}`:''}${typeof header?.gap_px==='number'?' mz-gap-custom':''}${header?.element_order?.length?' mz-reorder':''}`} style={typeof header?.gap_px==='number'?({'--row-gap':header.gap_px+'px'} as CSSProperties):undefined}>
      <div className="mz-header-main">
        {logo && <img className="mz-site-logo" style={brandStyle} src={logo} alt="" />}
        {brand && <span className="mz-site-brand" style={brandStyle}>{brand}</span>}
        {searchTarget && <form className="mz-header-search" style={searchStyle} role="search" action={searchTarget ?? undefined} method="get" onSubmit={e => e.preventDefault()}>
          <input type="search" name="q" placeholder={searchPlaceholder} aria-label={searchPlaceholder} />
          <button type="submit" aria-label={searchPlaceholder || 'Search'}><HeaderIcon name="search" /></button>
        </form>}
        {!!links.length && <nav>{links.map((l, i) => <a key={i} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}</nav>}
        {!!actions.length && <div className="mz-site-actions">{actions.map((l, i) => <a key={i} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}</div>}
        {!!icons.length && <div className="mz-header-icons" style={iconsStyle}>{icons.map((ic, i) => <a key={i} className="mz-header-icon" href={ic.href} aria-label={ic.label} title={ic.label} onClick={e => e.preventDefault()}><HeaderIcon name={ic.icon} /></a>)}</div>}
        {(!!links.length || !!barLinks.length || (ctaLabel && ctaHref)) && <details className="mz-header-menu">
          <summary aria-label="Menu">
            <svg className="mz-menu-open" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
            <svg className="mz-menu-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>
          </summary>
          <nav>
            {links.map((l, i) => <a key={'n'+i} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}
            {barLinks.map((l, i) => <a key={'b'+i} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}
            {ctaLabel && ctaHref && <a className="mz-header-cta" href={ctaHref} onClick={e => e.preventDefault()}>{ctaLabel}</a>}
          </nav>
        </details>}
      </div>
      {(!!barLinks.length || (ctaLabel && ctaHref)) && <div className="mz-header-bar">
        {!!barLinks.length && <nav>{barLinks.map((l, i) => <a key={i} href={l.href} onClick={e => e.preventDefault()}>{l.label}</a>)}</nav>}
        {ctaLabel && ctaHref && <a className="mz-header-cta" href={ctaHref} onClick={e => e.preventDefault()}>{ctaLabel}</a>}
      </div>}
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
  const socials = (footer.socials ?? []).slice(0, 6)
    .map(e => ({ icon: String(e?.icon ?? ''), href: safeUrl(e?.href, 'href'), label: String(e?.label ?? '').trim().slice(0, 40) }))
    .filter((e): e is { icon: string; href: string; label: string } => !!e.href && !!e.label && e.icon in SOCIAL_ICON_PATHS);
  if (!lines.length && !links.length && !groups.length && !socials.length) return null;
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
      {!!socials.length && <div className="mz-footer-socials">{socials.map((s, i) => (
        <a key={`s${i}`} className="mz-footer-social" href={s.href} aria-label={s.label} title={s.label} onClick={e => e.preventDefault()}><SocialIcon name={s.icon} /></a>
      ))}</div>}
    </footer>
  );
}

export default function TreePreview({ tree, lang, device, theme }: { tree: PageNode; lang: string; device: Device; theme?: ThemeSpec }) {
  return (
    <div className="mz-site" dir={lang.split('-')[0] === 'ar' ? 'rtl' : 'ltr'} style={themeStyle(theme)}>
      <ThemeHeader header={theme?.header} device={device} />
      <NodeView node={tree} lang={lang} device={device} />
      <ThemeFooter footer={theme?.footer} />
    </div>
  );
}
