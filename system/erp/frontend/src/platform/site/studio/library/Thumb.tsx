// Shared live-rendering thumbnail for library assets: renders the real preset or
// template tree through the site renderer, scaled to fit the card.
import {useEffect,useMemo,useRef} from 'react';
import TreePreview,{type ThemeSpec} from '../treerender';
import type {PageNode} from '../pagetree';
import {createPreset,createTemplate,type PresetKind,type TemplateKind} from '../nativePresets';
export default function AssetThumb({tree,preset,template,theme}:{tree:PageNode;preset?:PresetKind;template?:TemplateKind;theme?:ThemeSpec}){
 const previewTree=useMemo(()=>{
  const key=preset??template??'asset';
  const unique=(n:PageNode):PageNode=>({...n,id:`thumb_${key}_${n.id}`,...(n.children?{children:n.children.map(unique)}:{})});
  const body=preset?createPreset(tree,preset):createTemplate(tree,template as TemplateKind);
  return unique({...tree,children:body.children??[body]});
 },[tree,preset,template]);
 const host=useRef<HTMLDivElement>(null),page=useRef<HTMLDivElement>(null);
 useEffect(()=>{const fit=()=>{if(!host.current||!page.current)return;const scale=Math.min(host.current.clientWidth/760,138/Math.max(1,page.current.scrollHeight));page.current.style.transform=`scale(${scale})`;page.current.style.left=`${Math.max(0,(host.current.clientWidth-760*scale)/2)}px`};const observer=new ResizeObserver(fit);if(host.current)observer.observe(host.current);if(page.current)observer.observe(page.current);fit();return()=>observer.disconnect()},[previewTree,theme]);
 return <div ref={host} className="library-real-thumbnail" aria-hidden="true" data-block-thumbnail={preset??template}><div ref={page} className="library-thumbnail-page preview-frame"><TreePreview tree={previewTree} theme={theme} lang="en" device="desktop"/></div></div>;
}
