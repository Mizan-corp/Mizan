import { describe, expect, it } from 'vitest';
import { fromPageTree } from './fromtree';
import { toPageTree } from './pagetree';
import { initialProject, moveSection, type Project } from './model';

function roundTrip(project: Project) {
  return fromPageTree(toPageTree(project), project);
}

describe('fromPageTree', () => {
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
