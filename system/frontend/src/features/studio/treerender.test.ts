// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';
import TreePreview, { sanitizeHtml, themeStyle } from './treerender';
import { toPageTree, previewPayload } from './pagetree';
import { initialProject } from './model';

const project = structuredClone(initialProject);
const tree = toPageTree(project);

function render(device: 'desktop' | 'tablet' | 'mobile', lang = project.language) {
  return renderToStaticMarkup(
    createElement(TreePreview, { tree, lang, device, theme: previewPayload(project, 'page-1').theme as never }),
  );
}

describe('TreePreview over toPageTree output', () => {
  it('wraps the page in one mz-section and every project section in a columns row', () => {
    // Registry shape: the root section may only contain columns/canvas rows, so each
    // project section maps to one mz-columns row under the single mz-section page wrapper.
    const html = render('desktop');
    expect(html.match(/class="mz-section"/g)!.length).toBe(1);
    expect(html.match(/mz-columns mz-columns-\d/g)!.length).toBe(project.sections.length);
  });
  it('keeps the two-column hero with the media column', () => {
    const p = structuredClone(initialProject);
    p.sections[0].image = 'https://images.northline.example/hero-1.jpg';
    p.sections[1].image = 'https://images.northline.example/story-1.jpg';
    const t = toPageTree(p);
    const html = renderToStaticMarkup(createElement(TreePreview, { tree: t, lang: p.language, device: 'desktop', theme: previewPayload(p, 'page-1').theme as never }));
    expect(html).toContain('mz-columns mz-columns-2');
    expect(html.match(/mz-image/g)!.length).toBe(2); // one art image per section
  });
  it('renders eyebrow and editorial-note variants', () => {
    const html = render('desktop');
    expect(html).toContain('mz-text-eyebrow');
    expect(html).toContain('mz-text-note');
    expect(html).toContain('01 / INTENTIONAL BY DESIGN');
  });
  it('renders theme header and footer chrome', () => {
    const html = render('desktop');
    expect(html).toContain('mz-site-header');
    expect(html).toContain('mz-site-brand');
    expect(html).toContain('Collections');
    expect(html).toContain('Bag (0)');
    expect(html).toContain('mz-site-footer');
    expect(html).toContain('Made to make it yours.');
  });
  it('applies theme typography and radius, refusing unknown families', () => {
    const project = { ...initialProject, font: 'serif' as const, radius: 4 };
    const theme = previewPayload(project, 'page-1').theme as never;
    const style = themeStyle(theme);
    expect(style['--radius' as keyof typeof style]).toBe('4px');
    expect(String((style as Record<string, string>).fontFamily)).toContain('Georgia');
    const bad = themeStyle({ typography: { family: 'evil' }, shape: { radius: 999 } } as never);
    expect((bad as Record<string, string>).fontFamily).toBeUndefined();
    expect((bad as Record<string, string>)['--radius']).toBeUndefined();
  });
  it('applies theme color tokens as css variables', () => {
    const html = render('desktop');
    expect(html).toContain('--background:');
  });
  it('honors per-device visibility', () => {
    const p = structuredClone(initialProject);
    p.sections[1].visible.mobile = false;
    const t = toPageTree(p);
    const html = renderToStaticMarkup(createElement(TreePreview, { tree: t, lang: p.language, device: 'mobile' }));
    expect(html).not.toContain(p.sections[1].title);
    const desktop = renderToStaticMarkup(createElement(TreePreview, { tree: t, lang: p.language, device: 'desktop' }));
    expect(desktop).toContain(p.sections[1].title);
  });
  it('keeps copy-first reading order on stacked devices even for reversed sections', () => {
    const html = render('mobile');
    // Section 2 is reversed on desktop, but stacked devices read copy first.
    expect(html.indexOf('Less noise.')).toBeLessThan(html.lastIndexOf('mz-art-sculpture-alt'));
  });
  it('stacks columns for mobile via mz-stack', () => {
    expect(render('mobile')).toContain('mz-stack');
  });
});

describe('sanitizeHtml', () => {
  it('strips script/style/svg with content', () => {
    expect(sanitizeHtml('<p>ok</p><script>alert(1)</script>')).toBe('<p>ok</p>');
  });
  it('strips disallowed tags but keeps inner text', () => {
    expect(sanitizeHtml('<marquee><b>hi</b></marquee>')).toBe('<b>hi</b>');
  });
  it('keeps only safe link schemes', () => {
    expect(sanitizeHtml('<a href="javascript:alert(1)">x</a>')).toBe('<a>x</a>');
    expect(sanitizeHtml('<a href="https://a.b/c">x</a>')).toBe('<a href="https://a.b/c">x</a>');
  });
});
