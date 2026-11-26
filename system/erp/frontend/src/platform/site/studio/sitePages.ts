// Storage client for the site pages API (feat/s2-page-storage, ADR-015 S2/S3).
// Talks to the workspace backend's /site/pages routes with the session cookie, like
// the rest of the ERP frontend. This is the studio's only path to persisted pages;
// the local Project model stays the editing model and is converted with toPageTree.
import { previewPayload, toPageTree, type PageNode } from './pagetree';
import { validChromeLinks, validFooterGroups, type Project } from './model';
import { safeNativeUrl } from './nativeTree';

export type PageStatus = 'draft' | 'published' | 'archived';

export type PageSummary = {
  id: string;
  slug: string;
  titles: Record<string, string>;
  status: PageStatus;
  has_draft: boolean;
  published: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type PageDetail = PageSummary & {
  edit_token?: string;
  draft_tree: PageNode | null;
  published_tree: PageNode | null;
};

export type PublicAccess = { enabled: boolean; host: string | null; url: string | null; connected_data?: boolean; sources?: string[] };
export type Revision = {
  id: string;
  number: number;
  titles: Record<string, string>;
  created_by: string | null;
  created_at: string | null;
};

type ListResponse<T> = { items: T[] };

export class SiteApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail || `Request failed (${status})`);
    this.name = 'SiteApiError';
  }
  get isAuth() { return this.status === 401; }
  get isForbidden() { return this.status === 403; }
  get isNotFound() { return this.status === 404; }
  get isConflict() { return this.status === 409; }
  get isInvalid() { return this.status === 422; }
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

/**
 * Single sign-on: Studio opened from the ERP on the same host reuses the ERP session token.
 * Only for the one configured production API origin, never for a caller-supplied origin.
 * Pure so it is testable: `raw` is the stored `mizan.session` JSON.
 */
export function ssoToken(baseUrl: string, hosted: string | undefined, raw: string | null): string | null {
  if (!hosted || baseUrl !== hosted) return null;
  try {
    const token = (JSON.parse(raw ?? 'null') as { token?: unknown } | null)?.token;
    return typeof token === 'string' && token ? token : null;
  } catch { return null; /* no ERP session: the API answers 401 */ }
}

/**
 * The workspace the ERP is signed into (shared `mizan.tenant`), so Studio names the real
 * workspace instead of a default. Pure: `raw` is the stored JSON. Falls back to `fallback`.
 */
export function ssoWorkspace(raw: string | null, fallback: string): { slug: string; label: string } {
  try {
    const t = JSON.parse(raw ?? 'null') as { slug?: unknown; name?: unknown } | null;
    const slug = typeof t?.slug === 'string' && t.slug ? t.slug : '';
    const name = typeof t?.name === 'string' && t.name.trim() ? t.name.trim().slice(0, 80) : '';
    if (slug || name) return { slug: slug || fallback, label: name || slug };
  } catch { /* no ERP workspace: keep the default */ }
  return { slug: fallback, label: fallback };
}

export function siteRequestHeaders(baseUrl: string, method: string, hasBody: boolean, cookies: string): Record<string, string> {
  const headers: Record<string, string> = hasBody ? { 'Content-Type': 'application/json' } : {};
  const sso = ssoToken(baseUrl, import.meta.env.VITE_STUDIO_API as string | undefined,
    typeof localStorage === 'undefined' ? null : localStorage.getItem('mizan.session'));
  if (sso) headers['Authorization'] = `Bearer ${sso}`;
  // Match the native workspace client's double-submit cookie protocol. Never forward
  // this readable cookie to a caller-supplied external API origin.
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && (baseUrl === '' || (baseUrl.startsWith('/') && !baseUrl.includes('//')))) {
    const csrf = cookies.split(';').map(part => part.trim()).find(part => part.startsWith('csrf_token='))?.slice('csrf_token='.length);
    if (csrf) { try { headers['X-CSRF-Token'] = decodeURIComponent(csrf); } catch { /* malformed cookie: server refuses write */ } }
  }
  return headers;
}

async function request<T>(fetchImpl: FetchLike, baseUrl: string, method: string, path: string, body?: unknown): Promise<T> {
  const headers = siteRequestHeaders(baseUrl, method, body !== undefined, typeof document === 'undefined' ? '' : document.cookie);
  const response = await fetchImpl(`${baseUrl}${path}`, {
    method,
    credentials: 'include',
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    let detail = '';
    try {
      const data: unknown = await response.json();
      if (data && typeof data === 'object' && typeof (data as { detail?: unknown }).detail === 'string') {
        detail = (data as { detail: string }).detail;
      }
    } catch { /* non-JSON error body: keep the generic message */ }
    throw new SiteApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

// The API accepts lowercase latin letters, digits and hyphens only (service.check_slug).
export function slugFromName(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80)
    .replace(/-+$/g, '');
  return slug || 'home';
}

export function createPayload(project: Project, slugOverride?: string): { slug: string; titles: Record<string, string>; tree: PageNode } {
  const requested = (slugOverride ?? '').trim();
  if (requested && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(requested)) {
    throw new Error('Use lowercase letters, numbers and single hyphens for the page address.');
  }
  return { slug: requested || slugFromName(project.name), titles: { [project.language]: project.name }, tree: toPageTree(project) };
}

export function draftPayload(project: Project): { tree: PageNode; titles: Record<string, string> } {
  return { tree: toPageTree(project), titles: { [project.language]: project.name } };
}

// Durable site settings (theme + chrome): one record per workspace, read back on load
// so theme choices survive a wiped browser. Same validation rules as the renderer.
export type SiteSettingsValue = {
  colors?: { light?: Record<string, string> };
  typography?: { family?: string };
  shape?: { radius?: number };
  header?: { layout?: 'inline'|'centered'; surface?: 'default'|'dark'; brand?: string; logo?: string; links?: { label: string; href: string }[]; actions?: { label: string; href: string }[]; search_enabled?: boolean; search_target?: string; search_placeholder?: string; search_style?: 'filled'|'outline'; bar_style?: 'pills'|'plain'; density?: 'comfortable'|'compact'; row_align?: 'start'|'center'|'end'|'between'|'around'|'evenly'; row_gap?: 'tight'|'wide'; gap_px?: number; tablet?: { density?: 'comfortable'|'compact'; hide_search?: boolean; hide_bar?: boolean }; mobile?: { density?: 'comfortable'|'compact'; hide_search?: boolean; hide_bar?: boolean }; element_order?: ('brand'|'search'|'icons')[]; icons?: { icon: 'whatsapp'|'cart'|'heart'|'user'|'phone'|'globe'|'search'; label: string; href: string }[]; bar_links?: { label: string; href: string }[]; bar_cta_label?: string; bar_cta_href?: string };
  footer?: { layout?: 'split'|'stacked'; lines?: string[]; links?: { label: string; href: string }[]; groups?: { title: string; links: { label: string; href: string }[] }[]; socials?: { icon: string; label: string; href: string }[] };
  /** Server-owned flag the editor does not edit but must round-trip untouched. */
  follow_workspace?: boolean;
};

export function settingsPayload(project: Project): SiteSettingsValue {
  return previewPayload(project, 'desktop').theme as SiteSettingsValue;
}

/** The settings GET/PUT payload: the stored doc plus read-only preview views - what
    visitors get (workspace base merged under stored settings) and the base alone. */
export type SiteSettingsResponse = { value: SiteSettingsValue; resolved?: SiteSettingsValue; base?: SiteSettingsValue; edit_token?: string };

/** Mirror of the server's _merge_site_settings: explicit site settings win over the
    workspace base, per token for colors and per key for the header. */
export function mergeSiteSettings(base: SiteSettingsValue | undefined, explicit: SiteSettingsValue | undefined): SiteSettingsValue {
  const b = base ?? {}, e = explicit ?? {};
  const out: SiteSettingsValue = { ...b };
  if (e.colors) out.colors = { light: { ...(b.colors?.light ?? {}), ...(e.colors.light ?? {}) } };
  if (e.typography) out.typography = e.typography;
  if (e.shape) out.shape = e.shape;
  if (e.header) out.header = { ...(b.header ?? {}), ...e.header };
  if (e.footer) out.footer = e.footer;
  return out;
}

const HEX = /^#[0-9a-fA-F]{6}$/;
const FONTS = new Set(['sans-serif', 'serif', 'monospace']);

// Applies a stored settings value onto a project, refusing anything invalid. Only the
// fields the studio owns: palette, typeface, radius, brand name.
export function applySettings(project: Project, value: SiteSettingsValue): Project {
  if (!value || typeof value !== 'object') return project;
  const next = structuredClone(project);
  const light = value.colors?.light;
  if (light) {
    if (typeof light.background === 'string' && HEX.test(light.background)) next.colors.background = light.background;
    if (typeof light.foreground === 'string' && HEX.test(light.foreground)) next.colors.foreground = light.foreground;
    if (typeof light.primary === 'string' && HEX.test(light.primary)) next.colors.accent = light.primary;
  }
  const family = value.typography?.family;
  if (typeof family === 'string' && FONTS.has(family)) next.font = family as Project['font'];
  const radius = value.shape?.radius;
  if (typeof radius === 'number' && Number.isInteger(radius) && radius >= 0 && radius <= 40) next.radius = radius;
  const links = value.header?.links, actions = value.header?.actions, lines = value.footer?.lines, footerLinks = value.footer?.links, logo = value.header?.logo, footerGroups = value.footer?.groups;
  if (links !== undefined || actions !== undefined || lines !== undefined || footerLinks !== undefined || logo !== undefined || footerGroups !== undefined) {
    const base = next.chrome ?? { links: [], actions: [], footer: [] };
    const chrome = { ...base };
    if (validChromeLinks(footerLinks, 8)) chrome.footerLinks = footerLinks.map(l => ({ label: l.label.trim(), href: l.href }));
    if (validChromeLinks(links, 8)) chrome.links = links.map(l => ({ label: l.label.trim(), href: l.href }));
    if (validChromeLinks(actions, 4)) chrome.actions = actions.map(l => ({ label: l.label.trim(), href: l.href }));
    if (Array.isArray(lines) && lines.length <= 4 && lines.every(x => typeof x === 'string' && x.trim() && x.length <= 120)) chrome.footer = lines.map(x => x.trim());
    if (typeof logo === 'string' && logo.trim() && logo.length <= 300 && safeNativeUrl(logo, true) && /^(\/|https:\/\/)/.test(logo)) chrome.logo = logo;
    if (validFooterGroups(footerGroups)) chrome.footerGroups = footerGroups.map(g => ({ title: g.title, links: g.links.map(l => ({ label: l.label, href: l.href })) }));
    next.chrome = chrome;
  }
  const brand = value.header?.brand;
  if (typeof brand === 'string' && brand.trim() && brand.length <= 100) next.name = brand.trim();
  return next;
}

export function createSitePagesClient(options: { baseUrl: string; fetchImpl?: FetchLike }) {
  const { baseUrl } = options;
  const fetchImpl = options.fetchImpl ?? fetch;
  const call = <T>(method: string, path: string, body?: unknown) => request<T>(fetchImpl, baseUrl, method, path, body);
  return {
    discoverData: () => call<{modules:unknown[];collections?:unknown[]}>('GET','/site/data'),
    previewData: (tree:PageNode,language:string,device:string) => call<{tree:PageNode;html:string}>('POST','/site/data/preview',{tree,language,device}),
    listPages: () => call<ListResponse<PageSummary>>('GET', '/site/pages'),
    createPage: (project: Project, slug?: string) => call<PageDetail>('POST', '/site/pages', createPayload(project, slug)),
    createNativePage: (payload: {slug:string;titles:Record<string,string>;tree:PageNode}) => call<PageDetail>('POST', '/site/pages', payload),
    getPage: (pageId: string) => call<PageDetail>('GET', `/site/pages/${pageId}`),
    saveTreeDraft: (pageId: string, tree: PageNode, expectedToken?: string, titles?:Record<string,string>) => call<PageDetail>('PUT', `/site/pages/${pageId}/draft`, { tree, ...(expectedToken?{expected_token:expectedToken}:{}),...(titles?{titles}:{}) }),
    saveDraft: (pageId: string, project: Project, titles?: Record<string, string>) => call<PageDetail>('PUT', `/site/pages/${pageId}/draft`, { ...draftPayload(project), ...(titles ? { titles } : {}) }),
    publish: (pageId: string) => call<PageDetail>('POST', `/site/pages/${pageId}/publish`),
    getPublicAccess: (pageId: string) => call<PublicAccess>('GET', `/site/pages/${pageId}/public-access`),
    setPublicAccess: (pageId: string, enabled: boolean) => call<PublicAccess>('PUT', `/site/pages/${pageId}/public-access`, { enabled }),
    setConnectedDataAccess: (pageId: string, enabled: boolean, audienceVersion: string) => call<PublicAccess>('PUT', `/site/pages/${pageId}/connected-data-access`, { enabled, audience_version: audienceVersion }),
    // Must mirror AUDIENCE_POLICY_CONNECTED in system/core/backend app/platform/site/service.py;
    // the writer refuses any other version so stale cached wording can never approve silently.
    connectedDataAudienceVersion: 'mizan.site-audience.connected-data.v1' as const,
    listRevisions: (pageId: string) => call<ListResponse<Revision>>('GET', `/site/pages/${pageId}/revisions`),
    rollback: (pageId: string, revisionId: string) => call<PageDetail>('POST', `/site/pages/${pageId}/rollback/${revisionId}`),
    getSettings: () => call<SiteSettingsResponse>('GET', '/site/settings'),
    saveSharedSettings: (value:SiteSettingsValue, expectedToken:string) => call<SiteSettingsResponse>('PUT','/site/settings',{value,expected_token:expectedToken}),
    putSettings: (project: Project) => call<{ value: SiteSettingsValue }>('PUT', '/site/settings', { value: settingsPayload(project) }),
    archive: (pageId: string) => call<PageSummary>('POST', `/site/pages/${pageId}/archive`),
    reopen: (pageId: string) => call<PageSummary>('POST', `/site/pages/${pageId}/reopen`),
  };
}
