import { fromPageTree } from './fromtree';
import type { Project } from './model';
import type { PageDetail } from './sitePages';

export type PageRestore = { writable: true; project: Project } | { writable: false; reason: string };

// This narrow prototype must never silently replace data it cannot represent.
export function restoreEditablePage(page: PageDetail, base: Project): PageRestore {
  if (page.status === 'archived') return { writable: false, reason: 'This page is archived.' };
  if (Object.keys(page.titles).length !== 1 || page.titles[base.language] !== base.name) {
    return { writable: false, reason: 'This page has titles or languages this prototype cannot preserve.' };
  }
  const tree = page.draft_tree ?? page.published_tree;
  if (!tree) return { writable: true, project: base };
  try { return { writable: true, project: fromPageTree(tree, base) }; }
  catch { return { writable: false, reason: 'This page contains blocks, content or settings this prototype cannot preserve.' }; }
}
