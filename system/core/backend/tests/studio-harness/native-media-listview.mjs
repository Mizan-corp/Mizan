// CDP driver: media library list view toggle - grid default, list rows, selection, mobile sheet list.
import { writeFileSync } from 'node:fs';
const CHROME = 'http://127.0.0.1:9222';
const PAGE_ID = process.env.PAGE_ID;
const OUT = process.env.STUDIO_OUT || '/downloads';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const r0 = await fetch(`${CHROME}/json/new?about:blank`, { method: 'PUT' });
const target = await r0.json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let seq = 0; const pending = new Map();
ws.onmessage = (m) => { const msg = JSON.parse(m.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } if (msg.method === 'Page.javascriptDialogOpening') send('Page.handleJavaScriptDialog', { accept: true }); };
function send(method, params = {}) { const id = ++seq; ws.send(JSON.stringify({ id, method, params })); return new Promise(res => pending.set(id, res)); }
async function evaluate(expression) { const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }); if (r.result?.exceptionDetails) throw new Error('page error: ' + JSON.stringify(r.result.exceptionDetails).slice(0, 300)); return r.result?.result?.value; }
async function shot(name) { const r = await send('Page.captureScreenshot', { format: 'png', fromSurface: true }); writeFileSync(`${OUT}/${name}`, Buffer.from(r.result.data, 'base64')); console.log('shot', name); }
async function waitFor(expression, tries = 40) { for (let i = 0; i < tries; i++) { if (await evaluate(expression)) return true; await sleep(500); } await shot('listview-debug.png'); throw new Error('timeout: ' + expression.slice(0, 90)); }

await send('Page.enable'); await send('Runtime.enable'); await send('DOM.enable');

async function openPicker() {
  await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b => b.querySelector('span')?.textContent === 'Style' || b.querySelector('span')?.textContent === 'النمط')?.click()`);
  await waitFor(`!!document.querySelector('.native-shared-chrome:not([hidden])')`);
  await evaluate(`[...document.querySelectorAll('.native-shared-chrome button')].find(b => /Load site appearance|حمّل شكل الموقع/.test(b.textContent))?.click()`);
  await waitFor(`[...document.querySelectorAll('.native-shared-chrome button')].some(b => /Save site appearance|حفظ شكل الموقع/.test(b.textContent))`);
  await evaluate(`[...document.querySelectorAll('.native-shared-chrome .library-filters button')].find(b => /^Header$|^الهيدر$/.test(b.textContent.trim()))?.click()`);
  await waitFor(`!!document.querySelector('.native-shared-chrome .media-library-open')`);
  await evaluate(`document.querySelector('.native-shared-chrome .media-library-open').click()`);
  await waitFor(`!!document.querySelector('.media-modal[role="dialog"]')`);
  await waitFor(`document.querySelectorAll('.media-grid .media-tile').length > 0`);
}

// desktop: grid default -> list toggle -> select a row
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url: `http://127.0.0.1:5188/studio.html?editor=tree&page=${PAGE_ID}` });
await waitFor(`!!document.querySelector('.preview-frame')`);
await openPicker();
if (!(await evaluate(`!!document.querySelector('.media-grid')`))) throw new Error('grid not default');
await evaluate(`document.querySelector('.media-view-toggle button[aria-label="List view"],.media-view-toggle button[aria-label="عرض قائمة"]').click()`);
await waitFor(`!!document.querySelector('.media-list .media-row-item')`);
const rows = await evaluate(`document.querySelectorAll('.media-list .media-row-item').length`);
console.log('list rows:', rows);
await evaluate(`document.querySelector('.media-list .media-row-item .media-row').click()`);
await waitFor(`!!document.querySelector('.media-list .media-row-item.selected')`);
const foot = await evaluate(`document.querySelector('.media-selected-name')?.textContent`);
console.log('footer selection:', foot);
await shot('17-media-listview.png');
await evaluate(`[...document.querySelectorAll('.media-modal-head button')].find(b => b.textContent.trim() === '\\u00d7')?.click()`);
await waitFor(`!document.querySelector('.media-modal[role="dialog"]')`);

// phone: list view inside the sheet
await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
await send('Page.navigate', { url: `http://127.0.0.1:5188/studio.html?editor=tree&page=${PAGE_ID}` });
await waitFor(`!!document.querySelector('.preview-frame')`);
await openPicker();
await evaluate(`document.querySelector('.media-view-toggle button[aria-label="List view"],.media-view-toggle button[aria-label="عرض قائمة"]').click()`);
await waitFor(`!!document.querySelector('.media-list .media-row-item')`);
const overflow = await evaluate(`document.documentElement.scrollWidth <= 390`);
if (!overflow) throw new Error('phone horizontal overflow');
await shot('18-media-listview-mobile.png');
console.log('MEDIA-LISTVIEW-PASS');
process.exit(0);
