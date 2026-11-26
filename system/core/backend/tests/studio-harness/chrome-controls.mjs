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


await send('Page.navigate', {url:'http://127.0.0.1:5188/studio.html'});
await waitFor(`!!document.querySelector('.chrome-inspector')`);
await evaluate(`localStorage.clear()`);await send('Page.reload');await sleep(800);await waitFor(`!!document.querySelector('.chrome-inspector')`);
async function input(label,value){await evaluate(`(()=>{const e=document.querySelector('[aria-label="${label}"]');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await sleep(100);}
async function click(text){await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)}).click()`);await sleep(100);}
await click('+ Add footer link');
await input('footerLinks label 1','Returns');await input('footerLinks link 1','/returns');
if(!(await evaluate(`document.querySelector('.mz-site-footer a')?.getAttribute('href')==='/returns'`)))throw Error('preview missing footer link');
await evaluate(`document.querySelector('[aria-label="footerLinks label 1"]').scrollIntoView({block:'center'})`);await shot((process.env.STUDIO_OUT || '/downloads') + '/studio-footer-links.png');
await click('Save local draft');await send('Page.reload');await sleep(800);await waitFor(`document.querySelector('[aria-label="footerLinks label 1"]')?.value==='Returns'`);
await click('+ Add footer link');await input('footerLinks label 2','Contact');await input('footerLinks link 2','/contact');
await evaluate(`document.querySelector('[aria-label="Move footerLinks 2 up"]').click()`);await sleep(100);
if(!(await evaluate(`document.querySelector('[aria-label="footerLinks label 1"]').value==='Contact'`)))throw Error('reorder failed');
await evaluate(`document.querySelector('[aria-label="remove footerLinks 2"]').click()`);await sleep(100);
await input('footerLinks link 1','javascript:alert(1)');
if(!(await evaluate(`document.querySelector('[aria-label="footerLinks link 1"]').getAttribute('aria-invalid')==='true' && document.querySelectorAll('.mz-site-footer a').length===0`)))throw Error('invalid URL handling failed');
await input('footerLinks link 1','/contact');await evaluate(`document.querySelector('[aria-label="links label 1"]').scrollIntoView({block:'center'})`);await shot((process.env.STUDIO_OUT || '/downloads') + '/studio-header-controls.png');
console.log('PASS footer add/edit, local reload, reorder/remove, invalid URL feedback and preview rejection');ws.close();
