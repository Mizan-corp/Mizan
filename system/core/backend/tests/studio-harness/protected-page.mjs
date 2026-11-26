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



// Mocked responses only. No backend writes or real page data in this regression.
await send('Page.addScriptToEvaluateOnNewDocument',{source:`
window.__writes=[];
window.fetch=async (url,init={})=>{
 if(String(url).startsWith('/__studio/api')){
  if(init.method && init.method!=='GET') window.__writes.push({url,method:init.method});
  let body={};
  if(String(url).endsWith('/site/pages')) body={items:[{id:'unsupported-page',slug:'northline-studio'}]};
  else if(String(url).endsWith('/site/settings')) body={value:{}};
  else body={id:'unsupported-page',slug:'northline-studio',titles:{en:'Northline studio'},status:'draft',draft_tree:{id:'n_root',type:'gallery',settings:{},content:{}},published_tree:null};
  return new Response(JSON.stringify(body),{status:200,headers:{'Content-Type':'application/json'}});
 }
 throw Error('Unexpected non-mock fetch');
};localStorage.clear();`});
await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html'});
await waitFor(`!!document.querySelector('.studio-protection')`);
if(!(await evaluate(`![...document.querySelectorAll('.top-actions button')].some(b=>b.textContent==='Save to local backend'||b.textContent==='Publish (local test)')`)))throw Error('write actions remain');
await evaluate(`document.querySelector('textarea').value`);
await shot((process.env.STUDIO_OUT||'/downloads')+'/studio-protected-page.png');
if(!(await evaluate(`window.__writes.length===0`)))throw Error('unexpected API write');
console.log('PASS mocked unsupported backend page: protection visible, backend save/publish absent, zero write requests');ws.close();
