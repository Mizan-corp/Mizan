import { describe, expect, it } from 'vitest';
import { previewConfig, HOSTED_API } from './previewConfig';
describe('isolated preview configuration', () => {
 it('allows only a fixed same-origin session API', () => {
  expect(previewConfig({apiBase:'/api',label:'Isolated test workspace'})).toEqual({apiBase:'/api',label:'Isolated test workspace'});
 });
 it('rejects arbitrary hosts, tokens and URL configuration', () => {
  for(const value of [null, [], {}, {apiBase:'https://example.test',label:'Test'}, {apiBase:'//example.test',label:'Test'}, {apiBase:'/api',label:'Test',token:'no'}, {apiBase:'/api',label:'<script>'}, {apiBase:'/__studio/api',label:'Test'}]) expect(()=>previewConfig(value)).toThrow();
 });
 it('does not mutate the supplied data', () => {
  const value=Object.freeze({apiBase:'/api',label:'Preview'});expect(previewConfig(value)).toEqual(value);
 });
 it('allows exactly the production API origin for single sign-on, nothing near it', () => {
  expect(previewConfig({apiBase:HOSTED_API,label:'Mizan Studio'}).apiBase).toBe(HOSTED_API);
  for(const apiBase of ['https://api.allmizan.live','https://api.allmizan.live/api/','https://api.allmizan.live.evil.test/api','http://api.allmizan.live/api','https://evil.test/api']) expect(()=>previewConfig({apiBase,label:'Test'})).toThrow();
 });
});
