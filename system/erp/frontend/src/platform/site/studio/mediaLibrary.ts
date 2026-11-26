import { SiteApiError, siteRequestHeaders } from './sitePages';

export type MediaItem = { id: string; url: string; size: number; content_type: string | null; name: string | null; created_at: string | null };
export type MediaList = { items: MediaItem[]; total_bytes: number };
type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

async function errorDetail(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === 'object' && typeof (data as { detail?: unknown }).detail === 'string') {
      return (data as { detail: string }).detail;
    }
  } catch { /* non-JSON body: generic message */ }
  return '';
}

/** Client for the site media library (/site/media). Same-origin workspace API with the
 * double-submit CSRF cookie echoed on writes, exactly like the pages client. */
export function createMediaClient(options: { baseUrl: string; fetchImpl?: FetchLike }) {
  const { baseUrl } = options;
  const fetchImpl = options.fetchImpl ?? fetch;
  const cookies = () => (typeof document === 'undefined' ? '' : document.cookie);
  return {
    async list(): Promise<MediaList> {
      const res = await fetchImpl(`${baseUrl}/site/media`, { credentials: 'include' });
      if (!res.ok) throw new SiteApiError(res.status, await errorDetail(res));
      return res.json() as Promise<MediaList>;
    },
    async upload(file: File): Promise<MediaItem> {
      const body = new FormData();
      body.append('file', file);
      // multipart: the browser sets the boundary Content-Type; the CSRF echo still applies.
      const headers = siteRequestHeaders(baseUrl, 'POST', false, cookies());
      const res = await fetchImpl(`${baseUrl}/site/media`, { method: 'POST', credentials: 'include', headers, body });
      if (!res.ok) throw new SiteApiError(res.status, await errorDetail(res));
      return res.json() as Promise<MediaItem>;
    },
    async remove(id: string): Promise<void> {
      const headers = siteRequestHeaders(baseUrl, 'DELETE', false, cookies());
      const res = await fetchImpl(`${baseUrl}/site/media/${id}`, { method: 'DELETE', credentials: 'include', headers });
      if (!res.ok) throw new SiteApiError(res.status, await errorDetail(res));
    },
  };
}

export type MediaClient = ReturnType<typeof createMediaClient>;

// The picker lives deep in the controls tree; the studio registers its client once
// instead of threading it through every layer.
let current: MediaClient | null = null;
export function registerMediaClient(client: MediaClient | null): void { current = client; }
export function mediaClient(): MediaClient | null { return current; }

/** A 409 from delete means the image is still used in a page tree. */
export function isInUseError(error: unknown): boolean {
  return error instanceof SiteApiError && error.isConflict;
}
