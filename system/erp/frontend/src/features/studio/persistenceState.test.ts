import { expect, it } from 'vitest';
import { shouldWarnBeforeLeave, browserSaveLabel, backendSaveLabel, type PersistenceState } from './persistenceState';
const base: PersistenceState = {current:'initial',baseline:'initial',browserSaved:null,backendSaved:null,backendConnected:false,busy:false};
it('does not warn for unchanged initial state but warns for unpersisted local edits', () => {
  expect(shouldWarnBeforeLeave(base)).toBe(false);
  expect(shouldWarnBeforeLeave({...base,current:'edit'})).toBe(true);
  expect(shouldWarnBeforeLeave({...base,current:'edit',browserSaved:'edit'})).toBe(false);
});
it('browser save does not clear a connected backend dirty warning', () => {
  expect(shouldWarnBeforeLeave({...base,current:'edit',browserSaved:'edit',backendConnected:true,backendSaved:'initial'})).toBe(true);
  expect(shouldWarnBeforeLeave({...base,current:'edit',backendConnected:true,backendSaved:'edit'})).toBe(false);
});
it('always protects an in-flight operation and keeps failed storage unsaved', () => {
  expect(shouldWarnBeforeLeave({...base,busy:true})).toBe(true);
  expect(browserSaveLabel('edit',null)).toBe('Browser copy not saved');
  expect(backendSaveLabel('edit','edit',true)).toBe('Backend snapshot saved');
  expect(backendSaveLabel('edit','edit',false)).toBe('Backend saving unavailable');
});
