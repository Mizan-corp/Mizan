// @vitest-environment jsdom
import {it,expect,afterEach} from 'vitest';
import {createElement as h} from 'react';
import {render,cleanup} from '@testing-library/react';
import NativeRepeatControls from './NativeRepeatControls';
import NativeCardRepeatControls from './NativeCardRepeatControls';
import {repeatSchema,repeatCardSchema} from './nativeBindings';

// Regression: a collection bound under one content language silently rendered
// NOTHING when the page was rendered in its other/default language (live finding
// 2026-11-25: ar-bound repeat invisible on an en-titled public page). The
// controls must say so in both directions and stay quiet when both languages
// are bound.

const plan={module:'helpdesk',source:'services',field:'name',limit:8,on_missing:'hide'};
const discover=async()=>({collections:[]});
const noop=()=>{};

function headingNode(content:Record<string,unknown>){
 return {id:'n1',type:'heading',settings:{},content:{en:{text:'x'},ar:{text:'x'}},children:[],
         repeat:{schema:repeatSchema,content}} as never;
}
function columnNode(content:Record<string,unknown>){
 return {id:'c1',type:'column',settings:{},content:{},repeat:{schema:repeatCardSchema,slots:{heading:'name'},content},
         children:[{id:'h1',type:'heading',settings:{},content:{en:{text:'x'}},children:[]}]} as never;
}

afterEach(()=>cleanup());

it('unbound side: hints that the collection is bound for the other language only',()=>{
 const {container}=render(h(NativeRepeatControls,{node:headingNode({ar:plan}),language:'en',discover,onChange:noop}));
 expect(container.textContent).toContain('bound for Arabic only');
 expect(container.textContent).toContain('choose the same collection here');
});

it('bound side: hints that this language is the only bound one',()=>{
 const {container}=render(h(NativeRepeatControls,{node:headingNode({en:plan}),language:'en',discover,onChange:noop}));
 expect(container.textContent).toContain('bound for this content language only');
 expect(container.textContent).toContain('open the other language');
});

it('both languages bound: no hint either way',()=>{
 const {container}=render(h(NativeRepeatControls,{node:headingNode({en:plan,ar:plan}),language:'en',discover,onChange:noop}));
 expect(container.textContent).not.toContain('bound for this content language only');
 expect(container.textContent).not.toContain('bound for Arabic only');
});

it('nothing bound: no hint',()=>{
 const {container}=render(h(NativeRepeatControls,{node:headingNode({}),language:'en',discover,onChange:noop}));
 expect(container.textContent).not.toContain('only');
});

it('card repeat: same hint in both directions',()=>{
 const a=render(h(NativeCardRepeatControls,{node:columnNode({ar:plan}),language:'en',discover,onChange:noop}));
 expect(a.container.textContent).toContain('bound for Arabic only');
 cleanup();
 const b=render(h(NativeCardRepeatControls,{node:columnNode({en:plan}),language:'en',discover,onChange:noop}));
 expect(b.container.textContent).toContain('bound for this content language only');
});
