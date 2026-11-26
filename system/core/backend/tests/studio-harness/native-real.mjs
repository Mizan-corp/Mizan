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
const tree=await evaluate(`(async()=>{const {toPageTree}=await import('/src/platform/site/studio/pagetree.ts');const {initialProject}=await import('/src/platform/site/studio/model.ts');return toPageTree(initialProject)})()`);


// Real authenticated loopback bridge, no fetch overrides.
const created=await evaluate(`(async()=>{const r=await fetch('/__studio/api/site/pages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slug:'native-real-'+Date.now(),titles:{en:'Real native page'},tree:${JSON.stringify(tree)}})});if(!r.ok)throw Error('create '+r.status);return r.json()})()`);
const url='http://127.0.0.1:5188/studio.html?editor=tree&page='+created.id;
await send('Page.navigate',{url});await sleep(250);await waitFor(`!!document.querySelector('.native-node')`);
const heading=tree.children[0].children[0].children.find(n=>n.type==='heading').id;
async function edit(text){await evaluate(`document.querySelector('[data-node-id="${heading}"]').click()`);await sleep(50);await evaluate(`(()=>{const e=document.querySelector('[aria-label="Native text"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,${JSON.stringify(text)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await sleep(60);}
async function save(){await evaluate(`document.querySelector('.top-actions .save').click()`);}
await edit('Native real first save');await save();await waitFor(`document.querySelector('.studio-notice').textContent.startsWith('Native tree draft saved')`);
const snapshot=await evaluate(`fetch('/__studio/api/site/pages/${created.id}').then(r=>r.json())`);
const expected=structuredClone(tree);expected.children[0].children[0].children.find(n=>n.id===heading).content.en.text='Native real first save';
if(JSON.stringify(snapshot.draft_tree)!==JSON.stringify(expected)){
 const key=v=>JSON.stringify(v, Object.keys(v).sort()); // compare using page-native canonicalizer below
 if(!(await evaluate(`(async()=>{const {nativeTreeKey}=await import('/src/platform/site/studio/nativeTree.ts');return nativeTreeKey(${JSON.stringify(snapshot.draft_tree)})===nativeTreeKey(${JSON.stringify(expected)})})()`)))throw Error('real save changed unrelated tree');
}
await send('Page.reload');await sleep(250);await waitFor(`!!document.querySelector('.native-node')`);await edit('Local edits must survive conflict');
// Another authenticated client writes with its freshly loaded token.
await evaluate(`(async()=>{const d=await fetch('/__studio/api/site/pages/${created.id}').then(r=>r.json());const t=structuredClone(d.draft_tree);t.children[0].children[0].children.find(n=>n.id==='${heading}').content.en.text='Other session won';const r=await fetch('/__studio/api/site/pages/${created.id}/draft',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tree:t,expected_token:d.edit_token})});if(!r.ok)throw Error('other save '+r.status)})()`);
await save();await waitFor(`!!document.querySelector('.native-conflict')`);
if(!(await evaluate(`document.querySelector('[aria-label="Native text"]').value==='Local edits must survive conflict' && document.querySelector('.top-actions .save').disabled`)))throw Error('conflict lost edits or allowed repeat save');
const server=await evaluate(`fetch('/__studio/api/site/pages/${created.id}').then(r=>r.json())`);if(server.draft_tree.children[0].children[0].children.find(n=>n.id===heading).content.en.text!=='Other session won')throw Error('stale overwrote server');
await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:'/downloads',eventsEnabled:true});
await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Export my unsaved tree').click()`);await sleep(180);
const {readFileSync}=await import('node:fs');const exported=JSON.parse(readFileSync('/downloads/mizan-unsaved-tree.json','utf8'));if(exported.children[0].children[0].children.find(n=>n.id===heading).content.en.text!=='Local edits must survive conflict')throw Error('export lost unsaved tree');
await shot('/downloads/native-real-conflict.png');

await send('Page.reload');await sleep(250);await waitFor(`!!document.querySelector('.native-node')`);await edit('Deliberately reloaded and saved');await save();await waitFor(`document.querySelector('.studio-notice').textContent.startsWith('Native tree draft saved')`);await shot('/downloads/native-real-saved.png');
await evaluate(`document.querySelector('[data-node-id="${heading}"]').click()`);await sleep(50);await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b=>b.textContent==='Animate').click()`);await sleep(50);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Soft zoom').click()`);await save();await waitFor(`document.querySelector('.simple-save-state').textContent==='Saved to local test copy'`);const motionSaved=await evaluate(`fetch('/__studio/api/site/pages/${created.id}').then(r=>r.json())`);if(motionSaved.draft_tree.children[0].children[0].children.find(n=>n.id===heading).settings.desktop.animation!=='zoom')throw Error('real motion persistence failed');await send('Page.reload');await sleep(200);await waitFor(`!!document.querySelector('.mz-animation-zoom')`);
console.log('PASS REAL REDUCED API native motion save/reload.');
// Actual library template save, real workspace page list and explicit Explorer switching.
await evaluate(`[...document.querySelectorAll('.workspace-modes button')].find(b=>b.textContent==='Assets').click()`);await sleep(60);
await evaluate(`document.querySelector('[aria-label="Inspect Creative services"]').click()`);await sleep(50);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Preview this page starter').click()`);await sleep(50);await sleep(60);await evaluate(`window.confirm=()=>true;[...document.querySelectorAll('button')].find(b=>b.textContent==='Use this template').click()`);await sleep(60);await save();await waitFor(`document.querySelector('.simple-save-state').textContent==='Saved to local test copy'`);
const librarySaved=await evaluate(`fetch('/__studio/api/site/pages/${created.id}').then(r=>r.json())`);if(librarySaved.draft_tree.id!==tree.id||librarySaved.draft_tree.children.length!==4)throw Error('real template persistence/root failed');
await send('Page.reload');await sleep(200);await waitFor(`document.querySelector('.studio-canvas .preview-frame')?.textContent.includes('A fresh perspective for your next project.')`);
const other=await evaluate(`(async()=>{const r=await fetch('/__studio/api/site/pages',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({slug:'explorer-other-'+Date.now(),titles:{en:'Explorer second page'},tree:${JSON.stringify(tree)}})});if(!r.ok)throw Error('second create '+r.status);return r.json()})()`);
await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b=>b.textContent==='Pages').click()`);await waitFor(`document.querySelector('.explorer-pages')?.textContent.includes('Explorer second page')`);await shot('/downloads/native-library-real-explorer.png');
await evaluate(`[...document.querySelectorAll('.explorer-pages button')].find(b=>b.textContent.includes('Explorer second page')).click()`);await waitFor(`new URL(location.href).searchParams.get('page')==='${other.id}' && document.querySelector('.document-title')?.textContent.includes('Explorer second page')`);
await evaluate(`[...document.querySelectorAll('.explorer-pages button')].find(b=>b.textContent.includes('Real native page')).click()`);await waitFor(`new URL(location.href).searchParams.get('page')==='${created.id}' && document.querySelector('.studio-canvas .preview-frame')?.textContent.includes('A fresh perspective for your next project.')`);
// Native shared design is a separate settings save, never a page draft save.
await evaluate(`window.confirm=()=>true`);
await evaluate(`[...document.querySelectorAll('.workspace-modes button')].find(b=>b.textContent==='Design').click()`);await waitFor(`!![...document.querySelectorAll('button')].find(b=>b.textContent==='Headers')`);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Headers').click()`);await waitFor(`!!document.querySelector('[aria-label="Shared brand"]')`);
console.log('shared loaded');await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent.endsWith('Centered navigation')).click()`);await sleep(80);await evaluate(`(()=>{const e=document.querySelector('[aria-label="Shared brand"]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'Shared test brand');e.dispatchEvent(new Event('input',{bubbles:true}))})()`);await sleep(80);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Save shared site design').click()`);await waitFor(`document.querySelector('.native-shared-chrome').textContent.includes('Shared test-site design saved')`);await shot('/downloads/native-shared-saved.png');
const shared=await evaluate(`fetch('/__studio/api/site/settings').then(r=>r.json())`);if(shared.value.header.brand!=='Shared test brand'||shared.value.header.layout!=='centered')throw Error('shared design not persisted');
await evaluate(`(()=>{const e=document.querySelector('[aria-label="Shared brand"]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'Keep my local shared design');e.dispatchEvent(new Event('input',{bubbles:true}))})()`);
await evaluate(`(async()=>{const d=await fetch('/__studio/api/site/settings').then(r=>r.json());d.value.header.brand='Other session shared design';const r=await fetch('/__studio/api/site/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:d.value,expected_token:d.edit_token})});if(!r.ok)throw Error('shared other client failed')})()`);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Save shared site design').click()`);await waitFor(`document.querySelector('.native-shared-chrome').textContent.includes('Saving paused')`);if(!(await evaluate(`document.querySelector('[aria-label="Shared brand"]').value==='Keep my local shared design'`)))throw Error('shared conflict lost work');await shot('/downloads/native-shared-conflict.png');
await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Reload shared design').click()`);await waitFor(`document.querySelector('[aria-label="Shared brand"]').value==='Other session shared design'`);
await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Footers').click()`);await sleep(50);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent.endsWith('Stacked footer')).click()`);await sleep(60);await evaluate(`(()=>{const e=document.querySelector('[aria-label="Shared footer lines"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,'Shared footer for every page');e.dispatchEvent(new Event('input',{bubbles:true}))})()`);await sleep(60);await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent==='Save shared site design').click()`);await waitFor(`document.querySelector('.native-shared-chrome').textContent.includes('Shared test-site design saved')`);
await evaluate(`document.querySelector('.studio-canvas .mz-site-footer').scrollIntoView({block:'center'});document.querySelector('.studio-canvas .mz-site-footer').click()`);await sleep(80);if(!(await evaluate(`!!document.querySelector('[aria-label="Shared footer lines"]')`)))throw Error('canvas footer targeting failed');await shot('/downloads/native-shared-footer.png');
const bodyAfterShared=await evaluate(`fetch('/__studio/api/site/pages/${created.id}').then(r=>r.json())`);if(JSON.stringify(bodyAfterShared.draft_tree)!==JSON.stringify(librarySaved.draft_tree))throw Error('shared save changed page body');
await evaluate(`[...document.querySelectorAll('.studio-rail button')].find(b=>b.textContent==='Pages').click()`);await waitFor(`document.querySelector('.explorer-pages')?.textContent.includes('Explorer second page')`);await evaluate(`[...document.querySelectorAll('.explorer-pages button')].find(b=>b.textContent.includes('Explorer second page')).click()`);await waitFor(`new URL(location.href).searchParams.get('page')==='${other.id}' && document.querySelector('.studio-canvas .mz-site-footer')?.textContent.includes('Shared footer for every page')`);
console.log('PASS shared footer save, canvas targeting, unrelated page body preservation and second-page shared render');
console.log('PASS REAL REDUCED API shared header variant/edit/save and independent-client settings conflict/local retention');
console.log('PASS REAL REDUCED API: template save/reload/root identity and real Explorer page-list/switch/return preserved tree.');
console.log('PASS REAL REDUCED API: native exact tree save/reload, other-session stale conflict, retained local edits/server content, save paused, deliberate reload/fresh save. Not full app.');ws.close();
