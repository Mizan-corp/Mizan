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
it('persists free width pct per device and resets to content-based',()=>{
  const next=editNativeTree(tree,{kind:'setting',id:'n_col1234',device:'desktop',field:'min_height_px',value:200});
  const wide=editNativeTree(next,{kind:'setting',id:'n_col1234',device:'desktop',field:'min_height_px',value:null});
  expect(wide.children?.[0].children?.[0].settings.desktop).toEqual({});
  const leaf:PageNode={id:'n_root123',type:'section',settings:{},content:{},children:[{id:'n_row1234',type:'columns',settings:{},content:{},children:[{id:'n_col1234',type:'column',settings:{},content:{},children:[{id:'n_tx1234',type:'text',settings:{},content:{en:{html:'hi'}}}]}]}]};
  const sized=editNativeTree(leaf,{kind:'setting',id:'n_tx1234',device:'desktop',field:'width_pct',value:63});
  expect(sized.children?.[0].children?.[0].children?.[0].settings.desktop?.width_pct).toBe(63);
  assertNativeTree(sized);
  const mobileSized=editNativeTree(sized,{kind:'setting',id:'n_tx1234',device:'mobile',field:'width_pct',value:80});
  expect(mobileSized.children?.[0].children?.[0].children?.[0].settings.mobile?.width_pct).toBe(80);
  expect(mobileSized.children?.[0].children?.[0].children?.[0].settings.desktop?.width_pct).toBe(63);
  const reset=editNativeTree(mobileSized,{kind:'setting',id:'n_tx1234',device:'desktop',field:'width_pct',value:null});
  expect(reset.children?.[0].children?.[0].children?.[0].settings.desktop?.width_pct).toBeUndefined();
  assertNativeTree(reset);
});
it('rejects out-of-bounds width pct',()=>{
  const leaf:PageNode={id:'n_root123',type:'section',settings:{},content:{},children:[{id:'n_row1234',type:'columns',settings:{},content:{},children:[{id:'n_col1234',type:'column',settings:{},content:{},children:[{id:'n_tx1234',type:'text',settings:{},content:{en:{html:'hi'}}}]}]}]};
  for(const bad of [9,101,63.5,'63',true,[63]])expect(()=>editNativeTree(leaf,{kind:'setting',id:'n_tx1234',device:'desktop',field:'width_pct',value:bad as number})).toThrow();
  expect(()=>editNativeTree(tree,{kind:'setting',id:'n_col1234',device:'desktop',field:'width_pct',value:50})).toThrow();
});
