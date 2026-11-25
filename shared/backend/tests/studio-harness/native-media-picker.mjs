// CDP driver: real authenticated studio picker flow.
// open page in NativeStudio -> select image node -> open media picker dialog ->
// upload a real PNG through the bridge -> select it -> save -> reload -> verify
// the persisted src and that the image actually loads through the /uploads proxy.
import { writeFileSync } from 'node:fs';

const CHROME = 'http://127.0.0.1:9222';
const PAGE_ID = process.env.PAGE_ID;
const OUT = process.env.STUDIO_OUT || '/downloads';
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
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
function send(method, params = {}) {
  const id = ++seq;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise(res => pending.set(id, res));
}
async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error('page error: ' + JSON.stringify(r.result.exceptionDetails).slice(0, 400));
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
  const buttons = await evaluate(`[...document.querySelectorAll('button')].map(b => b.textContent).join(' | ')`);
  console.log('DEBUG buttons:', buttons);
  await shot('picker-debug.png');
  throw new Error('timeout waiting for: ' + expression.slice(0, 90));
}

await send('Page.enable');
await send('Runtime.enable');
await send('DOM.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

// 1. open the seeded page in the native editor
await send('Page.navigate', { url: `http://127.0.0.1:5188/studio.html?editor=tree&page=${PAGE_ID}` });
await waitFor(`!!document.querySelector('.preview-frame')`);
await waitFor(`!!document.querySelector('.mz-saved') && !document.querySelector('.mz-saved').textContent.includes('بنفتح')`);
await shot('01-editor-open.png');

// 2. select the image node on the canvas
await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b => b.querySelector('span')?.textContent === 'Layers' || b.querySelector('span')?.textContent === 'الطبقات')?.click()`);
await waitFor(`!!document.querySelector('button.native-node[data-node-id="n_img1"]')`);
await evaluate(`document.querySelector('button.native-node[data-node-id="n_img1"]').click()`);
await waitFor(`!!document.querySelector('.media-library-open')`);
await shot('02-image-selected.png');

// 3. open the picker dialog
await evaluate(`document.querySelector('.media-library-open').click()`);
await waitFor(`!!document.querySelector('.media-picker[role="dialog"]')`);
await waitFor(`!!document.querySelector('.media-picker input[type="file"]')`);
await shot('03-picker-dialog.png');
const dlgRect = JSON.parse(await evaluate(`JSON.stringify(document.querySelector('.media-picker[role="dialog"]').getBoundingClientRect())`));
const vis = await evaluate(`(()=>{const r=document.querySelector('.media-picker[role="dialog"]').getBoundingClientRect();return r.top>=0&&r.top<window.innerHeight&&r.height>0})()`);
console.log('dialog visible in viewport:', vis, JSON.stringify(dlgRect));
const clip = { x: Math.max(0, dlgRect.x - 8), y: Math.max(0, dlgRect.y - 8), width: dlgRect.width + 16, height: Math.min(dlgRect.height + 16, 847), scale: 1 };
const dlgShot = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, clip });
writeFileSync(`${OUT}/03b-dialog-closeup.png`, Buffer.from(dlgShot.result.data, 'base64'));
console.log('shot 03b-dialog-closeup.png');

// 4. upload a real PNG via the hidden file input (bridge forwards multipart to the API)
const doc = await send('DOM.getDocument', { depth: -1 });
const input = await send('DOM.querySelector', { nodeId: doc.result.root.nodeId, selector: '.media-picker input[type="file"]' });
await send('DOM.setFileInputFiles', { nodeId: input.result.nodeId, files: ['/tmp/studio-picker.png'] });
await waitFor(`!!document.querySelector('.media-picker-grid .media-pick')`, 60);
// the API's freshest item is this run's upload; pick exactly that grid entry
const newest = await evaluate(`fetch('/__studio/api/site/media',{cache:'no-store'}).then(r=>r.json()).then(d=>{const items=d.items||[];items.sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));return items[0]?.url ?? null})`);
if (!newest) throw new Error('media list empty after upload');
await waitFor(`!![...document.querySelectorAll('.media-picker-grid .media-pick img')].find(i => i.getAttribute('src') === ${JSON.stringify('__NEWEST__')})`.replace('__NEWEST__', newest), 60);
await shot('04-picker-uploaded.png');

// 5. select the uploaded image
await evaluate(`[...document.querySelectorAll('.media-picker-grid .media-pick')].find(b => b.querySelector('img')?.getAttribute('src') === ${JSON.stringify('__NEWEST__')})?.click()`.replace('__NEWEST__', newest));
await waitFor(`!document.querySelector('.media-picker[role="dialog"]')`);
await waitFor(`(document.querySelector('input[aria-label="Native src"]')||{}).value?.includes('/uploads/')`);
const pickedSrc = await evaluate(`document.querySelector('input[aria-label="Native src"]').value`);
console.log('picked src:', pickedSrc);
await shot('05-src-applied.png');

// 6. save
await evaluate(`[...document.querySelectorAll('.top-actions button')].find(b => (b.title||'').startsWith('احفظ') || (b.title||'').startsWith('Save this page draft'))?.click()`);
await waitFor(`(()=>{const t=document.querySelector('.mz-saved')?.textContent||'';return t.includes('تم حفظ')||t.includes('All changes saved')})()`, 60);
await shot('06-saved.png');

// 7. server-side truth: the draft really holds the /uploads URL
const serverSrc = await evaluate(`fetch('/__studio/api/site/pages/${PAGE_ID}',{cache:'no-store'}).then(r=>r.json()).then(p=>{const j=JSON.stringify(p.draft_tree);const i=j.indexOf('/uploads/');return i<0?null:j.slice(i,i+120).split(String.fromCharCode(34))[0]})`);
console.log('server draft src:', serverSrc);
if (!serverSrc) throw new Error('server draft does not contain the uploads URL');

// 8. reload: the studio reopens from the server draft, image node keeps the src,
//    and the <img> actually loads its bytes through the /uploads proxy
await send('Page.navigate', { url: `http://127.0.0.1:5188/studio.html?editor=tree&page=${PAGE_ID}` });
await waitFor(`!!document.querySelector('.preview-frame') && !!document.getElementById('n_img1')`);
await waitFor(`(()=>{const img=document.querySelector('.preview-frame img.mz-image');return !!img && img.src.includes('/uploads/') && img.complete && img.naturalWidth > 0})()`, 60);
await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b => b.querySelector('span')?.textContent === 'Layers' || b.querySelector('span')?.textContent === 'الطبقات')?.click()`);
await waitFor(`!!document.querySelector('button.native-node[data-node-id="n_img1"]')`);
await evaluate(`document.querySelector('button.native-node[data-node-id="n_img1"]').click()`);
await waitFor(`(document.querySelector('input[aria-label="Native src"]')||{}).value?.includes('/uploads/')`);
await shot('07-reloaded-persisted.png');

console.log('PICKER-FLOW-PASS');
process.exit(0);
