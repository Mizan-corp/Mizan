import { describe, expect, it } from 'vitest';
import { createMediaClient, isInUseError, registerMediaClient, mediaClient } from './mediaLibrary';
import { SiteApiError } from './sitePages';

function res(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

const item = { id: 'm1', url: '/uploads/t/abc/site_image/file-x.png', size: 10, content_type: 'image/png', created_at: null };

describe('media library client', () => {
  it('lists the workspace library', async () => {
    const calls: string[] = [];
    const api = createMediaClient({ baseUrl: '/__studio/api', fetchImpl: async (input) => { calls.push(String(input)); return res(200, { items: [item], total_bytes: 10 }); } });
    const out = await api.list();
    expect(out.items).toEqual([item]);
    expect(calls).toEqual(['/__studio/api/site/media']);
  });

  it('uploads as multipart with the CSRF echo, never a JSON content type', async () => {
    (globalThis as { document?: unknown }).document = { cookie: 'csrf_token=tok123' };
    let seen: { url: string; init?: RequestInit } | null = null;
    const api = createMediaClient({ baseUrl: '/__studio/api', fetchImpl: async (input, init) => { seen = { url: String(input), init }; return res(201, item); } });
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'x.png', { type: 'image/png' });
    const out = await api.upload(file);
    expect(out).toEqual(item);
    expect(seen!.url).toBe('/__studio/api/site/media');
    expect(seen!.init?.method).toBe('POST');
    expect(seen!.init?.body).toBeInstanceOf(FormData);
    const headers = seen!.init?.headers as Record<string, string>;
    expect(headers['X-CSRF-Token']).toBe('tok123');
    expect(headers['Content-Type']).toBeUndefined();
  });

  it('no CSRF header leaves the origin when baseUrl is external', async () => {
    (globalThis as { document?: unknown }).document = { cookie: 'csrf_token=tok123' };
    let seen: RequestInit | undefined;
    const api = createMediaClient({ baseUrl: 'https://evil.example/api', fetchImpl: async (_i, init) => { seen = init; return res(201, item); } });
    await api.upload(new File([new Uint8Array([1])], 'x.png', { type: 'image/png' }));
    expect((seen?.headers as Record<string, string>)['X-CSRF-Token']).toBeUndefined();
  });

  it('surfaces delete 409 as an in-use conflict', async () => {
    const api = createMediaClient({ baseUrl: '/__studio/api', fetchImpl: async () => res(409, { detail: 'in use' }) });
    const err = await api.remove('m1').catch(e => e);
    expect(err).toBeInstanceOf(SiteApiError);
    expect(isInUseError(err)).toBe(true);
  });

  it('registry hands the registered client to nested controls', () => {
    const api = createMediaClient({ baseUrl: '/x', fetchImpl: async () => res(200, { items: [] }) });
    registerMediaClient(api);
    expect(mediaClient()).toBe(api);
    registerMediaClient(null);
    expect(mediaClient()).toBeNull();
  });
});
