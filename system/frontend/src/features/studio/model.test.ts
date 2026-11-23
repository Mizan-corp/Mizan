import { describe, expect, it } from 'vitest';
import { DRAFT_KEY, initialProject, loadDraft, moveSection, validateProject } from './model';
describe('experimental studio project', () => {
 it('validates the default and restores a saved local draft', () => {
  expect(validateProject(initialProject)).toBe(true);
  const changed = structuredClone(initialProject); changed.sections[0].title = 'Saved title';
  const storage = {getItem:(key:string) => key === DRAFT_KEY ? JSON.stringify(changed) : null};
  expect(loadDraft(storage).sections[0].title).toBe('Saved title');
 });
 it('falls back on invalid stored data without mutating defaults', () => {
  const a=loadDraft({getItem:()=>'{bad'});a.sections[0].title='Changed';
  expect(initialProject.sections[0].title).not.toBe('Changed');
  expect(loadDraft({getItem:()=>'{"version":9}'})).toEqual(initialProject);
 });
 it('reorders immutably and preserves bounds', () => {
  const moved=moveSection(initialProject,'hero-1',1);
  expect(moved.sections[1].id).toBe('hero-1');expect(initialProject.sections[0].id).toBe('hero-1');
  expect(moveSection(initialProject,'hero-1',-1)).toBe(initialProject);
 });
 it('refuses unsupported imported values and duplicate sections', () => {
  for(const image of ['javascript:alert(1)','http://example.com/x','//example.com/x']) {
   const p=structuredClone(initialProject);p.sections[0].image=image;expect(validateProject(p)).toBe(false);
  }
  const p=structuredClone(initialProject);p.sections.push(p.sections[0]);expect(validateProject(p)).toBe(false);
  expect(validateProject({...initialProject,colors:{background:'red',foreground:'#000000',accent:'#ffffff'}})).toBe(false);
  expect(validateProject({...initialProject,radius:999})).toBe(false);
 });
});
