import {describe,it,expect} from 'vitest';
import {newPagePayload} from './newPage';
import {assertNativeTree,nativeNodes} from './nativeTree';
describe('new native page',()=>{
 it('creates editable S2 content with exact independent title and address',()=>{const p=newPagePayload({title:'  My page  ',slug:'my-page',language:'en'});assertNativeTree(p.tree);expect(p.titles).toEqual({en:'My page'});expect(p.slug).toBe('my-page');expect(nativeNodes(p.tree).at(-1)?.content.en).toEqual({text:'My page'});});
 it('preserves Arabic without inventing a transliterated address',()=>{const p=newPagePayload({title:'صفحتي',slug:'about-us',language:'ar'});assertNativeTree(p.tree);expect(p.titles).toEqual({ar:'صفحتي'});expect(nativeNodes(p.tree).at(-1)?.content.ar).toEqual({text:'صفحتي'});});
 it('allocates distinct ids without reusing existing page identity',()=>{const input={title:'One',slug:'one',language:'en' as const};const a=newPagePayload(input),b=newPagePayload(input);const ids=[...nativeNodes(a.tree),...nativeNodes(b.tree)].map(n=>n.id);expect(new Set(ids).size).toBe(ids.length);});
 it('refuses empty, excessive and invalid input instead of fixing silently',()=>{for(const title of ['', ' '.repeat(5),'x'.repeat(121)])expect(()=>newPagePayload({title,slug:'valid',language:'en'})).toThrow();for(const slug of ['','UPPER','a b','/about','a--b','-abc','abc-','x'.repeat(81)])expect(()=>newPagePayload({title:'Title',slug,language:'en'})).toThrow();});
});
