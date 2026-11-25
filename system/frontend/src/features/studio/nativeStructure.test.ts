import {expect,it} from 'vitest';
import {toPageTree} from './pagetree';
import {initialProject} from './model';
import {nativeNodes,nativeUndo,nativeRedo,nativeChange} from './nativeTree';
import {changeStructure} from './nativeStructure';
it('inserts, reorders, removes and undo/redoes without regenerating existing IDs or unrelated fields',()=>{
 const tree=toPageTree(initialProject),before=JSON.stringify(tree),parent=tree.children![0].children![0];
 const inserted=changeStructure({tree,past:[],future:[]},{kind:'insert',parentId:parent.id,type:'heading',id:'n_newheading'});
 expect(nativeNodes(inserted.tree).map(n=>n.id).filter(id=>id!=='n_newheading')).toEqual(nativeNodes(tree).map(n=>n.id));
 const moved=changeStructure(inserted,{kind:'move',id:'n_newheading',direction:-1});
 expect(nativeNodes(moved.tree).find(n=>n.id===parent.id)!.children!.at(-2)!.id).toBe('n_newheading');
 const removed=changeStructure(moved,{kind:'remove',id:'n_newheading'});
 expect(removed.tree).toEqual(tree);expect(nativeUndo(removed).tree).toEqual(moved.tree);expect(nativeRedo(nativeUndo(removed)).tree).toEqual(tree);
 expect(JSON.stringify(tree)).toBe(before);
});
it('updates only edited row column-count when adding a column',()=>{
 const tree=toPageTree(initialProject),row=tree.children![0];
 const added=changeStructure({tree,past:[],future:[]},{kind:'insert',parentId:row.id,type:'column',id:'n_newcolumn'});
 const expected=structuredClone(tree);expected.children![0].children!.push({id:'n_newcolumn',type:'column',settings:{},content:{},children:[]});expected.children![0].settings.desktop.columns=3;
 expect(added.tree).toEqual(expected);
});
it('refuses root deletion, unsupported placement and duplicate IDs without mutation',()=>{
 const tree=toPageTree(initialProject),before=JSON.stringify(tree),state={tree,past:[],future:[]};
 expect(()=>changeStructure(state,{kind:'remove',id:tree.id})).toThrow();
 expect(()=>changeStructure(state,{kind:'insert',parentId:tree.children![0].children![0].id,type:'columns',id:'n_badplace'})).toThrow();
 expect(()=>changeStructure(state,{kind:'insert',parentId:tree.id,type:'columns',id:tree.id})).toThrow();
 expect(JSON.stringify(tree)).toBe(before);expect(state.past).toEqual([]);
});
it('newly inserted content remains native-editable',()=>{
 const tree=toPageTree(initialProject),state=changeStructure({tree,past:[],future:[]},{kind:'insert',parentId:tree.children![0].children![0].id,type:'text',id:'n_newtext'});
 expect(nativeNodes(nativeChange(state,{kind:'content',id:'n_newtext',lang:'ar',field:'html',value:'<p>جديد</p>'}).tree).find(n=>n.id==='n_newtext')!.content.ar.html).toBe('<p>جديد</p>');
});

it('new rows start with a valid column and refuse last-column deletion',()=>{
 const tree=toPageTree(initialProject),state=changeStructure({tree,past:[],future:[]},{kind:'insert',parentId:tree.id,type:'columns',id:'n_newrow'});
 const row=state.tree.children!.at(-1)!;
 expect(row.children).toHaveLength(1);expect(row.children![0].type).toBe('column');expect(row.children![0].id).toMatch(/^n_[a-z0-9]{4,16}$/);
 expect(()=>changeStructure(state,{kind:'remove',id:row.children![0].id})).toThrow('Keep at least one column');
});

it('places inserts and moves across compatible columns with original subtree IDs and undo',()=>{
 const tree=toPageTree(initialProject),source=tree.children![0].children![0],target=tree.children![0].children![1],node=source.children![0];
 const state={tree,past:[],future:[]};
 const moved=changeStructure(state,{kind:'relocate',id:node.id,parentId:target.id,index:0});
 expect(moved.tree.children![0].children![1].children![0]).toEqual(node);
 expect(nativeUndo(moved).tree).toEqual(tree);
 expect(nativeNodes(moved.tree).map(n=>n.id).sort()).toEqual(nativeNodes(tree).map(n=>n.id).sort());
 const inserted=changeStructure(state,{kind:'insert',parentId:source.id,type:'heading',id:'n_positioned',index:0});
 expect(inserted.tree.children![0].children![0].children![0].id).toBe('n_positioned');
 // A content block relocated onto a section is wrapped in a fresh row and column.
 const wrapped=changeStructure(state,{kind:'relocate',id:node.id,parentId:tree.id,index:0});
 expect(wrapped.tree.children![0].type).toBe('columns');
 expect(wrapped.tree.children![0].children![0].children![0].id).toBe(node.id);
 expect(()=>changeStructure(state,{kind:'relocate',id:source.id,parentId:source.id,index:0})).toThrow();
 expect(()=>changeStructure(state,{kind:'insert',parentId:source.id,type:'text',id:'n_invalidpos',index:999})).toThrow();
 expect(state.tree).toEqual(tree);
});

it('wraps a card dropped straight onto a section in a row, styled as a card',()=>{
 const tree=toPageTree(initialProject),state={tree,past:[],future:[]};
 const next=changeStructure(state,{kind:'insert',parentId:tree.id,type:'card',id:'n_newcard'});
 const row=next.tree.children!.at(-1)!;
 expect(row.type).toBe('columns');expect(row.settings.desktop.columns).toBe(1);
 const col=row.children![0];
 expect(col.type).toBe('column');expect(col.id).toBe('n_newcard');
 expect(col.settings.desktop).toEqual({background:'card',padding:'s',rounded:true});
});
it('wraps a content block dropped straight onto a section in a row and column',()=>{
 const tree=toPageTree(initialProject),state={tree,past:[],future:[]};
 const next=changeStructure(state,{kind:'insert',parentId:tree.id,type:'text',id:'n_newtext2',index:0});
 const row=next.tree.children![0];
 expect(row.type).toBe('columns');
 expect(row.children![0].type).toBe('column');
 expect(row.children![0].children![0]).toMatchObject({id:'n_newtext2',type:'text'});
});
it('wraps a column relocated onto a section in a fresh row and keeps the source row valid',()=>{
 const tree=toPageTree(initialProject),state={tree,past:[],future:[]};
 const sourceRow=tree.children![0];
 const colId=sourceRow.children![0].id;
 const targetSection=changeStructure(state,{kind:'insert',parentId:tree.id,type:'columns',id:'n_targetrow'}).tree;
 const next=changeStructure({tree:targetSection,past:[],future:[]},{kind:'relocate',id:colId,parentId:tree.id,index:0});
 expect(next.tree.children![0].type).toBe('columns');
 expect(next.tree.children![0].children![0].id).toBe(colId);
 const source=nativeNodes(next.tree).find(n=>n.id===sourceRow.id)!;
 expect(source.settings.desktop.columns).toBe(source.children!.length);
});
