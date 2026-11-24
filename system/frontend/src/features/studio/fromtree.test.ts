import { describe, expect, it } from 'vitest';
import { fromPageTree } from './fromtree';
import { toPageTree } from './pagetree';
import { initialProject, moveSection, type Project } from './model';

function roundTrip(project: Project) {
  return fromPageTree(toPageTree(project), project);
}

describe('fromPageTree', () => {
  it('refuses a custom button destination but accepts and upgrades the legacy #preview constant', () => {
    const tree = toPageTree(initialProject);
    const rows = tree.children!;
    const buttonOf = (row: (typeof rows)[number]) => {
      const copy = row.children![0];
      return copy.children!.find(c => c.type === 'button')!;
    };
    const custom = structuredClone(tree);
    (buttonOf(custom.children![0]).content.en as { href: string }).href = 'https://example.com/elsewhere';
    expect(() => fromPageTree(custom, initialProject)).toThrow('custom button destination');

    const legacy = structuredClone(tree);
    for (const row of legacy.children!) (buttonOf(row).content.en as { href: string }).href = '#preview';
    const restored = fromPageTree(legacy, initialProject);
    expect(restored.sections).toHaveLength(initialProject.sections.length);
    // The next save rewrites the href to the generated anchor form.
    const regenerated = toPageTree({ ...initialProject, sections: restored.sections });
    expect((regenerated.children![0].children![0].children!.find(c => c.type === 'button')!.content.en as { href: string }).href).toBe(`#${regenerated.children![1].id}`);
  });

  it('round-trips the initial project (section content, order, flags)', () => {
    const restored = roundTrip(initialProject);
    expect(restored.sections).toHaveLength(initialProject.sections.length);
    for (let i = 0; i < restored.sections.length; i++) {
      const a = initialProject.sections[i];
      const b = restored.sections[i];
      expect(b.eyebrow).toBe(a.eyebrow);
      expect(b.title).toBe(a.title);
      expect(b.description).toBe(a.description);
      expect(b.button).toBe(a.button);
      expect(b.image).toBe(a.image);
      expect(b.visible).toEqual(a.visible);
      // The media column is durable (registered art when imageless), so the
      // reversed flag survives the round-trip for every section.
      expect(b.reversed).toBe(a.reversed);
    }
  });

  it('round-trips edited, reordered, hidden and imaged sections', () => {
    let p: Project = structuredClone(initialProject);
    p = moveSection(p, p.sections[0].id, 1);
    p = { ...p, sections: p.sections.map((s, i) => ({ ...s,
      title: i === 0 ? 'Edited & <saved> "heading"' : s.title,
      image: i === 0 ? 'https://cdn.example.com/a.png' : '',
      visible: { desktop: true, tablet: i !== 0, mobile: true },
    })) };
    const restored = roundTrip(p);
    expect(restored.sections[0].title).toBe('Edited & <saved> "heading"');
    expect(restored.sections[0].image).toBe('https://cdn.example.com/a.png');
    expect(restored.sections[0].visible.tablet).toBe(false);
    expect(restored.sections[0].reversed).toBe(true);
    expect(restored.sections.map(s => s.eyebrow)).toEqual(p.sections.map(s => s.eyebrow));
  });

  it('keeps project-level fields from the base project', () => {
    const p: Project = { ...initialProject, name: 'متجر شمال', language: 'ar', radius: 12 };
    const restored = roundTrip(p);
    expect(restored.name).toBe('متجر شمال');
    expect(restored.language).toBe('ar');
    expect(restored.radius).toBe(12);
  });

  it('refuses trees it cannot edit faithfully (fail closed)', () => {
    expect(() => fromPageTree({ id: 'x', type: 'gallery', settings: {}, content: {} }, initialProject)).toThrow();
    const tree = toPageTree(initialProject);
    const foreign = structuredClone(tree);
    foreign.children![0].children![0].children!.push({ id: 'n_x', type: 'video', settings: {}, content: {} });
    expect(() => fromPageTree(foreign, initialProject)).toThrow();
    const noHeading = structuredClone(tree);
    noHeading.children![0].children![0].children = noHeading.children![0].children![0].children!.filter(c => c.type !== 'heading');
    expect(() => fromPageTree(noHeading, initialProject)).toThrow();
  });
});

it('preserves literal entity-looking plain heading and button text', () => {
  const p = structuredClone(initialProject);
  p.sections[0].title = 'Literal &amp; and &lt;text&gt;';
  p.sections[0].button = 'Buy &amp; keep';
  expect(roundTrip(p).sections[0].title).toBe(p.sections[0].title);
  expect(roundTrip(p).sections[0].button).toBe(p.sections[0].button);
});

it('rejects all values the narrow editor would drop, without changing input', () => {
  const mutations = [
    (t: ReturnType<typeof toPageTree>) => { t.settings.desktop.padding = 's'; },
    (t: ReturnType<typeof toPageTree>) => { const c=t.children![0].children![0].children!; c.push(structuredClone(c[0])); },
    (t: ReturnType<typeof toPageTree>) => { t.children![0].children![0].children![3].content.en.href = '/real-checkout'; },
    (t: ReturnType<typeof toPageTree>) => { t.children![0].children![0].children![1].content.ar = {text:'ترجمة'}; },
    (t: ReturnType<typeof toPageTree>) => { t.children![0].children![1].children![0].content.en.alt = 'Meaningful alt'; },
    (t: ReturnType<typeof toPageTree>) => { t.children![0].children![0].children![2].content.en.html = '<p><strong>Keep markup</strong></p>'; },
    (t: ReturnType<typeof toPageTree>) => { t.children![0].settings.mobile.gap = 's'; },
  ];
  for (const mutate of mutations) {
    const tree = toPageTree(initialProject); mutate(tree);
    const before = JSON.stringify(tree);
    expect(() => fromPageTree(tree, initialProject)).toThrow();
    expect(JSON.stringify(tree)).toBe(before);
  }
});
