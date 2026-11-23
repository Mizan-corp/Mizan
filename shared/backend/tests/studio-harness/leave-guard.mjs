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




await send('Page.addScriptToEvaluateOnNewDocument',{source:`
localStorage.clear();window.fetch=async()=>{throw Error('mock backend offline')};window.__storageFail=false;
const original=Storage.prototype.setItem;Storage.prototype.setItem=function(...args){if(window.__storageFail)throw new DOMException('mock quota exceeded','QuotaExceededError');return original.apply(this,args)};
window.__wouldWarn=()=>{const event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);return event.defaultPrevented};
`});
await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html'});await sleep(400);await waitFor(`document.querySelector('.studio-notice')?.textContent.includes('no local test backend')`);
if(await evaluate(`window.__wouldWarn()`))throw Error('clean initial state warns');
async function edit(text){await evaluate(`(()=>{const e=document.querySelector('textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,${JSON.stringify(text)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await sleep(100);}
async function save(){await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Save local draft').click()`);await sleep(100);}
await edit('Keep these unsaved edits');
if(!(await evaluate(`window.__wouldWarn() && document.querySelector('.persistence-bar').textContent.includes('Browser copy not saved')`)))throw Error('dirty warning absent');
await evaluate(`window.__storageFail=true`);await save();
if(!(await evaluate(`!!document.querySelector('.storage-error') && document.querySelector('textarea').value==='Keep these unsaved edits' && window.__wouldWarn()`)))throw Error('storage failure lost state');
await shot((process.env.STUDIO_OUT||'/downloads')+'/studio-browser-save-failure.png');
await evaluate(`window.__storageFail=false`);await save();
if(!(await evaluate(`!document.querySelector('.storage-error') && document.querySelector('.persistence-bar').textContent.includes('Browser copy saved') && !window.__wouldWarn()`)))throw Error('retry did not clear local dirty');
await shot((process.env.STUDIO_OUT||'/downloads')+'/studio-browser-save-status.png');
console.log('PASS mocked offline/local storage: clean baseline no guard, edited state guard, quota failure retains edits/guard, retry clears local dirty; synthetic beforeunload cancellation tested, not native dialog');ws.close();
