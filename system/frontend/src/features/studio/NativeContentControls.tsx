import { useEffect, useRef, useState } from 'react';
import type { PageNode } from './pagetree';
import { nativeContentFields, safeNativeUrl } from './nativeTree';
import { sanitizeHtml } from './treerender';
import {t} from './uiStrings';

export default function NativeContentControls({node,lang,onEdit}:{node:PageNode;lang:'en'|'ar';onEdit:(field:string,value:string)=>void}){
  const rich=useRef<HTMLDivElement>(null);
  const [urlError,setUrlError]=useState('');
  const ar=true; // Arabic-first UI chrome, content lang suffix kept
  const content=node.content[lang]??{};
  const html=String(content.html??'');
  useEffect(()=>{if(rich.current && sanitizeHtml(rich.current.innerHTML)!==sanitizeHtml(html))rich.current.innerHTML=sanitizeHtml(html)},[node.id,lang,html]);
  const commitRich=()=>{if(!rich.current)return;const next=sanitizeHtml(rich.current.innerHTML);if(next!==sanitizeHtml(html))onEdit('html',next);};
  return <div className="native-content-controls">
    {node.type==='text'&&<div className="native-rich"><label>{ar?t('النص'):'Text'} · {lang}</label><div className="native-rich-toolbar">{[[ar?t('عريض'):'Bold','bold'],[ar?t('مائل'):'Italic','italic'],[ar?t('نقاط'):'Bullets','insertUnorderedList']] .map(([label,command])=><button type="button" key={command} onMouseDown={e=>e.preventDefault()} onClick={()=>{rich.current?.focus();document.execCommand(command);commitRich()}}>{label}</button>)}</div><div ref={rich} contentEditable role="textbox" aria-label="Native rich text" aria-multiline="true" suppressContentEditableWarning onInput={commitRich}/><p className="hint">{ar?t('عدّل النص مباشرة. التنسيق المحفوظ بيفضل زي ما هو لحد ما تعدّل الحقل ده.'):'Edit text directly. Existing stored markup stays unchanged until you edit this field.'}</p></div>}
    {Object.entries(nativeContentFields(node.type)).filter(([field])=>field!=='html').map(([field,max])=>{
      const label=!ar?(field==='src'?'Image address':field==='alt'?'Image description':field==='href'?'Link destination':field==='label'?'Button text':'Heading text'):(field==='src'?t('عنوان الصورة'):field==='alt'?t('وصف الصورة'):field==='href'?t('وجهة الرابط'):field==='label'?t('نص الزر'):t('نص العنوان'));
      if(field==='src'||field==='href')return <label key={field}>{label} · {lang}<input key={`${node.id}-${lang}-${field}-${String(content[field])}`} aria-label={`Native ${field}`} defaultValue={String(content[field]??'')} maxLength={max} placeholder={field==='src'?'https://... or /media/...':'/page or https://...'} onBlur={e=>{if(!safeNativeUrl(e.target.value,field==='src')){setUrlError(ar?t('العنوان مرفوض. الوجهة المحفوظة ما اتغيرتش.'):'Address refused. The stored destination is unchanged.');return;}setUrlError('');onEdit(field,e.target.value)}}/>{urlError&&<span className="link-error" role="status">{urlError}</span>}<small>{ar?t('بيتحفظ لما تسيب الحقل. مفيش رفع ملفات ولا شراء.'):'Applied when you leave the field. No file upload or purchase.'}</small></label>;
      return <label key={field}>{label} · {lang}<textarea aria-label={`Native ${field}`} maxLength={max} value={String(content[field]??'')} onChange={e=>onEdit(field,e.target.value)}/></label>;
    })}
    {node.type==='image'&&typeof content.src==='string'&&content.src&&safeNativeUrl(content.src,true)&&<img className="native-media-thumbnail" src={content.src} alt={String(content.alt??(ar?t('معاينة الصورة'):'Image preview'))}/>}
  </div>;
}
