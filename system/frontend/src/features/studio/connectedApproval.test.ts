import {describe, expect, it} from 'vitest';
import {needsWiderApproval} from './connectedApproval';

describe('needsWiderApproval', () => {
  it('is false without an existing connected approval', () => {
    expect(needsWiderApproval(['inventory.products'], null)).toBe(false);
    expect(needsWiderApproval(['inventory.products'], {connected_data: false})).toBe(false);
  });
  it('is false when the published sources stay inside the approved set', () => {
    expect(needsWiderApproval(['inventory.website_cards'], {connected_data: true, sources: ['inventory.website_cards']})).toBe(false);
    expect(needsWiderApproval([], {connected_data: true, sources: ['inventory.website_cards']})).toBe(false);
  });
  it('is true when the published tree widened beyond the approved set', () => {
    expect(needsWiderApproval(['inventory.website_cards', 'inventory.products'], {connected_data: true, sources: ['inventory.website_cards']})).toBe(true);
  });
  it('treats a missing approved list as nothing approved', () => {
    expect(needsWiderApproval(['inventory.products'], {connected_data: true})).toBe(true);
  });
});
