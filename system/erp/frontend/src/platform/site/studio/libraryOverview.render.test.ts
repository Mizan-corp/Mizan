// @vitest-environment jsdom
import {it,expect} from 'vitest';
import {setUILang} from './uiStrings';
import {createElement as h} from 'react';
import {render} from '@testing-library/react';
// jsdom here has no ResizeObserver; the thumbnail fit effect only needs the API shape.
class RO{observe(){}unobserve(){}disconnect(){}}
(globalThis as unknown as {ResizeObserver?:unknown}).ResizeObserver=(globalThis as unknown as {ResizeObserver?:unknown}).ResizeObserver??RO;
import LibraryOverview from './LibraryOverview';
import {toPageTree} from './pagetree';
import {initialProject} from './model';

it('LibraryOverview renders the Arabic overview without touching uninitialized helpers',()=>{
 // Regression: the visible-assets filter once referenced a const helper declared
 // later in the component body (TDZ crash that blanked the deployed editor).
 setUILang('ar');
  const tree=toPageTree(initialProject);
 const {container}=render(h(LibraryOverview,{tree,onPage:()=>{},onBlock:()=>{},onMotion:()=>{},onDesign:()=>{}}));
 expect(container.textContent).toContain('مكتبة واحدة');
 expect(container.textContent).toContain('بدايات صفحات');
 expect(container.textContent).toContain('بلوكات');
});
