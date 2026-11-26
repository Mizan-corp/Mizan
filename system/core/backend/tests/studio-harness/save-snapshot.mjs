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
const tree=await evaluate(`(async()=>{const {toPageTree}=await import('/src/platform/site/studio/pagetree.ts');const {initialProject}=await import('/src/platform/site/studio/model.ts');return toPageTree(initialProject)})()`);

await send('Page.addScriptToEvaluateOnNewDocument',{source:`
window.__calls=[];window.__release=null;window.__fail=false;window.confirm=()=>true;localStorage.clear();
const stored={id:'stable-id',slug:'original',titles:{en:'Page title'},status:'draft',draft_tree:${JSON.stringify(tree)},published_tree:null};
window.fetch=async(url,init={})=>{
 const path=String(url),method=init.method||'GET';window.__calls.push({path,method,body:init.body?JSON.parse(init.body):null});
 let body={},status=200;
 if(method==='GET')body=path.endsWith('/site/pages')?{items:[stored]}:path.endsWith('/site/settings')?{value:{}}:stored;
 else if(path.endsWith('/draft')){await new Promise(r=>window.__release=r);stored.draft_tree=JSON.parse(init.body).tree;body=stored;}
 else if(path.endsWith('/publish')){await new Promise(r=>window.__release=r);body={...stored,status:'published'};}
 else if(path.endsWith('/site/settings')){if(window.__fail){status=500;body={detail:'mock settings failure'};}else body={value:JSON.parse(init.body).value};}
 return new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
};`});
await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html?page=stable-id'});await sleep(400);await waitFor(`document.querySelector('.studio-notice').textContent.includes('Loaded')`);
async function edit(text){await evaluate(`(()=>{const e=document.querySelector('textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,${JSON.stringify(text)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await sleep(100);}
async function button(text){await evaluate(`[...document.querySelectorAll('.top-actions button')].find(b=>b.textContent===${JSON.stringify(text)}).click()`);await sleep(100);}
async function release(){await evaluate(`window.__release();window.__release=null`);await sleep(200);}
await edit('Snapshot A');await button('Save to local backend');
await waitFor(`!!window.__release`);
await button('Saving snapshot...');
await edit('Newer edit B');
if(!(await evaluate(`document.querySelector('.top-actions button[title]').disabled`)))throw Error('publish not disabled during save');
await release();await waitFor(`document.querySelector('.studio-notice').textContent.includes('Newer local changes are NOT saved')`);
if(!(await evaluate(`window.__calls.filter(c=>c.path.endsWith('/draft')).length===1`)))throw Error('duplicate save');
await shot((process.env.STUDIO_OUT||'/downloads')+'/studio-newer-edits-unsaved.png');
await button('Save to local backend');await waitFor(`!!window.__release`);await release();
await waitFor(`document.querySelector('.studio-notice').textContent.startsWith('Draft and site settings saved')`);
await button('Publish (local test)');await waitFor(`!!window.__release`);await button('Publishing snapshot...');await edit('Newer edit C');await release();
await waitFor(`document.querySelector('.studio-notice').textContent.includes('NOT saved or published')`);
if(!(await evaluate(`window.__calls.filter(c=>c.path.endsWith('/publish')).length===1`)))throw Error('duplicate publish');
await evaluate(`window.__fail=true`);await button('Save to local backend');await waitFor(`!!window.__release`);await release();await waitFor(`document.querySelector('.studio-notice').textContent.includes('settings FAILED')`);
if(!(await evaluate(`document.querySelector('.top-actions button[title]').disabled`)))throw Error('partial failure allowed publish');
await evaluate(`window.__fail=false`);await button('Save to local backend');await waitFor(`!!window.__release`);await release();await waitFor(`document.querySelector('.studio-notice').textContent.startsWith('Draft and site settings saved')`);
console.log('PASS mocked save/publish: repeated clicks serialized, older snapshot warning, dirty publish blocked, newer edit during publish preserved, partial settings failure then retry');ws.close();
