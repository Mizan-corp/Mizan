import { describe, expect, it } from 'vitest';
import { ssoToken, siteRequestHeaders, SiteApiError, applySettings, createPayload, createSitePagesClient, draftPayload, settingsPayload, slugFromName } from './sitePages';
import { initialProject } from './model';
import { toPageTree } from './pagetree';

type Call = { input: string; init?: RequestInit };

function mockFetch(status: number, body: unknown) {
  const calls: Call[] = [];
  const fetchImpl = (input: string, init?: RequestInit) => {
    calls.push({ input, init });
    return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
  };
  return { calls, fetchImpl };
}

const okList = { items: [{ id: 'p1', slug: 'home', titles: { ar: 'الرئيسية' }, status: 'draft', has_draft: true, published: false, created_at: null, updated_at: null }] };

describe('site pages storage client', () => {
  it('lists pages with the session cookie', async () => {
    const { calls, fetchImpl } = mockFetch(200, okList);
    const client = createSitePagesClient({ baseUrl: 'https://erp.example', fetchImpl });
    const result = await client.listPages();
    expect(calls).toHaveLength(1);
    expect(calls[0].input).toBe('https://erp.example/site/pages');
    expect(calls[0].init?.method).toBe('GET');
    expect(calls[0].init?.credentials).toBe('include');
    expect(result.items[0].slug).toBe('home');
  });

  it('creates a page from a studio project with a page-tree body', async () => {
    const { calls, fetchImpl } = mockFetch(201, {});
    const client = createSitePagesClient({ baseUrl: '', fetchImpl });
    await client.createPage(initialProject);
    const body = JSON.parse(String(calls[0].init?.body));
    expect(calls[0].input).toBe('/site/pages');
    expect(calls[0].init?.method).toBe('POST');
    expect(body.slug).toBe('northline-studio');
    expect(body.titles).toEqual({ en: initialProject.name });
    expect(body.tree).toEqual(toPageTree(initialProject));
    expect(body.tree.id).toBe('n_root01');
  });

  it('saves a draft with tree and titles', async () => {
    const { calls, fetchImpl } = mockFetch(200, {});
    const client = createSitePagesClient({ baseUrl: '', fetchImpl });
    await client.saveDraft('p1', initialProject);
    expect(calls[0].input).toBe('/site/pages/p1/draft');
    expect(calls[0].init?.method).toBe('PUT');
    const body = JSON.parse(String(calls[0].init?.body));
    expect(body.tree).toEqual(toPageTree(initialProject));
    expect(body.titles).toEqual({ en: initialProject.name });
  });

  it('posts publish, archive, reopen and rollback with no body', async () => {
    const { calls, fetchImpl } = mockFetch(200, {});
    const client = createSitePagesClient({ baseUrl: '', fetchImpl });
    await client.publish('p1');
    await client.archive('p1');
    await client.reopen('p1');
    await client.rollback('p1', 'r2');
    expect(calls.map(c => c.input)).toEqual([
      '/site/pages/p1/publish', '/site/pages/p1/archive', '/site/pages/p1/reopen', '/site/pages/p1/rollback/r2',
    ]);
    for (const call of calls) {
      expect(call.init?.method).toBe('POST');
      expect(call.init?.body).toBeUndefined();
    }
  });

  it('maps revisions list', async () => {
    const { fetchImpl } = mockFetch(200, { items: [{ id: 'r1', number: 2, titles: {}, created_by: null, created_at: null }] });
    const client = createSitePagesClient({ baseUrl: '', fetchImpl });
    const result = await client.listRevisions('p1');
    expect(result.items[0].number).toBe(2);
  });

  it('classifies API errors', async () => {
    for (const [status, check] of [[401, 'isAuth'], [403, 'isForbidden'], [404, 'isNotFound'], [409, 'isConflict'], [422, 'isInvalid']] as const) {
      const { fetchImpl } = mockFetch(status, { detail: 'رسالة' });
      const client = createSitePagesClient({ baseUrl: '', fetchImpl });
      const error = await client.listPages().catch((e: unknown) => e);
      expect(error).toBeInstanceOf(SiteApiError);
      expect((error as SiteApiError)[check]).toBe(true);
      expect((error as SiteApiError).detail).toBe('رسالة');
    }
  });

  it('survives a non-JSON error body', async () => {
    const fetchImpl = () => Promise.resolve(new Response('oops', { status: 500 }));
    const client = createSitePagesClient({ baseUrl: '', fetchImpl });
    const error = await client.listPages().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SiteApiError);
    expect((error as SiteApiError).status).toBe(500);
  });
});

describe('slugFromName', () => {
  it('keeps latin names as kebab slugs', () => {
    expect(slugFromName('Northline studio')).toBe('northline-studio');
    expect(slugFromName('  My  Store!! ')).toBe('my-store');
  });
  it('falls back to home for names without latin letters', () => {
    expect(slugFromName('متجري')).toBe('home');
    expect(slugFromName('---')).toBe('home');
  });
  it('stays within the 80 character API limit', () => {
    const slug = slugFromName('a'.repeat(120));
    expect(slug.length).toBeLessThanOrEqual(80);
    expect(slugFromName(`${'b'.repeat(78)}--`)).toHaveLength(78);
  });
});

describe('payload mapping', () => {
  it('uses the project language for titles', () => {
    const arabic = { ...initialProject, language: 'ar' as const, name: 'متجر شمال' };
    expect(createPayload(arabic).titles).toEqual({ ar: 'متجر شمال' });
    expect(createPayload(arabic).slug).toBe('home');
    expect(draftPayload(arabic).titles).toEqual({ ar: 'متجر شمال' });
  });
});


describe('site settings client + mapping', () => {
  it('sends the project theme as the settings value and reads it back', async () => {
    const { calls, fetchImpl } = mockFetch(200, { value: settingsPayload(initialProject) });
    const client = createSitePagesClient({ baseUrl: 'https://erp.example', fetchImpl });
    await client.putSettings(initialProject);
    expect(calls[0].input).toBe('https://erp.example/site/settings');
    expect(calls[0].init?.method).toBe('PUT');
    const sent = JSON.parse(String(calls[0].init?.body));
    expect(sent.value.typography.family).toBe(initialProject.font);
    expect(sent.value.shape.radius).toBe(initialProject.radius);
    expect(sent.value.colors.light.primary).toBe(initialProject.colors.accent);
    const read = await client.getSettings();
    expect(read.value.shape?.radius).toBe(initialProject.radius);
  });

  it('applySettings restores palette, font, radius and brand, refusing invalid values', () => {
    const base = structuredClone(initialProject);
    const applied = applySettings(base, {
      colors: { light: { background: '#111111', foreground: '#222222', primary: '#333333', 'primary-foreground': '#444444', bogus: '#555555' } },
      typography: { family: 'serif' },
      shape: { radius: 4 },
      header: { brand: 'Restored brand' },
    });
    expect(applied.colors).toEqual({ background: '#111111', foreground: '#222222', accent: '#333333' });
    expect(applied.font).toBe('serif');
    expect(applied.radius).toBe(4);
    expect(applied.name).toBe('Restored brand');
    const refused = applySettings(base, {
      colors: { light: { background: 'red' } },
      typography: { family: 'evil' },
      shape: { radius: 999 },
      header: { brand: '' },
    });
    expect(refused).toEqual(base);
  });

  it('round-trips custom header links, actions and footer lines', () => {
    const custom = structuredClone(initialProject);
    custom.chrome = { links: [{ label: 'Shop', href: '/shop' }], actions: [{ label: 'Account', href: '#account' }], footer: ['Custom footer', 'Second line'] };
    const value = settingsPayload(custom);
    expect(value.header?.links).toEqual([{ label: 'Shop', href: '/shop' }]);
    expect(value.footer?.lines).toEqual(['Custom footer', 'Second line']);
    const restored = applySettings(structuredClone(initialProject), value);
    expect(restored.chrome).toEqual(custom.chrome);
    const bad = applySettings(structuredClone(initialProject), { header: { links: [{ label: 'x', href: 'javascript:alert(1)' }] }, footer: { lines: ['', 'ok'] } });
    expect(bad.chrome?.links).toEqual([]);
    expect(bad.chrome?.footer).toEqual([]);
  });
});


describe('site-wide settings across distinct page trees', () => {
  it('applies the same stored chrome to two pages without changing their content', () => {
    const home = structuredClone(initialProject);
    const about = structuredClone(initialProject);
    about.sections[0].title = 'Our separate about page';
    const theme = structuredClone(initialProject);
    theme.chrome = { links: [{ label: 'About', href: '/about' }], actions: [], footer: ['Shared footer'], footerLinks: [{ label: 'Returns', href: '/returns' }] };
    const stored = settingsPayload(theme);
    const restoredHome = applySettings(home, stored);
    const restoredAbout = applySettings(about, stored);
    expect(restoredHome.chrome).toEqual(restoredAbout.chrome);
    expect(restoredHome.chrome?.footerLinks).toEqual([{ label: 'Returns', href: '/returns' }]);
    expect(restoredHome.sections).toEqual(home.sections);
    expect(restoredAbout.sections).toEqual(about.sections);
    restoredHome.chrome!.footerLinks![0].label = 'Changed locally';
    expect(restoredAbout.chrome?.footerLinks?.[0].label).toBe('Returns');
    expect(stored.footer?.links?.[0].label).toBe('Returns');
  });
  it('clears footer links explicitly and leaves older saved projects compatible', () => {
    const base = structuredClone(initialProject);
    base.chrome = { links: [], actions: [], footer: [], footerLinks: [{ label: 'Contact', href: '/contact' }] };
    expect(applySettings(base, { footer: { links: [] } }).chrome?.footerLinks).toEqual([]);
    expect(applySettings(base, { footer: { links: [{ label: 'Bad', href: 'javascript:alert(1)' }] } }).chrome?.footerLinks).toEqual(base.chrome.footerLinks);
    expect(settingsPayload(initialProject).footer?.links).toBeUndefined();
  });
});

it('preserves an existing page title independently of the global brand on draft save', async () => {
  const {calls,fetchImpl} = mockFetch(200,{});
  const client = createSitePagesClient({baseUrl:'',fetchImpl});
  await client.saveDraft('stable-page-id', {...initialProject,name:'Changed global brand'}, {en:'Original page title'});
  expect(calls[0].input).toBe('/site/pages/stable-page-id/draft');
  expect(JSON.parse(String(calls[0].init?.body)).titles).toEqual({en:'Original page title'});
});

it('native tree save sends the original tree only, without titles or global settings', async () => {
  const {calls,fetchImpl}=mockFetch(200,{});
  const client=createSitePagesClient({baseUrl:'',fetchImpl});
  const tree=toPageTree(initialProject);
  await client.saveTreeDraft('native-original',tree);
  expect(calls).toHaveLength(1);
  expect(calls[0].input).toBe('/site/pages/native-original/draft');
  expect(JSON.parse(String(calls[0].init?.body))).toEqual({tree});
});

it('native concurrency save sends expected token without titles or settings',async()=>{
 const {calls,fetchImpl}=mockFetch(200,{});const client=createSitePagesClient({baseUrl:'',fetchImpl});const tree=toPageTree(initialProject);
 await client.saveTreeDraft('native-original',tree,'a'.repeat(64));
 expect(JSON.parse(String(calls[0].init?.body))).toEqual({tree,expected_token:'a'.repeat(64)});
});


describe('native cookie CSRF protocol', () => {
 it('echoes the token on same-origin mutations, including bodyless publish', () => {
  for(const method of ['POST','PUT','PATCH','DELETE']) expect(siteRequestHeaders('/api',method,false,'other=x; csrf_token=a%2Bb')).toEqual({'X-CSRF-Token':'a+b'});
 });
 it('never leaks readable cookies to external or protocol-relative destinations', () => {
  for(const base of ['https://api.example','//api.example','/a//b']) expect(siteRequestHeaders(base,'PUT',true,'csrf_token=private')).toEqual({'Content-Type':'application/json'});
 });
 it('does not echo on reads or fail on malformed/missing cookie data', () => {
  expect(siteRequestHeaders('/api','GET',false,'csrf_token=x')).toEqual({});
  expect(siteRequestHeaders('/api','POST',false,'csrf_token=%QQ')).toEqual({});
  expect(siteRequestHeaders('/api','POST',false,'other=x')).toEqual({});
 });
});

describe('studio single sign-on token', () => {
  const HOST = 'https://api.allmizan.live/api';
  const raw = JSON.stringify({ token: 'abc.def', user: { id: 1 } });
  it('returns the ERP session token only for the configured production API', () => {
    expect(ssoToken(HOST, HOST, raw)).toBe('abc.def');
    expect(ssoToken('/api', HOST, raw)).toBeNull();
    expect(ssoToken('https://evil.test/api', HOST, raw)).toBeNull();
    expect(ssoToken(HOST, undefined, raw)).toBeNull();
  });
  it('is quiet without an ERP session or with a broken one', () => {
    for (const bad of [null, '', 'not json', '{}', '{"token":""}', '{"token":5}', 'null']) expect(ssoToken(HOST, HOST, bad)).toBeNull();
  });
});
