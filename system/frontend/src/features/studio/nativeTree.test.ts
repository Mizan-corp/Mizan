import { describe, expect, it } from 'vitest';
import { toPageTree, type PageNode } from './pagetree';
import { initialProject } from './model';
import { assertNativeTree, nativeChange, nativeUndo, nativeRedo, editNativeTree, nativeNodes } from './nativeTree';

export function compositions(): PageNode[] {
  const first=toPageTree(initialProject);
  first.children![0].children![0].children![1].content.ar={text:'عنوان محفوظ'};
  const second: PageNode={id:'n_secondroot',type:'section',settings:{desktop:{padding:'s'},mobile:{padding:'none'}},content:{},children:[
    {id:'n_rowdifferent',type:'columns',settings:{desktop:{columns:1,gap:'s'}},content:{},children:[
      {id:'n_colcustom',type:'column',settings:{desktop:{align:'center'}},content:{},children:[
        {id:'n_titleoriginal',type:'heading',settings:{desktop:{level:3},mobile:{align:'end'}},content:{en:{text:'Distinct page'},ar:{text:'صفحة أخرى'}}},
        {id:'n_richoriginal',type:'text',settings:{desktop:{variant:'body'}},content:{en:{html:'<p><strong>Retain this markup</strong></p>'}}},
        {id:'n_photooriginal',type:'image',settings:{desktop:{rounded:false}},content:{en:{src:'https://cdn.example.com/photo.png',alt:'Original image description'}}},
        {id:'n_buttonoriginal',type:'button',settings:{desktop:{style:'ghost'}},content:{en:{label:'Contact us',href:'/contact'}}},
      ]},
    ]},
  ]};
  return [first,second];
}

describe('tree-native immutable authoring',()=>{
  it.each([0,1])('edits one field in composition %s without touching other data or IDs, then undo/redo',i=>{
    const tree=compositions()[i], before=JSON.stringify(tree);
    const target=nativeNodes(tree).find(n=>n.type==='heading')!;
    const next=nativeChange({tree,past:[],future:[]},{kind:'content',id:target.id,lang:'en',field:'text',value:'Edited native heading'});
    const expected=structuredClone(tree);nativeNodes(expected).find(n=>n.id===target.id)!.content.en.text='Edited native heading';
    expect(next.tree).toEqual(expected);expect(JSON.stringify(tree)).toBe(before);
    expect(nativeNodes(next.tree).map(n=>n.id)).toEqual(nativeNodes(tree).map(n=>n.id));
    expect(nativeUndo(next).tree).toEqual(tree);
    expect(nativeRedo(nativeUndo(next)).tree).toEqual(expected);
    expect(JSON.parse(JSON.stringify(next.tree))).toEqual(expected);
  });
  it('changes a per-device setting without touching desktop, content, translation or alt',()=>{
    const tree=compositions()[1];
    const next=editNativeTree(tree,{kind:'setting',id:'n_titleoriginal',device:'mobile',field:'level',value:5});
    const expected=structuredClone(tree);nativeNodes(expected).find(n=>n.id==='n_titleoriginal')!.settings.mobile.level=5;
    expect(next).toEqual(expected);
  });
  it('refuses unsupported operations and formats without changing source or history',()=>{
    const tree=compositions()[1], before=JSON.stringify(tree);
    for(const edit of [
      {kind:'content',id:'missing',lang:'en',field:'text',value:'x'},
      {kind:'content',id:'n_buttonoriginal',lang:'en',field:'href',value:'javascript:alert(1)'},
      {kind:'setting',id:'n_titleoriginal',device:'mobile',field:'raw_css',value:'color:red'},
    ] as const) expect(()=>editNativeTree(tree,edit)).toThrow();
    expect(JSON.stringify(tree)).toBe(before);
    const foreign=structuredClone(tree);foreign.children![0].children![0].children![0].type='gallery';
    const foreignBefore=JSON.stringify(foreign);expect(()=>assertNativeTree(foreign)).toThrow();expect(JSON.stringify(foreign)).toBe(foreignBefore);
  });
  it('rejects duplicate IDs and preserves original input on rejected edits',()=>{
    const t=compositions()[0];t.children![0].id=t.id;
    expect(()=>assertNativeTree(t)).toThrow();
  });
});
