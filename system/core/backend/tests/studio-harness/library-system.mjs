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




await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html'});
await waitFor(`!!document.querySelector('.studio-inspector')`);
const tree=await evaluate(`(async()=>{const {toPageTree}=await import('/src/features/studio/pagetree.ts');const {initialProject}=await import('/src/features/studio/model.ts');return toPageTree(initialProject)})()`);


// Real authenticated loopback bridge, no fetch overrides.
const created=await evaluate(`(async()=>{const r=await fetch('/__studio/api/site/pages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slug:'native-real-'+Date.now(),titles:{en:'Real native page'},tree:${JSON.stringify(tree)}})});if(!r.ok)throw Error('create '+r.status);return r.json()})()`);
const url='http://127.0.0.1:5188/studio.html?editor=tree&page='+created.id;
await send('Page.navigate',{url});await sleep(250);await waitFor(`!!document.querySelector('.native-node')`);

const original=await evaluate(`fetch('/__studio/api/site/pages/${created.id}').then(r=>r.json())`);
await evaluate(`[...document.querySelectorAll('.workspace-modes button')].find(b=>b.textContent==='Assets').click()`);await waitFor(`!!document.querySelector('[aria-label="Search entire library"]')`);await shot('/downloads/native-library-system.png');
await evaluate(`document.querySelector('[aria-label="Inspect Independent studio"]').click()`);await waitFor(`document.querySelector('.asset-details')?.textContent.includes('Intro + image')`);if(!(await evaluate(`(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);return ids.length===new Set(ids).size})()`)))throw Error('asset preview duplicated live canvas IDs');await shot('/downloads/native-library-relationships.png');
await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Preview this page starter').click()`);await waitFor(`!!document.querySelector('.asset-summary')`);await shot('/downloads/native-library-contents.png');await evaluate(`document.querySelector('[aria-label="Close library preview"]').click()`);
await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Back to all library assets').click()`);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Color palettes').click()`);await evaluate(`document.querySelector('[aria-label="Inspect Ink & paper"]').click()`);await waitFor(`!!document.querySelector('.identity-swatches')`);await shot('/downloads/native-library-palette.png');
const after=await evaluate(`fetch('/__studio/api/site/pages/${created.id}').then(r=>r.json())`);if(JSON.stringify(original)!==JSON.stringify(after))throw Error('discovery mutated page');
await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Open coordinated site design').click()`);await waitFor(`!!document.querySelector('[aria-label="Stage Ink & paper"]')`);const settingsBefore=await evaluate(`fetch('/__studio/api/site/settings').then(r=>r.json())`);if(!(await evaluate(`document.querySelector('[aria-label="Site color primary"]').value==='#263F36' && document.querySelector('.native-shared-chrome').textContent.includes('Selected identity staged')`)))throw Error('selected design identity was not routed exactly');await sleep(60);await shot('/downloads/native-design-staged.png');
await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Preview staged design on canvas').click()`);await sleep(80);if(!(await evaluate(`getComputedStyle(document.querySelector('.studio-canvas .mz-site')).fontFamily.includes('serif') && document.querySelector('.canvas-bar').textContent.includes('not saved') && document.querySelector('.simple-save-state').textContent==='Shared design not saved' && document.querySelector('.top-actions .save').textContent==='Save page only'`)))throw Error('full staged preview missing');await shot('/downloads/native-design-canvas-preview.png');await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await sleep(80);await shot('/downloads/native-design-canvas-mobile.png');if(!(await evaluate(`document.documentElement.scrollWidth<=390 && document.querySelector('.workspace-modes').getBoundingClientRect().right<=390`)))throw Error('preview mobile overflow');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});await sleep(50);await evaluate(`document.querySelector('.top-actions .save').click()`);await waitFor(`document.querySelector('.studio-notice').textContent.startsWith('Native tree draft saved')`);const previewOnly=await evaluate(`fetch('/__studio/api/site/settings').then(r=>r.json())`);if(JSON.stringify(previewOnly)!==JSON.stringify(settingsBefore))throw Error('canvas preview wrote settings');await evaluate(`[...document.querySelectorAll('.workspace-modes button')].find(b=>b.textContent==='Build').click()`);await sleep(80);if(await evaluate(`document.querySelector('.canvas-bar').textContent.includes('not saved')`))throw Error('preview escaped Design scope');await evaluate(`[...document.querySelectorAll('.workspace-modes button')].find(b=>b.textContent==='Design').click()`);await sleep(80);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Show saved canvas').click()`);await sleep(50);

const notSaved=await evaluate(`fetch('/__studio/api/site/settings').then(r=>r.json())`);if(JSON.stringify(notSaved)!==JSON.stringify(settingsBefore))throw Error('staging saved settings');await evaluate(`window.confirm=()=>true;[...document.querySelectorAll('button')].find(b=>b.textContent==='Save shared site design').click()`);await waitFor(`document.querySelector('.native-shared-chrome')?.textContent.includes('Shared test-site design saved')`);
const savedDesign=await evaluate(`fetch('/__studio/api/site/settings').then(r=>r.json())`);if(savedDesign.value.colors.light.primary!=='#263F36'||savedDesign.value.typography.family!=='serif'||JSON.stringify(savedDesign.value.header)!==JSON.stringify(settingsBefore.value.header)||JSON.stringify(savedDesign.value.footer)!==JSON.stringify(settingsBefore.value.footer))throw Error('identity persistence/preservation failed');await shot('/downloads/native-design-saved.png');
await evaluate(`(()=>{const e=document.querySelector('[aria-label="Site color foreground"]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'#FCFAF5');e.dispatchEvent(new Event('input',{bubbles:true}))})()`);await sleep(60);if(!(await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Save shared site design').disabled && document.querySelector('.native-shared-chrome').textContent.includes('contrast')`)))throw Error('unreadable color save allowed');
await evaluate(`document.querySelector('[aria-label="Stage Ink & paper"]').click()`);await sleep(60);
await evaluate(`document.querySelector('[aria-label="Stage Clear slate"]').click()`);await sleep(60);await evaluate(`(async()=>{const d=await fetch('/__studio/api/site/settings').then(r=>r.json());d.value.shape.radius=13;const r=await fetch('/__studio/api/site/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:d.value,expected_token:d.edit_token})});if(!r.ok)throw Error('other design write failed')})()`);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Save shared site design').click()`);await waitFor(`document.querySelector('.native-shared-chrome').textContent.includes('Saving paused')`);if(!(await evaluate(`document.querySelector('[aria-label="Site color primary"]').value==='#334C80'`)))throw Error('design conflict lost local staged palette');await shot('/downloads/native-design-conflict.png');
const bodyAfter=await evaluate(`fetch('/__studio/api/site/pages/${created.id}').then(r=>r.json())`);if(JSON.stringify(bodyAfter)!==JSON.stringify(original))throw Error('design save changed page tree');
await send('Page.reload');await sleep(150);await waitFor(`!!document.querySelector('.native-node')`);if(!(await evaluate(`getComputedStyle(document.querySelector('.studio-canvas .mz-site')).fontFamily.includes('serif')`)))throw Error('saved site font not restored');
await evaluate(`[...document.querySelectorAll('.workspace-modes button')].find(b=>b.textContent==='Assets').click()`);await waitFor(`!!document.querySelector('[aria-label="Search entire library"]')`);await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await sleep(120);await shot('/downloads/native-library-system-mobile.png');
console.log('PASS unified library discovery, real recipe containment, preview contents/requirements, palette nonmutation and mobile');ws.close();
