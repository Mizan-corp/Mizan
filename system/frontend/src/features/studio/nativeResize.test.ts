import {it,expect} from 'vitest';
import {assertNativeTree,editNativeTree} from './nativeTree';
import type {PageNode} from './pagetree';
const tree:PageNode={id:'n_root123',type:'section',settings:{},content:{},children:[{id:'n_row1234',type:'columns',settings:{},content:{},children:[{id:'n_col1234',type:'column',settings:{},content:{},children:[]},{id:'n_col2345',type:'column',settings:{},content:{},children:[]}]}]};
it('persists free divider track ratios per device and resets to equal',()=>{
  const next=editNativeTree(tree,{kind:'setting',id:'n_row1234',device:'desktop',field:'tracks',value:[1.62,0.38]});
  expect(next.children?.[0].settings.desktop?.tracks).toEqual([1.62,0.38]);
  assertNativeTree(next);
  const mobile=editNativeTree(next,{kind:'setting',id:'n_row1234',device:'mobile',field:'tracks',value:[1,1.4]});
  expect(mobile.children?.[0].settings.mobile?.tracks).toEqual([1,1.4]);
  expect(mobile.children?.[0].settings.desktop?.tracks).toEqual([1.62,0.38]);
  const reset=editNativeTree(mobile,{kind:'setting',id:'n_row1234',device:'desktop',field:'tracks',value:null});
  expect(reset.children?.[0].settings.desktop?.tracks).toBeUndefined();
  assertNativeTree(reset);
});
it('rejects invalid track ratios',()=>{
  for(const bad of [[99,1],[0.1,1],[1],[1,1,1,1,1,1,1],['2',1],'2fr 1fr',2])expect(()=>editNativeTree(tree,{kind:'setting',id:'n_row1234',device:'desktop',field:'tracks',value:bad as number[]})).toThrow();
});
it('persists px min-height and resets to content-based',()=>{
  const next=editNativeTree(tree,{kind:'setting',id:'n_col1234',device:'desktop',field:'min_height_px',value:320});
  expect(next.children?.[0].children?.[0].settings.desktop?.min_height_px).toBe(320);
  assertNativeTree(next);
  const reset=editNativeTree(next,{kind:'setting',id:'n_col1234',device:'desktop',field:'min_height_px',value:null});
  expect(reset.children?.[0].children?.[0].settings.desktop).toEqual({});
});
it('rejects out-of-bounds min-height',()=>{
  for(const bad of [39,1201,300.5,'300',true])expect(()=>editNativeTree(tree,{kind:'setting',id:'n_col1234',device:'desktop',field:'min_height_px',value:bad as number})).toThrow();
});
