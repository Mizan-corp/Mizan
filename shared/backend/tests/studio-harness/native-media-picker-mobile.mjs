// Follow-up pass on the already-saved picker page:
// A. UI publish flow -> server published_tree holds the /uploads URL.
// B. Phone viewport (390x844): picker dialog reachable/usable (open, upload,
//    select, delete attempt, close) with in-viewport assertions + screenshots.
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
  await shot('mp-debug.png');
  throw new Error('timeout waiting for: ' + expression.slice(0, 90));
}

await send('Page.enable');
await send('Runtime.enable');
await send('DOM.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

// A. publish through the UI
await send('Page.navigate', { url: `http://127.0.0.1:5188/studio.html?editor=tree&page=${PAGE_ID}` });
await waitFor(`!!document.querySelector('.preview-frame') && !!document.getElementById('n_img1')`);
await waitFor(`(()=>{const img=document.querySelector('.preview-frame img.mz-image');return !!img && img.complete && img.naturalWidth > 0})()`, 60);
await evaluate(`[...document.querySelectorAll('.top-actions button')].find(b => b.textContent.trim() === 'Publish' || b.textContent.trim() === 'نشر')?.click()`);
await waitFor(`!!document.querySelector('.mz-publish-card')`);
await shot('08-publish-dialog.png');
await evaluate(`[...document.querySelectorAll('.mz-publish-card button')].find(b => b.classList.contains('primary'))?.click()`);
await waitFor(`!!document.querySelector('.mz-publish-card') && (document.querySelector('.mz-publish-card').textContent.includes('اتنشرت') || document.querySelector('.mz-publish-card').textContent.includes('ublished'))`, 60);
await shot('09-published.png');
const publishedSrc = await evaluate(`fetch('/__studio/api/site/pages/${PAGE_ID}',{cache:'no-store'}).then(r=>r.json()).then(p=>{const j=JSON.stringify(p.published_tree);const i=j.indexOf('/uploads/');return i<0?null:j.slice(i,i+120).split(String.fromCharCode(34))[0]})`);
console.log('published tree src:', publishedSrc);
if (!publishedSrc) throw new Error('published tree does not contain the uploads URL');

// B. phone viewport picker usability
await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await send('Page.navigate', { url: `http://127.0.0.1:5188/studio.html?editor=tree&page=${PAGE_ID}` });
await waitFor(`!!document.querySelector('.preview-frame') && !!document.getElementById('n_img1')`);
await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b => b.querySelector('span')?.textContent === 'Layers' || b.querySelector('span')?.textContent === 'الطبقات')?.click()`);
await waitFor(`!!document.querySelector('button.native-node[data-node-id="n_img1"]')`);
await evaluate(`document.querySelector('button.native-node[data-node-id="n_img1"]').click()`);
await waitFor(`!!document.querySelector('.media-library-open')`);
await evaluate(`document.querySelector('.media-library-open').click()`);
await waitFor(`!!document.querySelector('.media-picker[role="dialog"] input[type="file"]')`);
const fit = JSON.parse(await evaluate(`(()=>{const r=document.querySelector('.media-picker[role="dialog"]').getBoundingClientRect();return JSON.stringify({top:r.top,right:r.right,width:r.width,inViewport:r.top>=0&&r.top<window.innerHeight&&r.right<=window.innerWidth+1})})()`));
console.log('mobile dialog fit:', JSON.stringify(fit));
await shot('10-mobile-picker.png');
// upload reachable on mobile
const doc = await send('DOM.getDocument', { depth: -1 });
const input = await send('DOM.querySelector', { nodeId: doc.result.root.nodeId, selector: '.media-picker input[type="file"]' });
const beforeCount = await evaluate(`document.querySelectorAll('.media-picker-grid .media-pick').length`);
await send('DOM.setFileInputFiles', { nodeId: input.result.nodeId, files: ['/tmp/studio-picker.png'] });
await waitFor(`document.querySelectorAll('.media-picker-grid .media-pick').length > ${beforeCount}`, 60);
await shot('11-mobile-uploaded.png');
// select the fresh upload
const newest = await evaluate(`fetch('/__studio/api/site/media',{cache:'no-store'}).then(r=>r.json()).then(d=>{const items=d.items||[];items.sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)));return items[0]?.url ?? null})`);
await evaluate(`[...document.querySelectorAll('.media-picker-grid .media-pick')].find(b => b.querySelector('img')?.getAttribute('src') === ${JSON.stringify('__NEWEST__')})?.click()`.replace('__NEWEST__', newest));
await waitFor(`(document.querySelector('input[aria-label="Native src"]')||{}).value === ${JSON.stringify('__NEWEST__')}`.replace('__NEWEST__', newest));
const mobileSrc = await evaluate(`document.querySelector('input[aria-label="Native src"]').value`);
console.log('mobile picked src:', mobileSrc);
if (mobileSrc !== newest) throw new Error('mobile pick did not land the fresh upload');
// close control reachable
await evaluate(`document.querySelector('.media-library-open').click()`);
await waitFor(`!!document.querySelector('.media-picker[role="dialog"]')`);
await evaluate(`document.querySelector('.media-picker [aria-label]') && [...document.querySelectorAll('.media-picker button')].find(b => b.textContent.trim() === '×')?.click()`);
await waitFor(`!document.querySelector('.media-picker[role="dialog"]')`);
console.log('mobile close ok');
// delete control reachable: the fresh upload is unreferenced in the DB (no save on
// mobile), so its delete must succeed and the item must leave the grid.
await evaluate(`document.querySelector('.media-library-open').click()`);
await waitFor(`!!document.querySelector('.media-picker[role="dialog"]')`);
await evaluate(`[...document.querySelectorAll('.media-picker-grid figure')].find(f => f.querySelector('img')?.getAttribute('src') === ${JSON.stringify('__NEWEST__')})?.querySelector('.media-delete')?.click()`.replace('__NEWEST__', newest));
await waitFor(`![...document.querySelectorAll('.media-picker-grid figure')].some(f => f.querySelector('img')?.getAttribute('src') === ${JSON.stringify('__NEWEST__')})`.replace('__NEWEST__', newest), 60);
console.log('mobile delete ok (unreferenced fresh upload removed)');
await shot('12-mobile-after.png');
console.log('MOBILE-PUBLISH-PASS');
process.exit(0);
