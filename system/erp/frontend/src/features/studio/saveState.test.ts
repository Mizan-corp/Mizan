import { describe, expect, it } from 'vitest';
import { createOperationGate, saveResultNotice, snapshotKey } from './saveState';
import { initialProject } from './model';
describe('single-editor snapshot operations', () => {
  it('rejects repeated operations until completion and permits retry after failure cleanup', () => {
    const gate = createOperationGate();
    expect(gate.start()).toBe(true);
    expect(gate.start()).toBe(false);
    expect(gate.active).toBe(true);
    gate.finish();
    expect(gate.start()).toBe(true);
    gate.finish();
    expect(gate.active).toBe(false);
  });
  it('reports an earlier snapshot honestly when editing continued', () => {
    const snapshot = snapshotKey(initialProject);
    const later = structuredClone(initialProject);later.sections[0].title='New unsaved text';
    expect(saveResultNotice(snapshot,snapshotKey(later))).toContain('Newer local changes are NOT saved');
    expect(saveResultNotice(snapshot,snapshot)).toContain('Draft and site settings saved');
    expect(saveResultNotice(snapshot,snapshot,true)).toContain('the workspace backend');
    expect(saveResultNotice(snapshot,snapshot,true)).not.toContain('local test backend');
    expect(saveResultNotice(snapshot,snapshotKey(later),true)).toContain('the workspace backend');
    expect(saveResultNotice(snapshot,snapshot,false)).toContain('local test backend');
  });
});
