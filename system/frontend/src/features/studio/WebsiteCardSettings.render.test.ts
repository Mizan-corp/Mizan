// @vitest-environment jsdom
import {it,expect,vi,beforeEach,afterEach} from 'vitest';
import {createElement as h} from 'react';
import {render,fireEvent,waitFor,cleanup} from '@testing-library/react';
import WebsiteCardSettings from './WebsiteCardSettings';
import {setUILang} from './uiStrings';

// Regression: the localization commit 1a4206c corrupted the currency select
// (fallback value became the literal 't(' and the EGP option became ')EGP'),
// making EGP unselectable on the deployed test host. Also pins the v3 consent
// wording: cards, repeating lists AND individually bound elements,
// authenticated previews only, no publication/checkout, and the save payload
// shape including the explicit consent_version acknowledgement. Pins the v4
// wording: v3 surfaces plus URL-selected detail pages, category linkage and
// the explicit description field.

const policy={products:['p1'],show_price:false,show_image:false,show_description:false,currency:null};
const choices={products:{items:[{id:'p1',name:'Widget'}]}};
let confirmText='';
let puts:Array<{path:string;body:unknown}>=[];

function fetchMock(input:RequestInfo|URL,init?:RequestInit){
 const path=String(input).replace(/^https?:\/\/[^/]+/,'');
 if(init?.method==='PUT'){const body=JSON.parse(String(init.body));puts.push({path,body});const {expected_token,consent_version,...value}=body;return Promise.resolve(new Response(JSON.stringify({value,edit_token:'tok2'}),{status:200}))}
 if(path.endsWith('/cards'))return Promise.resolve(new Response(JSON.stringify({value:policy,edit_token:'tok1'}),{status:200}));
 if(path.endsWith('/choices'))return Promise.resolve(new Response(JSON.stringify(choices),{status:200}));
 return Promise.resolve(new Response('{}',{status:404}));
}

beforeEach(()=>{
 setUILang('ar');
 puts=[];confirmText='';
 vi.stubGlobal('fetch',fetchMock);
 vi.stubGlobal('confirm',(text:string)=>{confirmText=text;return true});
});
afterEach(()=>{cleanup();vi.unstubAllGlobals()});

it('currency select offers real EGP with an empty fallback and saves the consent',async()=>{
 const {container,getByLabelText,getByRole}=render(h(WebsiteCardSettings,{apiBase:'https://api.test',onDirty:()=>{},onSaved:()=>{}}));
 await waitFor(()=>expect(getByLabelText('Card product Widget')).toBeTruthy());
 // Opt into prices: the currency select appears.
 fireEvent.click(getByLabelText('السماح بأسعار عرض للموقع'));
 const select=getByLabelText('عملة العرض في الموقع') as HTMLSelectElement;
 const values=Array.from(select.options).map(o=>o.value);
 expect(values).toContain('EGP');
 expect(values).not.toContain(')EGP');
 expect(select.value).toBe('');
 // Saving without an explicit currency is refused locally.
 fireEvent.click(getByRole('button',{name:'احفظ سياسة عرض منتجات الموقع'}));
 expect(puts).toHaveLength(0);
 // Choose EGP and save: confirm wording covers cards + repeating lists,
 // authenticated previews only, no publication/checkout.
 fireEvent.change(select,{target:{value:'EGP'}});
 fireEvent.click(getByRole('button',{name:'احفظ سياسة عرض منتجات الموقع'}));
 await waitFor(()=>expect(puts).toHaveLength(1));
 expect(confirmText).toContain('repeating product lists');
 expect(confirmText).toContain('individually bound elements');
 expect(confirmText).toContain('القوائم المتكررة');
 expect(confirmText).toContain('العناصر المربوطة منفردة');
 expect(confirmText).toContain('signed-in website previews');
 expect(confirmText).toContain('product detail page reads the product whose ID is in the URL');
 expect(confirmText).toContain('category pages show the selected products belonging to each published category');
 expect(confirmText).toContain('Description shows only if you check its box');
 expect(confirmText).toContain('صفحة تفاصيل المنتج');
 expect(confirmText).toContain('صفحات التصنيفات');
 expect(confirmText).toContain('does not enable checkout');
 expect(confirmText).toContain('مش بيفعّل الدفع');
 expect(puts[0].body).toEqual({expected_token:'tok1',consent_version:'mizan.inventory-website-cards.experimental.v4',products:['p1'],show_price:true,show_image:false,show_description:false,currency:'EGP'});
 expect(container.textContent).toContain('الدفع يفضل غير متاح');
});
