// CDP driver: render parity between the studio React live preview and the shared
// Python renderer snapshot, desktop + mobile, same page tree.
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
async function shotClip(path, selector) {
  const rect = await evaluate(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el) return null; const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; })()`);
  if (!rect) throw new Error('no element: ' + selector);
  // Grow the viewport past the element so every row is painted before capture.
  await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: Math.ceil(rect.y + rect.height + 60), deviceScaleFactor: 1, mobile: false });
  await sleep(400);
  const rect2 = await evaluate(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, width: r.width, height: r.height}; })()`);
  Object.assign(rect, rect2);
  const r = await send('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: true, clip: { x: rect.x, y: rect.y, width: rect.width, height: rect.height, scale: 1 } });
  writeFileSync(path, Buffer.from(r.result.data, 'base64'));
  return rect;
}
async function waitFor(expression, tries = 40) {
  for (let i = 0; i < tries; i++) {
    if (await evaluate(expression)) return true;
    await sleep(500);
  }
  throw new Error('timeout waiting for: ' + expression.slice(0, 80));
}


// Open the shared-renderer srcdoc in its own tab at an exact device width and capture full height.
async function shotShared(path, width, height) {
  const html = await evaluate(`document.querySelector('.shared-preview iframe').getAttribute('srcdoc')`);
  if (!html || html.length < 500) throw new Error('no srcdoc captured');
  const t2 = await newTab();
  const ws2 = new WebSocket(t2.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws2.onopen = res; ws2.onerror = rej; });
  let seq2 = 0; const pending2 = new Map();
  ws2.onmessage = (m) => { const msg = JSON.parse(m.data); if (msg.id && pending2.has(msg.id)) { pending2.get(msg.id)(msg); pending2.delete(msg.id); } };
  const send2 = (method, params = {}) => { const id = ++seq2; ws2.send(JSON.stringify({ id, method, params })); return new Promise(res => pending2.set(id, res)); };
  await send2('Page.enable');
  await send2('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 500 });
  await send2('Page.navigate', { url: 'data:text/html;base64,' + Buffer.from(html).toString('base64') });
  await sleep(1500);
  await send2('Runtime.evaluate', { expression: "const s = document.createElement('style'); s.textContent = 'html{scrollbar-width:none}::-webkit-scrollbar{display:none}'; document.head.appendChild(s);" });
  const r = await send2('Runtime.evaluate', { expression: 'document.documentElement.scrollHeight', returnByValue: true });
  const full = r.result.result.value;
  const shot = await send2('Page.captureScreenshot', { format: 'png', fromSurface: true, captureBeyondViewport: true, clip: { x: 0, y: 0, width, height: full, scale: 1 } });
  writeFileSync(path, Buffer.from(shot.result.data, 'base64'));
  console.log('shared shot', path, width + 'x' + full);
  ws2.close();
}

await send('Page.enable');
await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1200, deviceScaleFactor: 1, mobile: false });

await send('Page.navigate', { url: 'http://127.0.0.1:5188/studio.html' });
await waitFor(`!!document.querySelector('.preview-frame')`);
await sleep(1000);

// desktop: React live preview
await evaluate(`[...document.querySelectorAll('.device-switch button')].find(b => b.textContent === 'desktop')?.click()`);
await sleep(500);
let rect = await shotClip((process.env.STUDIO_OUT || '/downloads') + '/parity-react-desktop.png', '.preview-frame');
console.log('react desktop rect', JSON.stringify(rect));

// desktop: shared renderer snapshot
await evaluate(`[...document.querySelectorAll('button')].find(b => b.textContent === 'Shared renderer')?.click()`);
await waitFor(`!!document.querySelector('.shared-preview iframe')`);
await sleep(1500);
const fw = Math.round(rect.width); await shotShared((process.env.STUDIO_OUT || '/downloads') + '/parity-shared-desktop.png', fw, 900);
await evaluate(`[...document.querySelectorAll('button')].find(b => b.textContent === 'Close shared snapshot')?.click()`);
await sleep(300);

// mobile: React live preview
await evaluate(`[...document.querySelectorAll('.device-switch button')].find(b => b.textContent === 'mobile')?.click()`);
await sleep(500);
rect = await shotClip((process.env.STUDIO_OUT || '/downloads') + '/parity-react-mobile.png', '.preview-frame');
console.log('react mobile rect', JSON.stringify(rect));

// mobile: shared renderer snapshot
await evaluate(`[...document.querySelectorAll('button')].find(b => b.textContent === 'Shared renderer')?.click()`);
await waitFor(`!!document.querySelector('.shared-preview iframe')`);
await sleep(1500);
await shotShared((process.env.STUDIO_OUT || '/downloads') + '/parity-shared-mobile.png', 390, 844);

console.log('PARITY CAPTURE DONE');
ws.close();
process.exit(0);
