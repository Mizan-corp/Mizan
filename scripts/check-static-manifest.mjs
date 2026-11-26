#!/usr/bin/env node
// Predeploy guard: assert the isolated host's static/ tree still contains every
// entry the site needs before `vercel deploy` runs. A sync tool running with
// --delete (or a partial build) must fail this check, not ship a broken site.
import {existsSync,statSync} from 'node:fs';
import {join} from 'node:path';
const dir=process.argv[2];
if(!dir){console.error('usage: check-static-manifest.mjs <static-dir>');process.exit(2)}
const required=[
 'index.html','studio-preview.html','sw.js','manifest.webmanifest','icon.svg',
 'assets','fonts','studio-assets',
 'studio','studio/studio.html',
 'admin','admin/index.html','erp','erp/index.html','website','website/index.html','owner','owner/index.html',
];
const missing=required.filter(rel=>{const p=join(dir,rel);if(!existsSync(p))return true;const isDir=statSync(p).isDirectory();return rel.includes('.')?isDir:!isDir});
// entry HTML files must reference only asset files that exist on disk
import {readFileSync,readdirSync} from 'node:fs';
const broken=[];
for(const entry of ['index.html','studio-preview.html','studio/studio.html']){
 const p=join(dir,entry);if(!existsSync(p))continue;
 const html=readFileSync(p,'utf8');
 for(const m of html.matchAll(/(?:src|href)="\/(assets\/[^"]+|studio-assets\/[^"]+)"/g)){
  if(!existsSync(join(dir,m[1])))broken.push(entry+' -> '+m[1]);
 }
}
if(missing.length||broken.length){
 console.error('DEPLOY BLOCKED. missing:',missing.join(', ')||'none','| broken asset refs:',broken.join(', ')||'none');
 process.exit(1);
}
console.log('static manifest OK:',required.length,'entries present, entry asset refs resolve');
