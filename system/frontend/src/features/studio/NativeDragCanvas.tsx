import { createPortal } from 'react-dom';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { PageNode } from './pagetree';
import { readableType, readableTypeAr, readableName } from './nativePresets';
import { useUILang } from './uiStrings';
import { nativeNodes, type NativeDevice } from './nativeTree';
import { childTypes, newNativeId, type StructureEdit } from './nativeStructure';
import { beginTapGesture, trackTapMove, isTapRelease, type TapGesture } from './nativeTap';

type Pick={kind:'new';type:string}|{kind:'node';id:string;type:string}|{kind:'preset';type:'columns';preset:import('./nativePresets').PresetKind}|{kind:'template';type:'columns';template:import('./nativePresets').TemplateKind};
type Drop={parentId:string;index:number;x:number;y:number;width:number;height:number;label:string;box:{x:number;y:number;width:number;height:number}};
type Feedback={x:number;y:number;label:string;sample:string;valid:boolean;destination:string};
export default function NativeDragCanvas({tree,projectionMap,selected,onSelect,onChange,onSetting,device,children,lang}:{projectionMap?:Record<string,string>;tree:PageNode;selected:string;onSelect:(id:string)=>void;onChange:(edit:StructureEdit)=>void;onSetting:(id:string,field:string,value:string|number|boolean|number[]|null)=>void;device:NativeDevice;children:ReactNode;lang?:'en'|'ar'}){
 const uiLang=useUILang();
 const canvas=useRef<HTMLDivElement>(null),[pick,setPick]=useState<Pick|null>(null),[drop,setDrop]=useState<Drop|null>(null),[feedback,setFeedback]=useState<Feedback|null>(null),[status,setStatus]=useState('Drag a block to the page. On touch, select an element and use Move. Keyboard users can choose Insert here.');
 const [hover,setHover]=useState('');
 const [paletteHost,setPaletteHost]=useState<HTMLElement|null>(null);useEffect(()=>{setPaletteHost(document.getElementById('native-add-panel'))},[]);
 const active=useRef<Pick|null>(null),destination=useRef<Drop|null>(null),origin=useRef<{x:number;y:number}|null>(null),point=useRef<{x:number;y:number}|null>(null),dragging=useRef(false),suppressClick=useRef(false);
 const tap=useRef<TapGesture|null>(null);
 const nodes=nativeNodes(tree);
 const sourceId=(id:string)=>projectionMap?.[id]??id;
 const ancestors:PageNode[]=[];const findPath=(n:PageNode):boolean=>{ancestors.push(n);if(n.id===selected)return true;for(const c of n.children??[])if(findPath(c))return true;ancestors.pop();return false};findPath(tree);
 useEffect(()=>{const root=canvas.current;if(!root)return;for(const el of root.querySelectorAll<HTMLElement>('.mz-node')){el.classList.toggle('native-selected-node',sourceId(el.id)===selected&&selected!==tree.id);el.classList.toggle('native-hover-node',sourceId(el.id)===hover);const tagNode=nodes.find(n=>n.id===sourceId(el.id))??({type:'',settings:{}} as PageNode);el.dataset.nativeType=uiLang==='ar'?readableTypeAr(tagNode.type):readableType(tagNode.type);el.dataset.nativeLabel=uiLang==='ar'?readableTypeAr(tagNode.type)+' — اضغط للتعديل':readableType(tagNode.type)+' — Click to edit';}},[tree,selected,hover,projectionMap,uiLang]);
 const allowed=(parent:PageNode,item:Pick)=>{
  if(item.kind==='template')return parent.id===tree.id;
  if(item.kind==='preset')return parent.id===tree.id;
  // Sections accept a card, column or content block directly; the drop wraps it
  // in the row (and column) it needs (see nativeStructure.changeStructure).
  const effType=item.kind==='new'&&item.type==='card'?'column':item.type;
  if(parent.type==='section'&&(effType==='column'||childTypes('column').includes(effType)))return true;
  if(!childTypes(parent.type).includes(effType))return false;
  if(item.kind==='node'){
   const node=nodes.find(n=>n.id===item.id),source=nodes.find(n=>n.children?.some(c=>c.id===item.id));
   if(!node||nativeNodes(node).some(n=>n.id===parent.id))return false;
   if(source?.id!==parent.id&&source?.type==='columns'&&source.children?.length===1)return false;
   if(source?.id!==parent.id&&parent.type==='columns'&&(parent.children?.length??0)>=6)return false;
  }else if(parent.type==='columns'&&(parent.children?.length??0)>=6)return false;
  return true;
 };
 const apply=(item:Pick,target:{parentId:string;index:number})=>{onChange(item.kind==='preset'?{kind:'preset',preset:item.preset,index:target.index}:item.kind==='template'?{kind:'template',template:item.template}:item.kind==='new'?{kind:'insert',type:item.type,id:newNativeId(tree),...target}:{kind:'relocate',id:item.id,...target});setPick(null);setDrop(null);setStatus('Drop processed. Unsaved page change. Undo is available.');};
 const start=(item:Pick,x:number,y:number)=>{active.current=item;origin.current={x,y};point.current={x,y};destination.current=null;dragging.current=false;};
 const begin=(item:Pick,e:React.PointerEvent)=>{if(e.button!==0)return;start(item,e.clientX,e.clientY);e.preventDefault();};
 useEffect(()=>{
  let frame=0;
  const announce=(value:boolean)=>window.dispatchEvent(new CustomEvent('native-drag-state',{detail:value}));
  const library=(event:Event)=>{const d=(event as CustomEvent).detail;if(d&&['preset','template','node'].includes(d.item?.kind))start(d.item,d.x,d.y)};
  const update=()=>{
   const item=active.current,at=point.current,o=origin.current;if(!item||!at||!o)return;
   if(!dragging.current&&Math.hypot(at.x-o.x,at.y-o.y)<6)return;
   if(!dragging.current){dragging.current=true;setPick(item);announce(true);setStatus('Dragging. Release on a highlighted destination. Escape cancels.');}
   const scroller=canvas.current?.closest<HTMLElement>('.studio-canvas');
   if(scroller){const r=scroller.getBoundingClientRect(),top=r.top+55,bottom=Math.min(r.bottom,innerHeight-74);if(at.x>=r.left&&at.x<=r.right){if(at.y>=r.top+60&&at.y<top+15)scroller.scrollTop-=Math.min(16,(top+15-at.y)/3);else if(at.y>bottom-55)scroller.scrollTop+=Math.min(16,(at.y-bottom+55)/3);}}
   let el=document.elementFromPoint(at.x,at.y)?.closest<HTMLElement>('.mz-node')??null,target:Drop|null=null;
   while(el&&canvas.current?.contains(el)){
    const parent=nodes.find(n=>n.id===el!.id);
    if(parent&&allowed(parent,item)){
     const children=(parent.children??[]).map(n=>document.getElementById(n.id)).filter((n):n is HTMLElement=>!!n);
     const css=getComputedStyle(el),horizontal=parent.type==='columns'&&(css.display.includes('flex')?!css.flexDirection.startsWith('column'):(children.length>1&&Math.abs(children[0].getBoundingClientRect().top-children[1].getBoundingClientRect().top)<10));
     const rtl=horizontal&&css.direction==='rtl';let index=children.findIndex(c=>{const r=c.getBoundingClientRect();return horizontal?(rtl?at.x>r.left+r.width/2:at.x<r.left+r.width/2):at.y<r.top+r.height/2});if(index<0)index=children.length;
     const r=el.getBoundingClientRect(),next=children[index]?.getBoundingClientRect(),last=children.at(-1)?.getBoundingClientRect();
     const prevName=parent.children?.[index-1]?readableName(parent.children[index-1]):'',nextName=parent.children?.[index]?readableName(parent.children[index]):'';
     const label=item.kind==='template'?'Replace page body, confirmation required':prevName&&nextName?`Between ${prevName} and ${nextName}`:nextName?`Before ${nextName}`:prevName?`After ${prevName}`:`Inside ${readableType(parent.type)}`;
     target={parentId:parent.id,index,x:horizontal?(rtl?(next?.right??last?.left??r.right):(next?.left??last?.right??r.left)):r.left,y:horizontal?r.top:(next?.top??last?.bottom??r.top),width:horizontal?4:r.width,height:horizontal?r.height:4,label,box:{x:r.left,y:r.top,width:r.width,height:r.height}};break;
    }
    el=el.parentElement?.closest<HTMLElement>('.mz-node')??null;
   }
   destination.current=target;setDrop(target);
   const n=item.kind==='node'?nodes.find(n=>n.id===item.id):null,label=item.kind==='preset'?`${item.preset} section`:item.kind==='template'?`${item.template} page`:readableType(item.type);
   setFeedback({x:Math.min(innerWidth-228,Math.max(8,at.x+18)),y:Math.min(innerHeight-105,Math.max(8,at.y-155)),label,sample:n?readableName(n):item.kind==='template'?'Replace page body':'New editable block',valid:!!target,destination:target?.label??'Cannot drop here. Move onto a compatible area.'});
  };
  const tick=()=>{update();if(active.current)frame=requestAnimationFrame(tick)};
  const move=(e:PointerEvent)=>{if(!active.current)return;point.current={x:e.clientX,y:e.clientY};if(dragging.current||Math.hypot(e.clientX-origin.current!.x,e.clientY-origin.current!.y)>=6){if(e.cancelable)e.preventDefault();if(!frame)frame=requestAnimationFrame(tick)}};
  const reset=()=>{cancelAnimationFrame(frame);frame=0;active.current=null;point.current=null;origin.current=null;destination.current=null;dragging.current=false;setFeedback(null);setDrop(null);announce(false)};
  const end=()=>{const item=active.current,target=destination.current,moved=dragging.current;if(!item)return;suppressClick.current=moved;setTimeout(()=>{suppressClick.current=false},0);reset();if(moved&&target)apply(item,target);else{if(item.kind==='node'&&!moved)onSelect(item.id);if(item.kind!=='new')setPick(null);setStatus(moved?'Drop cancelled. Page unchanged.':'Element selected. Use Move to drag, or choose an Insert here position.');}};
  const cancel=()=>{reset();setPick(null);setStatus('Drag cancelled. Page unchanged.');};
  const key=(e:KeyboardEvent)=>{if(e.key==='Escape')cancel()};
  addEventListener('native-library-drag',library);addEventListener('pointermove',move,{passive:false});addEventListener('pointerup',end);addEventListener('pointercancel',cancel);addEventListener('keydown',key);
  return()=>{cancelAnimationFrame(frame);removeEventListener('native-library-drag',library);removeEventListener('pointermove',move);removeEventListener('pointerup',end);removeEventListener('pointercancel',cancel);removeEventListener('keydown',key)};
 },[tree,selected]);
 // --- Border & divider resize: free sizing by dragging, committed per device. ---
 const [handles,setHandles]=useState<{height?:{x:number;y:number};dividers?:{x:number;y:number;h:number;index:number}[];sides?:{left:{x:number;y:number};right:{x:number;y:number}}}>({});
 const resizeRef=useRef<null|{kind:'height';id:string;inner:HTMLElement;startY:number;startH:number;value:number}|{kind:'divider';id:string;index:number;inner:HTMLElement;tracks:number[];pairStart:number;pairWidth:number;leftFirst:boolean;value:number[]}|{kind:'width';id:string;edge:'left'|'right';inner:HTMLElement;anchorX:number;parentWidth:number;value:number}>(null);
 useEffect(()=>{
  const nodeEl=(id:string)=>[...canvas.current?.querySelectorAll<HTMLElement>('.mz-node')??[]].find(e=>sourceId(e.id)===id);
  const update=()=>{
   const node=nodes.find(n=>n.id===selected);
   const el=selected&&nodeEl(selected);
   if(!node||!el||selected===tree.id){setHandles({});return}
   const r=el.getBoundingClientRect();
   const dividers:{x:number;y:number;h:number;index:number}[]=[];
   if(node.type==='columns'&&(node.children?.length??0)>1){
    const kids=(node.children??[]).map(c=>nodeEl(c.id)).filter((e):e is HTMLElement=>!!e);
    for(let i=0;i<kids.length-1;i++){
     const a=kids[i].getBoundingClientRect(),b=kids[i+1].getBoundingClientRect();
     dividers.push({x:(a.right+b.left)/2,y:(a.top+b.bottom)/2,h:Math.max(a.height,b.height),index:i});
    }
   }
   const widthResizable=['heading','text','image','button','gallery','video_embed','icon_list'].includes(node.type);
   const sides=widthResizable?{left:{x:r.left,y:r.top+r.height/2},right:{x:r.right,y:r.top+r.height/2}}:undefined;
   setHandles({height:{x:r.left+r.width/2,y:r.bottom},dividers,sides});
  };
  update();
  const sc=canvas.current?.closest('.studio-canvas');
  sc?.addEventListener('scroll',update,true);
  window.addEventListener('resize',update);
  const tick=window.setInterval(update,900);
  return()=>{sc?.removeEventListener('scroll',update,true);window.removeEventListener('resize',update);window.clearInterval(tick)};
 },[selected,tree,projectionMap]);
 const selectedNode=nodes.find(n=>n.id===selected);
 const selSettings=(selectedNode?.settings?.[device]??{}) as Record<string,unknown>;
 const selDesktop=(selectedNode?.settings?.desktop??{}) as Record<string,unknown>;
 const hasMinH=selSettings.min_height_px!==undefined||selDesktop.min_height_px!==undefined;
 const hasTracks=selSettings.tracks!==undefined||selDesktop.tracks!==undefined;
 const hasWidthPct=selSettings.width_pct!==undefined||selDesktop.width_pct!==undefined;
 const beginHeight=(e:React.PointerEvent)=>{
  if(e.button!==0)return;
  const el=[...canvas.current?.querySelectorAll<HTMLElement>('.mz-node')??[]].find(x=>sourceId(x.id)===selected);
  const inner=el?.firstElementChild as HTMLElement|null;
  if(!inner)return;
  e.preventDefault();e.stopPropagation();
  resizeRef.current={kind:'height',id:selected,inner,startY:e.clientY,startH:inner.getBoundingClientRect().height,value:Math.round(inner.getBoundingClientRect().height)};
  (e.target as HTMLElement).setPointerCapture(e.pointerId);
 };
 const beginDivider=(e:React.PointerEvent,index:number)=>{
  if(e.button!==0)return;
  const node=nodes.find(n=>n.id===selected);
  if(!node||node.type!=='columns')return;
  const el=[...canvas.current?.querySelectorAll<HTMLElement>('.mz-node')??[]].find(x=>sourceId(x.id)===selected);
  const inner=el?.firstElementChild as HTMLElement|null;
  const kids=(node.children??[]).map(c=>[...canvas.current?.querySelectorAll<HTMLElement>('.mz-node')??[]].find(x=>sourceId(x.id)===c.id)).filter((x):x is HTMLElement=>!!x);
  const a=kids[index],b=kids[index+1];
  if(!inner||!a||!b)return;
  const ra=a.getBoundingClientRect(),rb=b.getBoundingClientRect();
  const n=node.children?.length??0;
  const existing=node.settings?.[device]?.tracks??node.settings?.desktop?.tracks;
  const base=Array.isArray(existing)&&existing.length===n?existing.map(Number):Array(n).fill(1);
  e.preventDefault();e.stopPropagation();
  resizeRef.current={kind:'divider',id:selected,index,inner,tracks:base,pairStart:Math.min(ra.left,rb.left),pairWidth:Math.max(ra.right,rb.right)-Math.min(ra.left,rb.left),leftFirst:ra.left<rb.left,value:base};
  (e.target as HTMLElement).setPointerCapture(e.pointerId);
 };
 const beginWidth=(e:React.PointerEvent,edge:'left'|'right')=>{
  if(e.button!==0)return;
  const el=[...canvas.current?.querySelectorAll<HTMLElement>('.mz-node')??[]].find(x=>sourceId(x.id)===selected);
  const parent=el?.parentElement as HTMLElement|null;
  if(!el||!parent)return;
  const r=el.getBoundingClientRect();const pr=parent.getBoundingClientRect();
  if(pr.width<8)return;
  e.preventDefault();e.stopPropagation();
  resizeRef.current={kind:'width',id:selected,edge,inner:el,anchorX:edge==='right'?r.left:r.right,parentWidth:pr.width,value:Math.round(r.width/pr.width*100)};
  (e.target as HTMLElement).setPointerCapture(e.pointerId);
 };
 const moveResize=(e:React.PointerEvent)=>{
  const r=resizeRef.current;if(!r)return;
  e.preventDefault();
  if(r.kind==='height'){
   const v=Math.round(Math.min(1200,Math.max(40,r.startH+(e.clientY-r.startY))));
   r.value=v;r.inner.style.minHeight=v+'px';
   setStatus(`Height ${v}px. Release to keep, double-click the handle for content-based height.`);
  }else if(r.kind==='divider'){
   const widthI=r.leftFirst?e.clientX-r.pairStart:r.pairStart+r.pairWidth-e.clientX;
   const frac=Math.min(0.88,Math.max(0.12,widthI/r.pairWidth));
   const i=r.index,sum=r.tracks[i]+r.tracks[i+1];
   const next=[...r.tracks];next[i]=+(sum*frac).toFixed(2);next[i+1]=+(sum*(1-frac)).toFixed(2);
   r.value=next;
   r.inner.style.gridTemplateColumns=next.map(v=>v+'fr').join(' ');
   setStatus(`Column ratio ${next.map(v=>v+' fr').join(' /')} fr. Release to keep, double-click the divider for equal widths.`);
  }else if(r.kind==='width'){
   const w=r.edge==='right'?e.clientX-r.anchorX:r.anchorX-e.clientX;
   const pct=Math.round(Math.min(100,Math.max(10,w/r.parentWidth*100)));
   r.value=pct;r.inner.style.width=pct+'%';
   setStatus(`Width ${pct}%. Release to keep, double-click the side handle for full width.`);
  }
 };
 const endResize=()=>{
  const r=resizeRef.current;if(!r)return;
  resizeRef.current=null;
  if(r.kind==='height')onSetting(r.id,'min_height_px',r.value);
  else if(r.kind==='width')onSetting(r.id,'width_pct',r.value);
  else onSetting(r.id,'tracks',(r.value as number[]).map(v=>+v.toFixed(2)));
  setStatus('Size saved to this device. Unsaved page changes remain until you save.');
 };
 const resetResize=(field:'min_height_px'|'tracks'|'width_pct')=>{
  onSetting(selected,field,null);
  setStatus(field==='tracks'?'Columns back to equal widths.':field==='width_pct'?'Back to full width.':'Back to content-based height.');
 };
 return <div className="native-dnd"><div className="native-palette" aria-label="Selection actions">{paletteHost?createPortal(<div className="native-element-grid">{['columns','card','column','heading','text','image','button'].map(type=><button key={type} style={{touchAction:'none'}} onPointerDown={e=>begin({kind:'new',type},e)} onClick={()=>{if(suppressClick.current)return;setPick({kind:'new',type});setStatus('Choose a compatible Insert here position below.')}}>+ {uiLang==='ar'?readableTypeAr(type):readableType(type)}</button>)}</div>,paletteHost):null}</div><nav className="native-breadcrumb" aria-label="Selected node ancestors">{ancestors.map((n,i)=><span key={n.id}>{i>0&&' ← '}<button aria-current={n.id===selected?'true':undefined} onClick={()=>onSelect(n.id)}>{readableName(n,lang??'en')}</button></span>)}</nav>{status&&<p className="native-dnd-status mz-sr" role="status">{status}</p>}{pick&&!feedback&&<details className="native-drop-options" open><summary>Choose insertion position for {pick.type}</summary>{nodes.filter(n=>allowed(n,pick)).map(n=><div key={n.id}><b>{readableType(n.type)} · {readableName(n)}</b>{Array.from({length:(n.children?.length??0)+1},(_,index)=><button key={index} onClick={()=>apply(pick,{parentId:n.id,index})}>Insert here, position {index+1} in {readableName(n)}</button>)}</div>)}<button onClick={()=>{setPick(null);setStatus('Move cancelled.')}}>Cancel move</button></details>}<div ref={canvas} className="native-drag-preview" onPointerMove={e=>{if(tap.current)tap.current=trackTapMove(tap.current,e.pointerId,e.clientX,e.clientY);if(active.current)return;const el=(e.target as HTMLElement).closest<HTMLElement>('.mz-node');setHover(el?sourceId(el.id):'')}} onPointerLeave={()=>setHover('')} onPointerDown={e=>{const el=(e.target as HTMLElement).closest<HTMLElement>('.mz-node');const n=nodes.find(n=>n.id===(el?sourceId(el.id):''));if(!n)return;const repeated=!!(el&&sourceId(el.id)!==el.id);if(e.pointerType==='touch'){tap.current=beginTapGesture(e.pointerId,e.clientX,e.clientY,n.id,repeated);return;}if(repeated){onSelect(n.id);setStatus('Editing the repeated template. Layout changes apply to all copies. Move it through Layers.');return;}if(n.id===tree.id)onSelect(n.id);else begin({kind:'node',id:n.id,type:n.type},e)}} onPointerUp={e=>{const t=tap.current;if(!t||e.pointerId!==t.pointerId)return;tap.current=null;if(!isTapRelease(t,e.pointerId))return;onSelect(t.nodeId);if(t.repeated)setStatus('Editing the repeated template. Layout changes apply to all copies. Move it through Layers.')}} onPointerCancel={e=>{if(tap.current&&e.pointerId===tap.current.pointerId)tap.current=null}}>{children}</div>{!feedback&&handles.height&&createPortal(<><button type="button" className="native-resize-handle" style={{left:handles.height.x,top:handles.height.y}} aria-label="Drag to set height in pixels. Double-click for content-based height." onPointerDown={beginHeight} onPointerMove={moveResize} onPointerUp={endResize} onDoubleClick={()=>resetResize('min_height_px')}/>{hasMinH&&<button type="button" className="native-resize-reset" style={{left:handles.height.x+16,top:handles.height.y}} onClick={()=>resetResize('min_height_px')}>↺ Auto height</button>}{handles.sides&&<><button type="button" className="native-side-handle" style={{left:handles.sides.left.x-5,top:handles.sides.left.y-17}} aria-label="Drag the left edge to resize width. Double-click for content-based width." onPointerDown={e=>beginWidth(e,'left')} onPointerMove={moveResize} onPointerUp={endResize} onDoubleClick={()=>resetResize('width_pct')}/><button type="button" className="native-side-handle" style={{left:handles.sides.right.x-5,top:handles.sides.right.y-17}} aria-label="Drag the right edge to resize width. Double-click for content-based width." onPointerDown={e=>beginWidth(e,'right')} onPointerMove={moveResize} onPointerUp={endResize} onDoubleClick={()=>resetResize('width_pct')}/></>}{hasWidthPct&&handles.sides&&<button type="button" className="native-resize-reset" style={{left:handles.sides.right.x+10,top:handles.sides.right.y-10}} onClick={()=>resetResize('width_pct')}>↺ Full width</button>}{handles.dividers?.map(d=><button type="button" key={d.index} className="native-divider-handle" style={{left:d.x,top:d.y,height:d.h}} aria-label="Drag to change the column ratio. Double-click for equal widths." onPointerDown={e=>beginDivider(e,d.index)} onPointerMove={moveResize} onPointerUp={endResize} onDoubleClick={()=>resetResize('tracks')}/>)}{hasTracks&&handles.dividers?.[0]&&<button type="button" className="native-resize-reset" style={{left:handles.dividers[0].x+12,top:handles.dividers[0].y}} onClick={()=>resetResize('tracks')}>↺ Equal widths</button>}</>,document.body)}{feedback&&createPortal(<div className="native-drag-feedback" aria-live="polite"><div className={`native-drag-ghost ${feedback.valid?'valid':'invalid'}`} style={{left:feedback.x,top:feedback.y}}><b>⠿ {feedback.label}</b><span>{feedback.sample}</span><small>{feedback.valid?'✓ '+feedback.destination:'⊘ '+feedback.destination}</small></div>{drop&&<><div className="native-drop-region" style={{left:drop.box.x,top:drop.box.y,width:drop.box.width,height:drop.box.height}}/><div className="native-drop-marker" data-parent-id={drop.parentId} data-insert-index={drop.index} style={{left:drop.x,top:drop.y,width:drop.width,height:drop.height}}><span>{drop.label}</span></div></>}</div>,document.body)}</div>;
}
