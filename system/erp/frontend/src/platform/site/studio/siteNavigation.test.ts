import {it,expect} from 'vitest';
import {selectedPageAddress} from './siteNavigation';
import type {PageSummary} from './sitePages';
const page={id:'one',slug:'about-us',titles:{en:'About'},status:'draft',has_draft:true,published:false,created_at:null,updated_at:null} as PageSummary;
it('stages exact source address, preserves title/source and does not infer publication',()=>{const before=structuredClone(page);expect(selectedPageAddress([page],'one')).toBe('/about-us');expect(page).toEqual(before);expect(page.published).toBe(false)});
it('refuses unknown, duplicate, archived, missing-tree and malformed addresses',()=>{expect(()=>selectedPageAddress([],'one')).toThrow();expect(()=>selectedPageAddress([page,page],'one')).toThrow();for(const patch of [{status:'archived'},{status:'other'},{has_draft:false},{slug:'//elsewhere'},{slug:'../private'},{slug:'two words'},{slug:'a'.repeat(81)}])expect(()=>selectedPageAddress([{...page,...patch} as PageSummary],'one')).toThrow()});
