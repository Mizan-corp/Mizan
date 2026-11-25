// @vitest-environment jsdom
import {it,expect,vi,beforeEach,afterEach} from 'vitest';
import {createElement as h} from 'react';
import {render,fireEvent,waitFor,cleanup} from '@testing-library/react';
import WebsiteHelpdeskSettings from './WebsiteHelpdeskSettings';
import {setUILang} from './uiStrings';

// Pins the Help Desk website selection consent: names only, signed-in previews
// plus per-page publish approval, no description/amount/currency/internal data,
// no booking/payment, and the save payload shape (expected_token + offerings).

const publication={value:{offerings:['o1']},edit_token:'tok1'};
const choices={offerings:{items:[{id:'o1',name:'صيانة تكييف'},{id:'o2',name:'دعم أجهزة'}],truncated:false}};
let confirmText='';
let puts:Array<{path:string;body:unknown}>=[];
let failWith=0;

function fetchMock(input:RequestInfo|URL,init?:RequestInit){
 const path=String(input).replace(/^https?:\/\/[^/]+/,'');
 if(failWith)return Promise.resolve(new Response('x',{status:failWith}));
 if(init?.method==='PUT'){const body=JSON.parse(String(init.body));puts.push({path,body});const {expected_token,...value}=body;return Promise.resolve(new Response(JSON.stringify({value,edit_token:'tok2'}),{status:200}))}
 if(path.endsWith('/choices'))return Promise.resolve(new Response(JSON.stringify(choices),{status:200}));
 if(path.endsWith('/site/module-settings/helpdesk'))return Promise.resolve(new Response(JSON.stringify(publication),{status:200}));
 return Promise.resolve(new Response('{}',{status:404}));
}

beforeEach(()=>{
 setUILang('ar');
 puts=[];confirmText='';failWith=0;
 vi.stubGlobal('fetch',fetchMock);
 vi.stubGlobal('confirm',(text:string)=>{confirmText=text;return true});
});
afterEach(()=>{cleanup();vi.unstubAllGlobals()});

it('selects service names and saves with the pinned consent wording',async()=>{
 const {getByLabelText,getByRole}=render(h(WebsiteHelpdeskSettings,{apiBase:'https://api.test',onDirty:()=>{},onSaved:()=>{}}));
 await waitFor(()=>expect(getByLabelText('Service دعم أجهزة')).toBeTruthy());
 // pre-selected offering renders checked
 expect((getByLabelText('Service صيانة تكييف') as HTMLInputElement).checked).toBe(true);
 fireEvent.click(getByLabelText('Service دعم أجهزة'));
 fireEvent.click(getByRole('button',{name:'احفظ اختيار خدمات الموقع'}));
 await waitFor(()=>expect(puts).toHaveLength(1));
 expect(confirmText).toContain('أسماء الخدمات المختارة بس');
 expect(confirmText).toContain('معاينات الموقع المقفولة بحسابك');
 expect(confirmText).toContain('حوار النشر');
 expect(confirmText).toContain('الوصف وسعر البداية والعملة والملاحظات الداخلية وطلبات العمل مش بتظهر أبدًا');
 expect(confirmText).toContain('مش بيفعّل حجز أو دفع');
 expect(confirmText).toContain('only the selected service names');
 expect(confirmText).toContain('signed-in website previews');
 expect(confirmText).toContain('does not enable booking or payment');
 expect(puts[0].body).toEqual({expected_token:'tok1',offerings:['o1','o2']});
});

it('shows an unavailable note instead of breaking when Help Desk is inactive (422)',async()=>{
 failWith=422;
 const {container}=render(h(WebsiteHelpdeskSettings,{apiBase:'https://api.test',onDirty:()=>{},onSaved:()=>{}}));
 await waitFor(()=>expect(container.textContent).toContain('مكتب الخدمات مش متفعّل في مساحة العمل دي'));
 expect(container.querySelector('fieldset')!.disabled).toBe(true);
});
