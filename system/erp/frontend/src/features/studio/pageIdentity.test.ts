import { describe, expect, it } from 'vitest';
import { choosePage } from './pageIdentity';
import type { PageSummary } from './sitePages';
const p = (id: string): PageSummary => ({id, slug: `slug-${id}`, titles:{en:'Independent title'},status:'draft',has_draft:true,published:false,created_at:null,updated_at:null});
describe('stable page selection', () => {
  it('uses the explicit identity even when list order and brand-related slugs differ', () => {
    expect(choosePage([p('two'),p('one')], 'one')).toEqual({kind:'existing',id:'one'});
  });
  it('never falls back when a requested identity disappears', () => {
    expect(choosePage([p('other')], 'missing').kind).toBe('blocked');
    expect(choosePage([], 'missing').kind).toBe('blocked');
  });
  it('uses only an unambiguous first-open target, never the first of many', () => {
    expect(choosePage([p('only')], null)).toEqual({kind:'existing',id:'only'});
    expect(choosePage([p('one'),p('two')], null).kind).toBe('blocked');
    expect(choosePage([], null)).toEqual({kind:'new'});
  });
  it('starts a fresh page on an explicit new request, even when pages exist', () => {
    expect(choosePage([p('one'),p('two')], 'new')).toEqual({kind:'new'});
    expect(choosePage([], 'new')).toEqual({kind:'new'});
  });
});
