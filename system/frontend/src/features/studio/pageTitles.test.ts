import {describe,it,expect} from 'vitest';
import {updatedPageTitles,pageTitlesKey} from './pageTitles';
describe('page titles',()=>{
 it('changes only selected language and never mutates input',()=>{const a={en:'About',ar:'عن الشركة'};expect(updatedPageTitles(a,'en','  About us  ')).toEqual({en:'About us',ar:'عن الشركة'});expect(a.en).toBe('About');});
 it('adds Arabic title without discarding English',()=>expect(updatedPageTitles({en:'About'},'ar','عنا')).toEqual({en:'About',ar:'عنا'}));
 it('refuses blank and overlong titles',()=>{for(const t of ['', '  ','x'.repeat(121)])expect(()=>updatedPageTitles({},'en',t)).toThrow();});
 it('compares independent of insertion order',()=>expect(pageTitlesKey({en:'A',ar:'ب'})).toBe(pageTitlesKey({ar:'ب',en:'A'})));
});
