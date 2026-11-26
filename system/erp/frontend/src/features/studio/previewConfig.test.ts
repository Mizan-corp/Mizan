import { describe, expect, it } from 'vitest';
import { previewConfig } from './previewConfig';
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
});
