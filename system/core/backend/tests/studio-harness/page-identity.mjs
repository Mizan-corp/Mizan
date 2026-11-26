// CDP driver: studio UI edit -> authenticated API save -> reload restoration, fail-closed
// error path, and local-test publish. Runs against the local vite studio + local test API.
import { writeFileSync } from 'node:fs';

const CHROME = 'http://127.0.0.1:9222';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function newTab() {
  for (let i = 0; i < 30; i++) {
    try {
      const r = await fetch(`${CHROME}/json/new?about:blank`, { method: 'PUT' });
      return await r.json();
    } catch { await sleep(500); }
  }
  throw new Error('chrome devtools not reachable');
}

const target = await newTab();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let seq = 0;
const pending = new Map();
const events = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  else if (msg.method) events.push(msg);
};
function send(method, params = {}) {
  const id = ++seq;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise(res => pending.set(id, res));
}
async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error('page error: ' + JSON.stringify(r.result.exceptionDetails).slice(0, 300));
  return r.result?.result?.value;
}
async function shot(path) {
  const r = await send('Page.captureScreenshot', { format: 'png', fromSurface: true });
  writeFileSync(path, Buffer.from(r.result.data, 'base64'));
}
async function waitFor(expression, tries = 30) {
  for (let i = 0; i < tries; i++) {
    if (await evaluate(expression)) return true;
    await sleep(500);
  }
  const notice = await evaluate(`document.querySelector('.studio-notice')?.textContent`);
  const buttons = await evaluate(`[...document.querySelectorAll('button')].map(b => b.textContent).join(' | ')`);
  console.log('DEBUG notice:', notice);
  console.log('DEBUG buttons:', buttons);
  await shot((process.env.STUDIO_OUT || '/downloads') + '/e2e-debug.png');
  throw new Error('timeout waiting for: ' + expression.slice(0, 80));
}

await send('Page.enable');
await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });




await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html'});
await waitFor(`!!document.querySelector('.studio-inspector')`);
const tree=await evaluate(`(async()=>{const {toPageTree}=await import('/src/features/studio/pagetree.ts');const {initialProject}=await import('/src/features/studio/model.ts');return toPageTree(initialProject)})()`);
await send('Page.addScriptToEvaluateOnNewDocument',{source:`
window.__writes=[];window.__release=null;localStorage.clear();
window.fetch=async (url,init={})=>{
 const path=String(url);const mode=new URL(location.href).searchParams.get('mock');
 const page={id:'stable-id',slug:'original-address',titles:{en:'Independent title'},status:'draft',draft_tree:${JSON.stringify(tree)},published_tree:null};
 if(init.method && init.method!=='GET')window.__writes.push({path,method:init.method,body:JSON.parse(init.body||'{}')});
 let body={};let status=200;
 if(path.endsWith('/site/pages')){
  if(init.method==='POST'){status=409;body={detail:'Conflict'};}
  else {if(mode==='slow')await new Promise(r=>window.__release=r);body={items:mode==='conflict'?[]:mode==='many'?[page,{...page,id:'other'}]:[page]};}
 }else if(path.endsWith('/site/settings'))body={value:{header:{brand:'Changed global brand'}}};
 else body=page;
 return new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
};`});
await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html?mock=slow&page=stable-id'});
await waitFor(`!!window.__release`);
if(!(await evaluate(`document.querySelector('.studio-workspace').inert && document.querySelector('.top-actions').inert && [...document.querySelectorAll('.top-actions button')].every(b=>b.disabled)`)))throw Error('loading not guarded');
await shot((process.env.STUDIO_OUT||'/downloads')+'/studio-page-loading.png');
await evaluate(`window.__release()`);
await waitFor(`document.querySelector('.studio-notice').textContent.includes('Loaded the draft')`);
if(!(await evaluate(`document.querySelector('.project-name').textContent.includes('Changed global brand') && location.search.includes('page=stable-id')`)))throw Error('identity/brand restore failed');
await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Save to local backend').click()`);await sleep(400);
if(!(await evaluate(`window.__writes.some(w=>w.path.endsWith('/stable-id/draft')&&w.body.titles.en==='Independent title') && !window.__writes.some(w=>w.method==='POST')`)))throw Error('save changed identity/title');
await shot((process.env.STUDIO_OUT||'/downloads')+'/studio-stable-page.png');
await send('Page.reload');await sleep(500);await waitFor(`!!window.__release`);await evaluate(`window.__release()`);await waitFor(`document.querySelector('.studio-notice').textContent.includes('Loaded the draft')`);
for(const query of ['mock=many','page=missing']){
 await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html?'+query});await sleep(400);await waitFor(`!!document.querySelector('.studio-protection')`);
 if(!(await evaluate(`window.__writes.length===0`)))throw Error('blocked selection wrote data');
}
await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html?mock=conflict'});await sleep(400);await waitFor(`document.querySelector('.studio-notice').textContent.includes('Connected')`);
await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Save to local backend').click()`);await waitFor(`!!document.querySelector('.studio-protection')`);
if(!(await evaluate(`window.__writes.length===1&&window.__writes[0].method==='POST'`)))throw Error('conflict adopted existing target');
console.log('PASS mocked identity: guarded delayed load, changed brand and independent title, stable save/reload, ambiguous/stale targets blocked, create conflict no overwrite');ws.close();
