// Storage client for the site pages API (feat/s2-page-storage, ADR-015 S2/S3).
// Talks to the workspace backend's /site/pages routes with the session cookie, like
// the rest of the ERP frontend. This is the studio's only path to persisted pages;
// the local Project model stays the editing model and is converted with toPageTree.
import { previewPayload, toPageTree, type PageNode } from './pagetree';
import { validChromeLinks, type Project } from './model';

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

export type PublicAccess = { enabled: boolean; host: string | null; url: string | null };
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

export function siteRequestHeaders(baseUrl: string, method: string, hasBody: boolean, cookies: string): Record<string, string> {
  const headers: Record<string, string> = hasBody ? { 'Content-Type': 'application/json' } : {};
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
  header?: { layout?: 'inline'|'centered'; brand?: string; links?: { label: string; href: string }[]; actions?: { label: string; href: string }[] };
  footer?: { layout?: 'split'|'stacked'; lines?: string[]; links?: { label: string; href: string }[] };
};

export function settingsPayload(project: Project): SiteSettingsValue {
  return previewPayload(project, 'desktop').theme as SiteSettingsValue;
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
  const links = value.header?.links, actions = value.header?.actions, lines = value.footer?.lines, footerLinks = value.footer?.links;
  if (links !== undefined || actions !== undefined || lines !== undefined || footerLinks !== undefined) {
    const base = next.chrome ?? { links: [], actions: [], footer: [] };
    const chrome = { ...base };
    if (validChromeLinks(footerLinks, 8)) chrome.footerLinks = footerLinks.map(l => ({ label: l.label.trim(), href: l.href }));
    if (validChromeLinks(links, 8)) chrome.links = links.map(l => ({ label: l.label.trim(), href: l.href }));
    if (validChromeLinks(actions, 4)) chrome.actions = actions.map(l => ({ label: l.label.trim(), href: l.href }));
    if (Array.isArray(lines) && lines.length <= 4 && lines.every(x => typeof x === 'string' && x.trim() && x.length <= 120)) chrome.footer = lines.map(x => x.trim());
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
    listRevisions: (pageId: string) => call<ListResponse<Revision>>('GET', `/site/pages/${pageId}/revisions`),
    rollback: (pageId: string, revisionId: string) => call<PageDetail>('POST', `/site/pages/${pageId}/rollback/${revisionId}`),
    getSettings: () => call<{ value: SiteSettingsValue; edit_token?:string }>('GET', '/site/settings'),
    saveSharedSettings: (value:SiteSettingsValue, expectedToken:string) => call<{value:SiteSettingsValue;edit_token:string}>('PUT','/site/settings',{value,expected_token:expectedToken}),
    putSettings: (project: Project) => call<{ value: SiteSettingsValue }>('PUT', '/site/settings', { value: settingsPayload(project) }),
    archive: (pageId: string) => call<PageSummary>('POST', `/site/pages/${pageId}/archive`),
    reopen: (pageId: string) => call<PageSummary>('POST', `/site/pages/${pageId}/reopen`),
  };
}
