import { describe, expect, it } from 'vitest';
import { restoreEditablePage } from './editSession';
import { initialProject } from './model';
import { toPageTree } from './pagetree';
import type { PageDetail } from './sitePages';
const page = (): PageDetail => ({ id: 'p1', slug: 'home', titles: { en: initialProject.name }, status: 'draft', has_draft: true, published: false, created_at: null, updated_at: null, draft_tree: toPageTree(initialProject), published_tree: null });
describe('safe backend editing target', () => {
  it('accepts a supported draft and a blank draft', () => {
    expect(restoreEditablePage(page(), initialProject).writable).toBe(true);
    expect(restoreEditablePage({ ...page(), draft_tree: null }, initialProject).writable).toBe(true);
  });
  it('blocks unsupported draft even when published tree is supported, without mutating source', () => {
    const original = page();
    original.published_tree = toPageTree(initialProject);
    original.draft_tree!.children![0].children![0].children!.push({ id: 'n_extra', type: 'video', settings: {}, content: {} });
    const before = JSON.stringify(original);
    const restored = restoreEditablePage(original, initialProject);
    expect(restored.writable).toBe(false);
    expect('project' in restored).toBe(false);
    expect(JSON.stringify(original)).toBe(before);
  });
  it('blocks archived pages and titles/languages a save would overwrite', () => {
    expect(restoreEditablePage({ ...page(), status: 'archived' }, initialProject).writable).toBe(false);
    expect(restoreEditablePage({ ...page(), titles: { en: 'Other title' } }, initialProject).writable).toBe(false);
    expect(restoreEditablePage({ ...page(), titles: { en: initialProject.name, ar: 'عنوان' } }, initialProject).writable).toBe(false);
  });
});
