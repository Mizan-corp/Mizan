// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { createElement } from 'react';
import TreePreview, { accentHtml, sanitizeHtml, themeStyle } from './treerender';
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
    expect(html.match(/class="mz-section[ "]/g)!.length).toBe(1);
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
  it('passes dark surface tokens through and emits the dark role class', () => {
    const style = themeStyle({ colors: { light: { dark: '#101820', 'dark-foreground': '#F3EEE4', bogus: '#101820' } } } as never);
    const vars = style as Record<string, string>;
    expect(vars['--dark']).toBe('#101820');
    expect(vars['--dark-foreground']).toBe('#F3EEE4');
    expect(vars['--bogus']).toBeUndefined();
    const tree = { type: 'section', id: 's1', settings: { desktop: { background: 'dark' } },
      children: [{ type: 'text', id: 't1', content: { en: { html: '<p>hi</p>' } }, settings: {} }] } as never;
    const html = renderToStaticMarkup(createElement(TreePreview, { tree, lang: 'en', device: 'desktop' }));
    expect(html).toContain('mz-background-dark');
  });
  it('renders the check_list text variant with its class', () => {
    const tree = { type: 'section', id: 's1', settings: {},
      children: [{ type: 'text', id: 't1', content: { en: { html: '<ul><li>Diagnosis first</li></ul>' } },
        settings: { desktop: { variant: 'check_list' } } }] } as never;
    const html = renderToStaticMarkup(createElement(TreePreview, { tree, lang: 'en', device: 'desktop' }));
    expect(html).toContain('mz-text-check_list');
    expect(html).toContain('<li>Diagnosis first</li>');
  });
  it('renders a column background image with an optional scrim, mirroring render.py', () => {
    const tree = { type: 'section', id: 's1', settings: {},
      children: [{ type: 'columns', id: 'r1', content: {}, settings: {},
        children: [{ type: 'column', id: 'c1', content: {},
          settings: { desktop: { background_image: '/site_image/bench.webp', background_dim: 'soft' } },
          children: [{ type: 'heading', id: 'h1', content: { en: { text: 'Hi' } }, settings: {} }] }] }] } as never;
    const html = renderToStaticMarkup(createElement(TreePreview, { tree, lang: 'en', device: 'desktop' }));
    expect(html).toContain('mz-bg-image');
    expect(html).toContain('bench.webp');
    expect(html).toContain('linear-gradient(');
    const t = tree as unknown as { children: { children: object[] }[] };
    const bad = { ...t, children: [{ ...t.children[0], children: [{ ...(t.children[0].children[0] as object),
      settings: { desktop: { background_image: 'https://x.test/a).png' } } }] }] } as never;
    const badHtml = renderToStaticMarkup(createElement(TreePreview, { tree: bad, lang: 'en', device: 'desktop' }));
    expect(badHtml).not.toContain('mz-bg-image');
  });
  it('accents heading text with mark only, escaping all other markup', () => {
    expect(accentHtml('Good <mark>technology</mark>.')).toBe('Good <mark>technology</mark>.');
    expect(accentHtml('<script>x</script> plain')).toBe('&lt;script&gt;x&lt;/script&gt; plain');
    expect(accentHtml('<mark class=bad>no</mark>')).toBe('&lt;mark class=bad&gt;no&lt;/mark&gt;');
    expect(accentHtml('<mark><b>nested</b></mark>')).toContain('&lt;b&gt;');
    const tree = { type: 'section', id: 's1', settings: {},
      children: [{ type: 'heading', id: 'h1', content: { en: { text: 'Good <mark>technology</mark>.' } }, settings: {} }] } as never;
    const html = renderToStaticMarkup(createElement(TreePreview, { tree, lang: 'en', device: 'desktop' }));
    expect(html).toContain('<mark>technology</mark>');
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

describe('icon_list inline SVG rendering', () => {
  const iconTree = () => ({ id: 'n_iconroot000', type: 'section', settings: {}, content: {}, children: [
    { id: 'n_iconrow0000', type: 'columns', settings: { desktop: { columns: 1 } }, content: {}, children: [
      { id: 'n_iconcol0000', type: 'column', settings: {}, content: {}, children: [
        { id: 'n_iclist0002', type: 'icon_list', settings: {}, content: { en: { items: [
          { icon: 'Wrench', text: 'Repairs covered' },
          { icon: 'NoSuchGlyph', text: 'Unknown falls back' },
        ] } } },
      ] },
    ] },
  ] });
  const renderIcons = () => renderToStaticMarkup(createElement(TreePreview, { tree: iconTree() as never, lang: 'en', device: 'desktop', theme: previewPayload(initialProject, 'page-1').theme as never }));
  it('renders bounded inline SVGs, never data-lucide placeholders', () => {
    const html = renderIcons();
    expect(html).toContain('mz-icon-list');
    expect(html).not.toContain('data-lucide');
    expect(html.match(/class="mz-icon"/g)!.length).toBe(2);
    expect(html).toContain('Repairs covered');
    expect(html).toContain('<circle cx="12" cy="12" r="5"/>'); // fallback dot for the unknown name
  });
});

describe('content fallback for language-neutral refs', () => {
  // Mirrors render.py _content_ref: src/href fall back across languages only when
  // absent; explicit '' stays blank; labels never fall back, so an untranslated
  // button stays hidden.
  const theme = previewPayload(project, 'page-1').theme as never;
  function node(id: string, type: string, content: Record<string, Record<string, unknown>>) {
    return { id, type, content, settings: {}, children: [] } as never;
  }
  function renderNodes(nodes: unknown[], lang: string) {
    const tree = {
      id: 's1', type: 'section', content: {}, settings: {},
      children: [{ id: 'r1', type: 'columns', content: {}, settings: {},
        children: [{ id: 'c1', type: 'column', content: {}, settings: {}, children: nodes }] }],
    } as never;
    return renderToStaticMarkup(createElement(TreePreview, { tree, lang, device: 'desktop', theme }));
  }
  it('renders an image in Arabic from the English src when Arabic never set one', () => {
    const html = renderNodes([node('i1', 'image', { en: { src: '/studio-assets/tech-laptop.svg', alt: 'Laptop' }, ar: { alt: 'لابتوب' } })], 'ar');
    expect(html).toContain('tech-laptop.svg');
    expect(html).toContain('لابتوب');
  });
  it('keeps an explicitly blank Arabic src blank', () => {
    const html = renderNodes([node('i2', 'image', { en: { src: '/studio-assets/tech-laptop.svg' }, ar: { src: '' } })], 'ar');
    expect(html).not.toContain('mz-image');
  });
  it('renders a button in Arabic with a translated label and the fallback href', () => {
    const html = renderNodes([node('b1', 'button', { en: { href: '/x', label: 'Go' }, ar: { label: 'روح' } })], 'ar');
    expect(html).toContain('href="/x"');
    expect(html).toContain('روح');
  });
  it('hides a button with no active-language label', () => {
    const html = renderNodes([node('b2', 'button', { en: { href: '/x', label: 'Go' } })], 'ar');
    expect(html).not.toContain('mz-button');
  });
  it('hides a button whose active-language href is explicitly blank', () => {
    const html = renderNodes([node('b3', 'button', { en: { href: '/x', label: 'Go' }, ar: { label: 'روح', href: '' } })], 'ar');
    expect(html).not.toContain('mz-button');
  });
});

describe('Theme chrome logo and footer groups', () => {
  it('renders a safe header logo before the brand and drops unsafe values', () => {
    const safe = renderToStaticMarkup(createElement(TreePreview, { tree, lang: 'en', device: 'desktop', theme: { header: { brand: 'B', logo: 'https://cdn.example.com/logo.svg', links: [{ label: 'A', href: '/a' }] } } } as never));
    expect(safe).toContain('<img class="mz-site-logo" src="https://cdn.example.com/logo.svg"');
    const unsafe = renderToStaticMarkup(createElement(TreePreview, { tree, lang: 'en', device: 'desktop', theme: { header: { brand: 'B', logo: 'javascript:alert(1)' } } } as never));
    expect(unsafe).not.toContain('javascript:');
    expect(unsafe).not.toContain('mz-site-logo');
  });
  it('renders footer groups with titles and caps groups and links', () => {
    const groups = Array.from({ length: 5 }, (_, i) => ({ title: `G${i + 1}`, links: Array.from({ length: 7 }, (_, j) => ({ label: `L${j + 1}`, href: `/x${j}` })) }));
    const html = renderToStaticMarkup(createElement(TreePreview, { tree, lang: 'en', device: 'desktop', theme: { footer: { lines: ['Line'], groups } } } as never));
    expect(html).toContain('mz-footer-groups');
    expect(html).toContain('>G4<');
    expect(html).not.toContain('>G5<');
    expect((html.match(/mz-footer-group-title/g) || []).length).toBe(4);
    expect(html).toContain('>L6<');
    expect(html).not.toContain('>L7<');
  });
});

describe('form block (contact-form V1)', () => {
  const formTree = {
    id: 'n_root1', type: 'section', settings: { desktop: {} }, content: {},
    children: [{
      id: 'n_cols01', type: 'columns', settings: { desktop: {} }, content: {},
      children: [{
        id: 'n_col001', type: 'column', settings: {}, content: {},
        children: [{
          id: 'n_form01', type: 'form',
          settings: { desktop: { visible: true, field_name: true, field_phone: false } },
          content: { en: { title: 'Contact us', submit_label: 'Send' } },
        }],
      }],
    }],
  };
  function renderForm() {
    return renderToStaticMarkup(createElement(TreePreview, { tree: formTree as never, lang: 'en', device: 'desktop' }));
  }
  it('renders inert: no form element, disabled button, fields by toggle', () => {
    const html = renderForm();
    expect(html).not.toContain('<form');
    expect(html).toContain('mz-form-inert');
    expect(html).toContain('disabled');
    expect(html).toContain('Contact us');
    expect(html).toContain('>Name</label>');
    expect(html).not.toContain('>Phone</label>');
    expect(html).toContain('type="email"');
  });
});
