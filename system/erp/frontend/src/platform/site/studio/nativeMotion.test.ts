// @vitest-environment jsdom
import {it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {createElement} from 'react';
import TreePreview from './treerender';
import {toPageTree} from './pagetree';
import {initialProject} from './model';
import {editNativeTree,nativeChange,nativeUndo,assertNativeTree} from './nativeTree';
it('persists only constrained per-device entrance settings and preserves unrelated content',()=>{const tree=toPageTree(initialProject),original=structuredClone(tree),node=tree.children![0];let next=tree;for(const effect of ['none','fade','rise','slide','zoom']){next=editNativeTree(tree,{kind:'setting',id:node.id,device:'desktop',field:'animation',value:effect});assertNativeTree(next);expect(next.children![1]).toEqual(tree.children![1]);expect(nativeUndo(nativeChange({tree,past:[],future:[]},{kind:'setting',id:node.id,device:'desktop',field:'animation',value:effect})).tree).toEqual(tree)}expect(()=>editNativeTree(tree,{kind:'setting',id:node.id,device:'desktop',field:'animation',value:'url(evil)'})).toThrow();expect(tree).toEqual(original)});
it('React emits shared motion classes with desktop inheritance and mobile override',()=>{const tree=toPageTree(initialProject);tree.children![0].settings.desktop={...tree.children![0].settings.desktop,animation:'rise',animation_speed:'slow',animation_delay:'short'};tree.children![0].settings.mobile={...tree.children![0].settings.mobile,animation:'none'};const render=(device:'desktop'|'mobile')=>renderToStaticMarkup(createElement(TreePreview,{tree,lang:'en',device}));expect(render('desktop')).toContain('mz-animation-rise');expect(render('desktop')).toContain('mz-animation-speed-slow');expect(render('mobile')).toContain('mz-animation-none');expect(render('mobile')).not.toContain('mz-animation-rise')});
