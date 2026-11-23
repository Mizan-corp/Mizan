import {nativeTreeKey,safeNativeUrl} from './nativeTree';
import type {SiteSettingsValue} from './sitePages';
export type ChromePart='header'|'footer';
export type ChromeVariant='header_inline'|'header_centered'|'footer_split'|'footer_stacked';
export const chromeCatalog:{id:ChromeVariant;part:ChromePart;name:string}[]=[{id:'header_inline',part:'header',name:'Inline navigation'},{id:'header_centered',part:'header',name:'Centered navigation'},{id:'footer_split',part:'footer',name:'Split footer'},{id:'footer_stacked',part:'footer',name:'Stacked footer'}];
export function chromePreset(value:SiteSettingsValue,variant:ChromeVariant):SiteSettingsValue{
 const next=structuredClone(value);
 if(variant.startsWith('header_'))next.header={...next.header,brand:next.header?.brand??'Your brand',links:next.header?.links??[{label:'About',href:'/about'},{label:'Contact',href:'/contact'}],actions:next.header?.actions??[],layout:variant==='header_centered'?'centered':'inline'};
 else next.footer={...next.footer,lines:next.footer?.lines??['Your brand. Your story.'],links:next.footer?.links??[{label:'Contact',href:'/contact'}],layout:variant==='footer_stacked'?'stacked':'split'};
 return next;
}
/** Refuse a lossy shared save. Unknown metadata stays in memory but is not silently dropped by API normalization. */
export function chromeProblems(value:SiteSettingsValue):string[]{
 const errors:string[]=[];
 const contrast=(a:string,b:string)=>{const luminance=(hex:string)=>{const c=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*c[0]+.7152*c[1]+.0722*c[2]};const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
 const light=value.colors?.light;
 if(light)for(const [fg,bg]of [['foreground','background'],['foreground','card'],['primary-foreground','primary']]){const a=light[fg],b=light[bg];if(a&&b&&/^#[0-9a-fA-F]{6}$/.test(a)&&/^#[0-9a-fA-F]{6}$/.test(b)&&contrast(a,b)<4.5)errors.push('Increase contrast between '+fg+' and '+bg+' to at least 4.5:1.');}

 const normalized=structuredClone(value);
 for(const part of ['header','footer']as const){const s=value[part];if(s)normalized[part]=(part==='header'?{brand:(value.header?.brand??'').trim(),links:value.header?.links??[],actions:value.header?.actions??[],...(value.header?.layout?{layout:value.header.layout}:{})}:{lines:value.footer?.lines??[],links:value.footer?.links??[],...(value.footer?.layout?{layout:value.footer.layout}:{})})as never;}
 if(nativeTreeKey(normalized)!==nativeTreeKey(value))errors.push('Shared settings are not in the supported lossless format.');

 if(value.colors&&(Object.keys(value.colors).some(k=>k!=='light')||!value.colors.light||Object.entries(value.colors.light).some(([k,v])=>!['background','foreground','card','primary','primary-foreground'].includes(k)||!/^#[0-9a-fA-F]{6}$/.test(v))))errors.push('Shared colors contain unsupported values.');
 if(value.typography&&(Object.keys(value.typography).some(k=>k!=='family')||!['sans-serif','serif','monospace'].includes(value.typography.family??'')))errors.push('Shared typography is not supported.');
 if(value.shape&&(Object.keys(value.shape).some(k=>k!=='radius')||!Number.isInteger(value.shape.radius)||value.shape.radius!<0||value.shape.radius!>64))errors.push('Shared shape is not supported.');

 if(Object.keys(value).some(k=>!['header','footer','colors','typography','shape'].includes(k)))errors.push('Shared settings contain fields this editor cannot preserve.');
 for(const part of ['header','footer'] as const){const section=value[part];if(!section)continue;
  if(Object.keys(section).some(k=>!(part==='header'?['brand','links','actions','layout']:['lines','links','layout']).includes(k)))errors.push('Shared '+part+' has unsupported fields.');
  for(const field of part==='header'?['links','actions']:['links']){const links=(section as Record<string,unknown>)[field];if(links!==undefined&&(!Array.isArray(links)||links.length>(field==='actions'?4:8)||links.some(l=>!l||Object.keys(l).some(k=>!['label','href'].includes(k))||typeof l.label!=='string'||l.label!==l.label.trim()||!l.label.trim()||l.label.length>40||typeof l.href!=='string'||l.href.length>200||!safeNativeUrl(l.href)||!(/^(\/|#|https:\/\/)/.test(l.href)))))errors.push('Use a label and safe /path, #anchor or https:// link for every '+field+'.');}
 }
 if(value.header?.brand!==undefined&&(value.header.brand.length>80||value.header.brand!==value.header.brand.trim()))errors.push('Brand must have no outer spaces and at most 80 characters.');
 if(value.header?.layout&&!['inline','centered'].includes(value.header.layout))errors.push('Unsupported header layout.');
 if(value.footer?.layout&&!['split','stacked'].includes(value.footer.layout))errors.push('Unsupported footer layout.');
 if((value.footer?.lines?.length??0)>4)errors.push('Use at most four footer lines.');
 if(value.footer?.lines?.some(l=>!l.trim()||l.length>120||l!==l.trim()))errors.push('Footer lines must be 1-120 characters without outer spaces.');
 return errors;
   }
