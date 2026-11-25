// CDP driver: hosted-style upload failure (VERCEL set, no blob token) surfaces
// the server's honest 503 detail inside the picker; nothing appears uploaded.
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const CHROME = 'http://127.0.0.1:9222';
const PAGE_ID = process.env.PAGE_ID;
const OUT = process.env.STUDIO_OUT || '/downloads';
const FIXTURE = (name) => fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url));
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const r0 = await fetch(`${CHROME}/json/new?about:blank`, { method: 'PUT' });
const target = await r0.json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0;
const pending = new Map();
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === 'Page.javascriptDialogOpening') send('Page.handleJavaScriptDialog', { accept: true });
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
async function shot(name) {
  const r = await send('Page.captureScreenshot', { format: 'png', fromSurface: true });
  writeFileSync(`${OUT}/${name}`, Buffer.from(r.result.data, 'base64'));
  console.log('shot', name);
}
async function waitFor(expression, tries = 40) {
  for (let i = 0; i < tries; i++) {
    if (await evaluate(expression)) return true;
    await sleep(500);
  }
  await shot('media-503-debug.png');
  throw new Error('timeout waiting for: ' + expression.slice(0, 90));
}

await send('Page.enable');
await send('Runtime.enable');
await send('DOM.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

await send('Page.navigate', { url: `http://127.0.0.1:5188/studio.html?editor=tree&page=${PAGE_ID}` });
await waitFor(`!!document.querySelector('.preview-frame')`);

// sanity: backend reports the hosted-style failure (503) for a direct upload of a real image
import { readFileSync } from 'node:fs';
const fd = new FormData();
fd.append('file', new Blob([readFileSync(FIXTURE('fix-menu-dish.png'))], { type: 'image/png' }), 'fix-menu-dish.png');
const directResp = await fetch('http://127.0.0.1:8000/site/media', { method: 'POST', headers: { Authorization: `Bearer ${process.env.STUDIO_TOKEN}` }, body: fd });
const direct = { status: directResp.status, body: await directResp.text() };
console.log('direct upload status:', direct.status, '| body:', direct.body.slice(0, 120));
if (direct.status !== 503) throw new Error('expected 503 from the unprovisioned backend, got ' + direct.status);

// open the picker from the chrome logo tools
await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b => b.querySelector('span')?.textContent === 'Style' || b.querySelector('span')?.textContent === 'النمط')?.click()`);
await waitFor(`!!document.querySelector('.native-shared-chrome:not([hidden])')`);
await evaluate(`[...document.querySelectorAll('.native-shared-chrome button')].find(b => /Load site appearance|حمّل شكل الموقع/.test(b.textContent))?.click()`);
await waitFor(`[...document.querySelectorAll('.native-shared-chrome button')].some(b => /Save site appearance|حفظ شكل الموقع/.test(b.textContent))`);
await evaluate(`[...document.querySelectorAll('.native-shared-chrome .library-filters button')].find(b => /^Header$|^الهيدر$/.test(b.textContent.trim()))?.click()`);
await waitFor(`!!document.querySelector('.native-shared-chrome .media-library-open')`);
await evaluate(`document.querySelector('.native-shared-chrome .media-library-open').click()`);
await waitFor(`!!document.querySelector('.media-modal[role="dialog"]')`);
await waitFor(`!!document.querySelector('.media-modal input[type="file"]')`);
await waitFor(`document.querySelectorAll('.media-grid .media-tile').length > 0 || !document.querySelector('.media-modal .hint')`);

const beforeCount = await evaluate(`document.querySelectorAll('.media-grid .media-tile').length`);
const doc = await send('DOM.getDocument', { depth: -1 });
const input = await send('DOM.querySelector', { nodeId: doc.result.root.nodeId, selector: '.media-modal input[type="file"]' });
await send('DOM.setFileInputFiles', { nodeId: input.result.nodeId, files: [FIXTURE('fix-menu-dish.png')] });
await waitFor(`!!document.querySelector('.media-modal .media-error[role="alert"]')`, 60);
const errText = await evaluate(`document.querySelector('.media-modal .media-error[role="alert"]').textContent`);
console.log('picker error shown:', errText);
if (!/تخزين الملفات|storage/i.test(errText)) throw new Error('picker error is not the server storage detail');
const afterCount = await evaluate(`document.querySelectorAll('.media-grid .media-tile').length`);
if (afterCount !== beforeCount) throw new Error('grid changed despite failed upload');
await shot('16-hosted-503-state.png');
console.log('MEDIA-503-PASS');
process.exit(0);
