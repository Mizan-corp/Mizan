// CDP driver: chrome logo via the shared media picker.
// open Style panel -> load site appearance -> Header -> open media library ->
// pick the product-candle fixture -> logo field holds the /uploads URL -> save
// site appearance -> server settings hold the logo -> the library refuses to
// delete the in-use logo (409) -> reload -> logo persists and renders.
import { writeFileSync } from 'node:fs';

const CHROME = 'http://127.0.0.1:9222';
const PAGE_ID = process.env.PAGE_ID;
const OUT = process.env.STUDIO_OUT || '/downloads';
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
  await shot('chrome-logo-debug.png');
  throw new Error('timeout waiting for: ' + expression.slice(0, 90));
}

await send('Page.enable');
await send('Runtime.enable');
await send('DOM.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

// the fixture we will pick, matched by its stored original filename
const logoUrl = await send('Page.navigate', { url: `http://127.0.0.1:5188/studio.html?editor=tree&page=${PAGE_ID}` }).then(() => waitFor(`!!document.querySelector('.preview-frame')`))
  .then(() => evaluate(`fetch('/__studio/api/site/media',{cache:'no-store'}).then(r=>r.json()).then(d=>(d.items||[]).find(i=>i.name==='fix-product-candle.png')?.url ?? null)`));
if (!logoUrl) throw new Error('fix-product-candle.png not in the library');
console.log('logo target:', logoUrl);

// 1. Style panel -> load appearance -> Header tab
await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b => b.querySelector('span')?.textContent === 'Style' || b.querySelector('span')?.textContent === 'النمط')?.click()`);
await waitFor(`!!document.querySelector('.native-shared-chrome:not([hidden])')`);
await evaluate(`[...document.querySelectorAll('.native-shared-chrome button')].find(b => /Load site appearance|حمّل شكل الموقع/.test(b.textContent))?.click()`);
await waitFor(`[...document.querySelectorAll('.native-shared-chrome button')].some(b => /Save site appearance|حفظ شكل الموقع/.test(b.textContent))`);
await evaluate(`[...document.querySelectorAll('.native-shared-chrome .library-filters button')].find(b => /^Header$|^الهيدر$/.test(b.textContent.trim()))?.click()`);
await waitFor(`!!document.querySelector('.native-shared-chrome input[aria-label="Site logo URL"],.native-shared-chrome input[aria-label="لوجو الموقع"]')`);

// 2. open the shared picker from the logo tools and pick the fixture
await evaluate(`document.querySelector('.native-shared-chrome .media-library-open').click()`);
await waitFor(`!!document.querySelector('.media-modal[role="dialog"]')`);
await shot('13-chrome-logo-picker.png');
await evaluate(`[...document.querySelectorAll('.media-grid .media-tile')].find(b => b.querySelector('img')?.getAttribute('src') === ${JSON.stringify(logoUrl)})?.click()`);
await waitFor(`!!document.querySelector('.media-grid figure.selected')`);
await evaluate(`[...document.querySelectorAll('.media-foot-actions button')].find(b => /Use image|استخدم الصورة/.test(b.textContent))?.click()`);
await waitFor(`!document.querySelector('.media-modal[role="dialog"]')`);
const fieldValue = await evaluate(`document.querySelector('.native-shared-chrome input[aria-label="Site logo URL"],.native-shared-chrome input[aria-label="لوجو الموقع"]').value`);
console.log('logo field:', fieldValue);
if (fieldValue !== logoUrl) throw new Error('logo field did not receive the picked URL');
await waitFor(`!!document.querySelector('.chrome-logo-preview')`);

// 3. save site appearance and verify the server holds the logo
await evaluate(`[...document.querySelectorAll('.native-shared-chrome button')].find(b => /Save site appearance|حفظ شكل الموقع/.test(b.textContent))?.click()`);
await waitFor(`(()=>{const el=[...document.querySelectorAll('.native-shared-chrome .motion-note')].find(p=>/matches the loaded version|مطابق للنسخة/.test(p.textContent));return !!el})()`, 60);
await shot('14-chrome-logo-saved.png');
const serverLogo = await evaluate(`fetch('/__studio/api/site/settings',{cache:'no-store'}).then(r=>r.json()).then(d=>d.value?.header?.logo ?? null)`);
console.log('server settings logo:', serverLogo);
if (serverLogo !== logoUrl) throw new Error('server settings do not hold the picked logo');

// 4. in-use guard: the library must refuse to delete the logo now (409)
const delStatus = await evaluate(`fetch('/__studio/api/site/media',{cache:'no-store'}).then(r=>r.json()).then(d=>{const it=(d.items||[]).find(i=>i.url===${JSON.stringify(logoUrl)});return fetch('/__studio/api/site/media/'+it.id,{method:'DELETE'}).then(r=>r.status)})`);
console.log('delete in-use logo status:', delStatus);
if (delStatus !== 409) throw new Error('in-use logo delete was not refused: ' + delStatus);

// 5. reload: logo persists in the field and renders in the header preview
await send('Page.navigate', { url: `http://127.0.0.1:5188/studio.html?editor=tree&page=${PAGE_ID}` });
await waitFor(`!!document.querySelector('.preview-frame')`);
await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b => b.querySelector('span')?.textContent === 'Style' || b.querySelector('span')?.textContent === 'النمط')?.click()`);
await waitFor(`!!document.querySelector('.native-shared-chrome:not([hidden])')`);
await evaluate(`[...document.querySelectorAll('.native-shared-chrome button')].find(b => /Load site appearance|حمّل شكل الموقع/.test(b.textContent))?.click()`);
await waitFor(`[...document.querySelectorAll('.native-shared-chrome button')].some(b => /Save site appearance|حفظ شكل الموقع/.test(b.textContent))`);
await evaluate(`[...document.querySelectorAll('.native-shared-chrome .library-filters button')].find(b => /^Header$|^الهيدر$/.test(b.textContent.trim()))?.click()`);
await waitFor(`(()=>{const i=document.querySelector('.native-shared-chrome input[aria-label="Site logo URL"],.native-shared-chrome input[aria-label="لوجو الموقع"]');return i && i.value === ${JSON.stringify(logoUrl)}})()`, 60);
await waitFor(`(()=>{const img=document.querySelector('.chrome-preview img.mz-site-logo');return !!img && img.complete && img.naturalWidth > 0})()`, 60);
await shot('15-chrome-logo-reloaded.png');

console.log('CHROME-LOGO-PASS');
process.exit(0);
