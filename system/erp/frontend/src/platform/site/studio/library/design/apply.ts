import {chromeProblems} from '../../sharedChrome';
import type {SiteSettingsValue} from '../../sitePages';
import {designIdentities} from './identities';
/** Stage only existing supported site tokens. Never touches page trees or ERP theme choices. */
export function stageDesignIdentity(value:SiteSettingsValue,id:string):SiteSettingsValue{
 if(chromeProblems(value).filter(p=>!p.startsWith('Increase contrast')).length)throw Error('Current shared settings need a supported lossless format before applying a design identity.');
 const design=designIdentities.find(d=>d.id===id);if(!design)throw Error('Unknown site design identity.');
 return {...structuredClone(value),colors:{light:{...design.palette}},typography:{...design.typography},shape:{radius:design.radius}};
}
