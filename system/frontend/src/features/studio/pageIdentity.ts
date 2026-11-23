import type { PageSummary } from './sitePages';

export type PageChoice = { kind: 'existing'; id: string } | { kind: 'new' } | { kind: 'blocked'; reason: string };

// Page identity is never inferred from a mutable brand name or a list's order.
export function choosePage(items: PageSummary[], requestedId: string | null): PageChoice {
  if (requestedId !== null) {
    const found = items.find(page => page.id === requestedId);
    return found ? { kind: 'existing', id: found.id } : { kind: 'blocked', reason: 'The requested page is not available. No other page was selected.' };
  }
  if (!items.length) return { kind: 'new' };
  if (items.length === 1) return { kind: 'existing', id: items[0].id };
  return { kind: 'blocked', reason: 'More than one page exists. Open an explicit ?page=PAGE_ID link. This prototype does not choose a page for you.' };
}
