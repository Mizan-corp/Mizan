// @vitest-environment jsdom
import {it,expect} from 'vitest';
import {createElement as h} from 'react';
import {render} from '@testing-library/react';
import LibraryOverview from './LibraryOverview';
import {toPageTree} from './pagetree';
import {initialProject} from './model';

it('LibraryOverview renders the Arabic overview without touching uninitialized helpers',()=>{
 // Regression: the visible-assets filter once referenced a const helper declared
 // later in the component body (TDZ crash that blanked the deployed editor).
 const tree=toPageTree(initialProject);
 const {container}=render(h(LibraryOverview,{tree,onPage:()=>{},onBlock:()=>{},onMotion:()=>{},onDesign:()=>{}}));
 expect(container.textContent).toContain('مكتبة واحدة');
 expect(container.textContent).toContain('بدايات صفحات');
 expect(container.textContent).toContain('بلوكات');
});
