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

// 1. open studio, connected to the local test backend
await send('Page.navigate', { url: 'http://127.0.0.1:5188/studio.html' });
await waitFor(`document.querySelector('.studio-notice')?.textContent.includes('local test backend')`);
console.log('1. studio connects to the local test backend  OK');
await shot((process.env.STUDIO_OUT || '/downloads') + '/e2e-1-connected.png');

// 2. edit the first section heading through the real inspector control
const EDITED = 'Edited in the browser and saved to the API';
await waitFor(`!!document.querySelector('.studio-inspector textarea')`);
await evaluate(`(() => {
  const el = document.querySelector('.studio-inspector textarea');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  setter.call(el, ${JSON.stringify(EDITED)});
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await waitFor(`document.querySelector('.preview-frame h1')?.textContent === ${JSON.stringify(EDITED)}`);
console.log('2. heading edited through the inspector, live preview updated  OK');

// 2b. change the accent color and typeface through the real inspector controls, so the
// settings roundtrip is observable
await evaluate(`(() => {
  const color = document.querySelector('input[aria-label="accent color"]');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(color, '#e0218a');
  color.dispatchEvent(new Event('input', { bubbles: true }));
  const sel = [...document.querySelectorAll('.studio-inspector select')][0];
  const ssetter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
  ssetter.call(sel, 'serif');
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  const range = document.querySelector('.studio-inspector input[type=range]');
  const rsetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  rsetter.call(range, '4');
  range.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await sleep(600);
console.log('2b. accent color + typeface + corner radius changed through the inspector  OK');

// 2c. edit header links, add a header action and rewrite footer lines through the real inspector
await evaluate(`(() => {
  const setIn = (el, v) => { Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })); };
  setIn(document.querySelector('input[aria-label="links label 1"]'), 'Atelier');
  setIn(document.querySelector('input[aria-label="links link 1"]'), '/atelier');
  setIn(document.querySelector('input[aria-label="links label 2"]'), 'Journal');
  setIn(document.querySelector('input[aria-label="actions label 1"]'), 'Visit us');
  return true;
})()`);
await sleep(300);
await evaluate(`(() => { const ta = document.querySelector('textarea[aria-label="footer lines"]'); Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set.call(ta, 'Atelier Nour, Suez\\nOpen Sat to Thu'); ta.dispatchEvent(new Event('input', { bubbles: true })); return true; })()`);
await sleep(600);
console.log('2c. header links, action and footer lines edited through the inspector  OK');

// 3. save to the backend through the bridge
await evaluate(`(() => { [...document.querySelectorAll('button')].find(b => b.textContent === 'Save to local backend')?.click(); return true; })()`);
await waitFor(`document.querySelector('.studio-notice')?.textContent.includes('Draft and site settings saved to the local test backend')`);
console.log('3. save to local backend -> draft saved  OK');

// 3b. the settings record exists server-side with the new theme
const settings = await evaluate(`fetch('/__studio/api/site/settings', { credentials: 'include' }).then(r => r.json())`);
const hv = settings?.value?.header, fv = settings?.value?.footer;
if (hv?.links?.[0]?.label !== 'Atelier' || hv?.links?.[0]?.href !== '/atelier' || hv?.actions?.[0]?.label !== 'Visit us' || fv?.lines?.[0] !== 'Atelier Nour, Suez') {
  throw new Error('chrome settings mismatch: ' + JSON.stringify({ hv, fv }).slice(0, 300));
}
console.log('3a. custom header links/actions/footer present in the saved settings record  OK');
if (settings?.value?.colors?.light?.primary !== '#e0218a' || settings?.value?.typography?.family !== 'serif' || settings?.value?.shape?.radius !== 4) {
  throw new Error('settings record mismatch: ' + JSON.stringify(settings).slice(0, 300));
}
console.log('3b. site settings record saved to the API (accent + serif + radius 4)  OK');

// 3c. partial failure is explicit: with the settings endpoint fault-injected, a save must
// report draft saved + settings FAILED, never whole-save success or whole-save failure
await fetch('http://127.0.0.1:8791/__test/fail-settings?on=true', { method: 'POST' });
await evaluate(`(() => { [...document.querySelectorAll('button')].find(b => b.textContent === 'Save to local backend')?.click(); return true; })()`);
await waitFor(`document.querySelector('.studio-notice')?.textContent.includes('Draft saved, but saving site settings FAILED')`);
console.log('3c. settings fault injected -> save reports draft saved + settings FAILED explicitly  OK');
await fetch('http://127.0.0.1:8791/__test/fail-settings?on=false', { method: 'POST' });
await evaluate(`(() => { [...document.querySelectorAll('button')].find(b => b.textContent === 'Save to local backend')?.click(); return true; })()`);
await waitFor(`document.querySelector('.studio-notice')?.textContent.includes('Draft and site settings saved to the local test backend')`);
console.log('3d. fault cleared -> save reports full success again  OK');

// 4. reload restoration from the server draft (browser storage wiped first)
await evaluate(`localStorage.clear()`);
await send('Page.navigate', { url: 'http://127.0.0.1:5188/studio.html' });
await waitFor(`document.querySelector('.studio-notice')?.textContent.includes('Loaded the draft and site settings from the local test backend')`);
const restored = await evaluate(`document.querySelector('.preview-frame h1')?.textContent`);
if (restored !== EDITED) throw new Error('restored heading mismatch: ' + restored);
console.log('4. reload with wiped browser storage -> draft restored from the API  OK');
const themeCheck = await evaluate(`(() => {
  const site = document.querySelector('.preview-frame .mz-site');
  const cs = getComputedStyle(site);
  return { primary: cs.getPropertyValue('--primary').trim(), font: cs.fontFamily, radius: cs.getPropertyValue('--radius').trim() };
})()`);
if (themeCheck.primary !== '#e0218a' || !/Georgia/.test(themeCheck.font) || themeCheck.radius !== '4px') {
  throw new Error('settings roundtrip mismatch: ' + JSON.stringify(themeCheck));
}
console.log('4b. theme (accent + serif + radius) restored from the API settings, not the browser  OK');
const chromeCheck = await evaluate(`(() => ({
  header: document.querySelector('.preview-frame .mz-site-header')?.textContent || '',
  footer: document.querySelector('.preview-frame .mz-site-footer')?.textContent || '',
  href: document.querySelector('.preview-frame .mz-site-header a[href="/atelier"]')?.textContent || ''
}))()`);
if (!/Atelier/.test(chromeCheck.header) || !/Journal/.test(chromeCheck.header) || !/Visit us/.test(chromeCheck.header) || /Collections|Our story|Search/.test(chromeCheck.header) || !/Atelier Nour, Suez/.test(chromeCheck.footer) || /Prototype preview only/.test(chromeCheck.footer)) {
  throw new Error('chrome roundtrip mismatch: ' + JSON.stringify(chromeCheck));
}
console.log('4c. custom (non-default) header links, action and footer restored from the API after storage wipe  OK');
await shot((process.env.STUDIO_OUT || '/downloads') + '/e2e-2-restored.png');
await evaluate(`(() => { const t = [...document.querySelectorAll('.studio-inspector .panel-title')].find(x => x.textContent.includes('HEADER')); t.scrollIntoView({ block: 'start' }); const f = document.querySelector('.preview-frame .mz-site-footer'); f.scrollIntoView({ block: 'end' }); return true; })()`);
await sleep(500);
await shot((process.env.STUDIO_OUT || '/downloads') + '/e2e-chrome-inspector-footer.png');
console.log('4d. screenshot: chrome inspector controls (restored values) + scrolled restored footer captured');

// 5. fail closed when the session is refused (direct call with a bad token path: use the
//    bridge with the API server down comes later; here the 401 mapping via a bad token
//    is covered by the HTTP suite - check the UI shows failure, not success, on refusal)
// Simulate: point a raw fetch at the bridge after breaking the session is not possible
// (token lives server-side); instead verify the fail-closed copy exists when offline:
console.log('5. (UI refusal path exercised in step 7 after stopping the API)');

// 6. publish (local test) with the confirm dialog
// headless=new does not surface Page.javascriptDialogOpening reliably; stub confirm
await evaluate(`window.confirm = (m) => { window.__confirmText = m; return true; }`);
await evaluate(`(() => { [...document.querySelectorAll('button')].find(b => b.textContent === 'Publish (local test)')?.click(); return true; })()`);
await waitFor(`document.querySelector('.studio-notice')?.textContent.includes('Marked published in the local test database')`);
console.log('6. publish (local test) confirmed -> marked published in the local DB only  OK');
console.log('   confirm dialog text:', await evaluate('window.__confirmText'));
await shot((process.env.STUDIO_OUT || '/downloads') + '/e2e-3-published.png');

// 7. fail-closed error path: stop the API, then a save must show failure, not success
const { execSync } = await import('node:child_process');
try { execSync('pkill -f serve_http.py'); } catch {}
await sleep(1500);
await evaluate(`(() => {
  const el = document.querySelector('.studio-inspector textarea');
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  setter.call(el, ${JSON.stringify(EDITED + ' v2')});
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await evaluate(`(() => { [...document.querySelectorAll('button')].find(b => b.textContent === 'Save to local backend')?.click(); return true; })()`);
await waitFor(`document.querySelector('.studio-notice')?.textContent.includes('Save to local backend failed')`, 40);
console.log('7. backend down -> explicit failure notice, no silent save  OK');
await shot((process.env.STUDIO_OUT || '/downloads') + '/e2e-4-failclosed.png');

console.log('E2E WIRING PASSED');
ws.close();
process.exit(0);
