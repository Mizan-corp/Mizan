import { describe, expect, it } from 'vitest';
import { fromPageTree } from './fromtree';
import { toPageTree } from './pagetree';
import { initialProject, moveSection, validateProject, type Project } from './model';

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

describe('feature-cards sections', () => {
  const featuresProject: Project = {
    ...initialProject,
    sections: [
      initialProject.sections[0],
      { id: 'features-1', eyebrow: 'WHY US', title: 'Made for real life', description: 'Three reasons.', button: '', image: '', visible: { desktop: true, tablet: true, mobile: true }, reversed: false, kind: 'features', cards: [
        { title: 'Fast delivery', text: 'Two days in Cairo.' },
        { title: 'Fair prices', text: 'No hidden fees.' },
        { title: 'Easy returns', text: 'Thirty days.' },
      ] },
    ],
  };

  it('round-trips a feature-cards section (lead copy plus every card)', () => {
    const restored = roundTrip(featuresProject);
    const section = restored.sections[1];
    expect(section.kind).toBe('features');
    expect(section.eyebrow).toBe('WHY US');
    expect(section.title).toBe('Made for real life');
    expect(section.description).toBe('Three reasons.');
    expect(section.cards).toEqual(featuresProject.sections[1].cards);
    expect(section.button).toBe('');
    expect(section.image).toBe('');
  });

  it('emits one lead column plus one column per card with level-3 headings', () => {
    const tree = toPageTree(featuresProject);
    const row = tree.children![1];
    expect(row.settings.desktop?.columns).toBe(4);
    expect(row.children).toHaveLength(4);
    expect(row.children![0].children!.some(c => c.type === 'button')).toBe(false);
    for (const card of row.children!.slice(1)) {
      expect(card.children!.map(c => c.type)).toEqual(['heading', 'text']);
      expect(card.children![0].settings.desktop?.level).toBe(3);
    }
  });

  it('refuses a features row without card columns, and validateProject rejects bad card counts', () => {
    const leadOnly = toPageTree(featuresProject);
    leadOnly.children![1].children = leadOnly.children![1].children!.slice(0, 1);
    expect(() => fromPageTree(leadOnly, featuresProject)).toThrow();
    expect(validateProject({ ...featuresProject, sections: [{ ...featuresProject.sections[1], cards: [] }] })).toBe(false);
    expect(validateProject({ ...featuresProject, sections: [{ ...featuresProject.sections[1], cards: [...featuresProject.sections[1].cards!, { title: 'A', text: 'b' }, { title: 'C', text: 'd' }] }] })).toBe(false);
  });

  it('keeps refusing trees the simple editor cannot preserve (extra card block)', () => {
    const tree = toPageTree(featuresProject);
    const card = tree.children![1].children![2];
    card.children!.push({ id: 'x', type: 'image', settings: {}, content: { en: { src: '', alt: '' } } });
    expect(() => fromPageTree(tree, featuresProject)).toThrow();
  });
});

describe('gallery sections', () => {
  const galleryProject: Project = {
    ...initialProject,
    sections: [
      initialProject.sections[0],
      { id: 'gallery-1', eyebrow: 'IN THE ROOM', title: 'Every angle', description: 'Shot in natural light.', button: '', image: '', visible: { desktop: true, tablet: true, mobile: true }, reversed: false, kind: 'gallery', images: [
        { src: 'https://images.example.test/one.jpg', alt: 'Chair in a room' },
        { src: 'https://images.example.test/two.jpg', alt: 'Table detail' },
      ] },
    ],
  };

  it('round-trips a gallery section (lead copy plus every image with alt text)', () => {
    const restored = roundTrip(galleryProject);
    const section = restored.sections[1];
    expect(section.kind).toBe('gallery');
    expect(section.title).toBe('Every angle');
    expect(section.images).toEqual(galleryProject.sections[1].images);
    expect(section.button).toBe('');
    expect(section.image).toBe('');
  });

  it('emits one full-width column whose gallery block carries grid mode', () => {
    const tree = toPageTree(galleryProject);
    const row = tree.children![1];
    expect(row.settings.desktop?.columns).toBe(1);
    expect(row.children).toHaveLength(1);
    const gallery = row.children![0].children!.find(c => c.type === 'gallery');
    expect(gallery?.settings.desktop?.mode).toBe('grid');
    expect((gallery?.content.en as { images: unknown[] }).images).toHaveLength(2);
  });

  it('drops empty-src rows from the emitted tree but keeps the section valid', () => {
    const withEmpty: Project = { ...galleryProject, sections: [galleryProject.sections[0], { ...galleryProject.sections[1], images: [{ src: '', alt: 'unfinished' }, ...galleryProject.sections[1].images!] }] };
    expect(validateProject(withEmpty)).toBe(true);
    const restored = roundTrip(withEmpty);
    expect(restored.sections[1].images).toEqual(galleryProject.sections[1].images);
  });

  it('refuses a gallery block with non-string image fields, and validateProject rejects unsafe sources', () => {
    const tree = toPageTree(galleryProject);
    const gallery = tree.children![1].children![0].children!.find(c => c.type === 'gallery')!;
    (gallery.content.en as { images: unknown[] }).images = [{ src: 42, alt: 'x' }];
    expect(() => fromPageTree(tree, galleryProject)).toThrow();
    expect(validateProject({ ...galleryProject, sections: [{ ...galleryProject.sections[1], images: [{ src: 'http://insecure.example/x.jpg', alt: '' }] }] })).toBe(false);
    expect(validateProject({ ...galleryProject, sections: [{ ...galleryProject.sections[1], images: Array.from({ length: 9 }, () => ({ src: 'https://images.example.test/x.jpg', alt: '' })) }] })).toBe(false);
  });
});

describe('layout switching', () => {
  it('keeps copy fields and per-kind data when a section changes layout and back', () => {
    const split = initialProject.sections[0];
    const asFeatures = { ...split, kind: 'features' as const, cards: [{ title: 'One', text: 'Two' }] };
    const asGallery = { ...asFeatures, kind: 'gallery' as const, images: [{ src: 'https://images.example.test/a.jpg', alt: 'a' }] };
    const backToFeatures = { ...asGallery, kind: 'features' as const };
    expect(backToFeatures.cards).toEqual(asFeatures.cards);
    expect(backToFeatures.images).toEqual(asGallery.images);
    expect(backToFeatures.title).toBe(split.title);
    expect(validateProject({ ...initialProject, sections: [backToFeatures] })).toBe(true);
    const restored = roundTrip({ ...initialProject, sections: [backToFeatures, initialProject.sections[1]] });
    expect(restored.sections[0].kind).toBe('features');
  });
});
