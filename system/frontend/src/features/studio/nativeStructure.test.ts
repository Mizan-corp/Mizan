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
 expect(()=>changeStructure(state,{kind:'insert',parentId:tree.id,type:'image',id:'n_badplace'})).toThrow();
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
