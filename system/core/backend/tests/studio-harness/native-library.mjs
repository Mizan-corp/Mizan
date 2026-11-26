// MOCKED native structure/content/theme acceptance driver. Isolated local Vite + CDP only.
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

const second={id:'n_secondroot',type:'section',settings:{desktop:{padding:'s'},mobile:{padding:'none'}},content:{},children:[{id:'n_differentrow',type:'columns',settings:{desktop:{columns:1,gap:'s'}},content:{},children:[{id:'n_customcolumn',type:'column',settings:{desktop:{align:'center'}},content:{},children:[{id:'n_originaltitle',type:'heading',settings:{desktop:{level:3},mobile:{align:'end'}},content:{en:{text:'Distinct page'},ar:{text:'صفحة أخرى'}}},{id:'n_originalrich',type:'text',settings:{desktop:{variant:'body'}},content:{en:{html:'<p><strong>Retain this markup</strong></p>'}}},{id:'n_originalbutton',type:'button',settings:{desktop:{style:'ghost'}},content:{en:{label:'Contact us',href:'/contact'}}}]}]}]};

const theme={header:{brand:'Saved native brand',links:[{label:'Story',href:'/story'}]},footer:{lines:['Saved shared footer'],links:[{label:'Returns',href:'/returns'}]},colors:{light:{background:'#f3f5f2',foreground:'#122c2b',primary:'#c3ed8d'}},typography:{family:'serif'},shape:{radius:12},unowned:{retain:'untouched'}};
await send('Page.addScriptToEvaluateOnNewDocument',{source:`
window.__calls=[];window.__confirm=true;window.__listFail=false;window.__theme=${JSON.stringify(theme)};window.confirm=()=>window.__confirm;
if(!sessionStorage.getItem('structure-tree'))sessionStorage.setItem('structure-tree',${JSON.stringify(JSON.stringify(tree))});
window.fetch=async(url,init={})=>{
 const path=String(url),method=init.method||'GET';window.__calls.push({path,method,body:init.body?JSON.parse(init.body):null});
 if(path.endsWith('/site/pages')&&window.__listFail)return new Response('{}',{status:503});
 if(path.endsWith('/site/pages'))return new Response(JSON.stringify({items:[{id:'native-one',slug:'native-one',titles:{en:'Original page'},status:'draft'},{id:'native-two',slug:'native-two',titles:{en:'Second page'},status:'published'},{id:'archived',slug:'archived',titles:{en:'Archived page'},status:'archived'}]}),{status:200});
 if(path.endsWith('/site/settings'))return new Response(JSON.stringify({value:window.__theme}),{status:200});
 if(method==='PUT')sessionStorage.setItem('structure-tree',JSON.stringify(JSON.parse(init.body).tree));
 return new Response(JSON.stringify({id:path.includes('native-two')?'native-two':'native-one',slug:path.includes('native-two')?'native-two':'native-one',titles:{en:path.includes('native-two')?'Second page':'Original page'},status:'draft',edit_token:'a'.repeat(64),draft_tree:JSON.parse(sessionStorage.getItem('structure-tree')),published_tree:null}),{status:200});
};`});
await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html?editor=tree&page=native-one'});await sleep(400);await waitFor(`!!document.querySelector('.native-node')`);
async function selectType(type){await evaluate(`[...document.querySelectorAll('.native-node')].find(b=>b.dataset.nodeType===${JSON.stringify(type)}).click()`);await sleep(80);}
async function click(text){await evaluate(`[...document.querySelectorAll('button,[role="button"]')].find(b=>b.textContent===${JSON.stringify(text)}||b.getAttribute('aria-label')===${JSON.stringify(text)}).click()`);await sleep(80);}





async function dragCard(name,touch=false){const a=await evaluate(`(()=>{const e=[...document.querySelectorAll('.library-cards article')].find(e=>e.getAttribute('aria-label')==='Preview '+${JSON.stringify(name)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+25}})()`);const b=await evaluate(`(()=>{document.querySelector('.studio-canvas').scrollTop=0;const e=document.querySelector('.native-drag-preview .mz-node');const r=e.getBoundingClientRect();return {x:r.x+r.width-15,y:r.y+80}})()`);if(touch){await send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});await send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:a.x,y:a.y,id:1}]});await send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:b.x,y:b.y,id:1}]});}else{await send('Input.dispatchMouseEvent',{type:'mousePressed',x:a.x,y:a.y,button:'left',clickCount:1});await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:b.x,y:b.y,button:'left',buttons:1});}await sleep(80);if(!(await evaluate(`!!document.querySelector('.native-drop-marker')`)))throw Error('library drop marker missing');await shot('/downloads/native-library-drop.png');if(touch){await send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await send('Emulation.setTouchEmulationEnabled',{enabled:false})}else await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:b.x,y:b.y,button:'left',clickCount:1});await sleep(100);if(await evaluate(`!!document.querySelector('[role="dialog"]')`))throw Error('drag opened preview')}
await click('+ Add');await shot('/downloads/native-library-blocks.png');
await click('Hero sections');if(await evaluate(`document.querySelectorAll('[data-library-mode="blocks"] article').length`)!==2)throw Error('hero variants missing');await shot('/downloads/native-library-categories.png');await click('Feedback');if(await evaluate(`document.querySelectorAll('[data-library-mode="blocks"] article').length`)!==2)throw Error('feedback variants missing');await click('Pricing');await shot('/downloads/native-library-pricing.png');await click('Preview Three plans');await shot('/downloads/native-library-pricing-preview.png');await click('Cancel preview');await click('All');
const generated=await evaluate(`(async()=>{const {blockCatalog,createPreset}=await import('/src/features/studio/nativePresets.ts');const tree=${JSON.stringify(tree)};return blockCatalog.map(b=>({name:b.name,tree:{...tree,children:[createPreset(tree,b.id)]}}))})()`);writeFileSync('/downloads/native-category-trees.json',JSON.stringify(generated));

async function input(selector,value){await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}))})()`);await sleep(50)}
await input('[aria-label="Search blocks"]','benefits');if(await evaluate(`document.querySelectorAll('[data-library-mode="blocks"] article').length`)!==1)throw Error('block search failed');
await dragCard('Three benefits');if(!(await evaluate(`document.querySelector('.simple-save-state').textContent==='Unsaved changes'`)))throw Error('block not inserted');
await click('Undo');await click('+ Add');await input('[aria-label="Search blocks"]','quote');await dragCard('Featured quote',true);await click('Undo');await click('Assets');await evaluate(`document.querySelector('.asset-details>button')?.click()`);await click('Inspect Independent studio');await click('Preview this page starter');await click('Cancel preview');await evaluate(`document.querySelector('.studio-canvas').scrollTop=0`);await shot('/downloads/native-library-templates.png');
await dragCard('Independent studio');if(!(await evaluate(`document.querySelector('.studio-canvas .preview-frame').textContent.includes('Independent ideas.')`)))throw Error('template drag failed');await click('Undo');await click('Assets');await evaluate(`document.querySelector('.asset-details>button')?.click()`);await click('Inspect Independent studio');await click('Preview this page starter');await click('Cancel preview');
await click('Preview Independent studio');
await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await sleep(50);if(await evaluate(`!!document.querySelector('[role="dialog"]')`))throw Error('Escape failed');
await click('Preview Independent studio');await evaluate(`document.querySelector('.library-modal footer button:last-child').focus()`);await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});if(!(await evaluate(`document.activeElement.getAttribute('aria-label')==='Close library preview'`)))throw Error('modal focus escaped');
await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await sleep(100);if(!(await evaluate(`getComputedStyle(document.querySelector('.library-modal .mz-columns')).gridTemplateColumns.split(' ').length===1`)))throw Error('mobile preview failed to stack');await shot('/downloads/native-library-mobile.png');if(!(await evaluate(`document.querySelector('.library-modal').getBoundingClientRect().width<=390 && document.querySelector('.library-modal footer button:last-child').getBoundingClientRect().bottom<=844`)))throw Error('mobile modal clipping');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});await sleep(50);await shot('/downloads/native-library-preview.png');
if(!(await evaluate(`!!document.querySelector('[role="dialog"] .mz-heading') && !document.querySelector('.simple-save-state').textContent.includes('Unsaved')`)))throw Error('preview mutated or not rendered');
await evaluate(`window.__confirm=false`);await click('Use this template');if(!(await evaluate(`!!document.querySelector('[role="dialog"]')`)))throw Error('cancel template failed');
await evaluate(`window.__confirm=true`);await click('Use this template');
if(!(await evaluate(`!document.querySelector('[role="dialog"]') && document.querySelector('.studio-canvas .preview-frame').textContent.includes('Independent ideas. Thoughtfully made.')`)))throw Error('template not applied');
await click('Undo');if(!(await evaluate(`document.querySelector('.studio-canvas .preview-frame').textContent.includes('Better things.')`)))throw Error('template undo lost original');await click('Redo');await click('Save');
await send('Page.reload');await sleep(200);await waitFor(`!!document.querySelector('.native-node')`);if(!(await evaluate(`document.querySelector('.studio-canvas .preview-frame').textContent.includes('Independent ideas. Thoughtfully made.')`)))throw Error('template save/reload failed');
await click('Pages');await waitFor(`document.querySelectorAll('.explorer-pages button').length===3`);await shot('/downloads/native-library-explorer.png');
await evaluate(`window.__listFail=true`);await click('Refresh pages');await waitFor(`!!document.querySelector('[data-library-mode="explorer"] [role="alert"]')`);if(!(await evaluate(`document.querySelector('.document-title').textContent.includes('Original page')`)))throw Error('list failure changed page');await evaluate(`window.__listFail=false`);await click('Try again');await waitFor(`document.querySelectorAll('.explorer-pages button').length===3`);
if(!(await evaluate(`document.querySelectorAll('.explorer-pages button')[2].disabled`)))throw Error('archive writable');
await input('[aria-label="Search explorer"]','second');if(await evaluate(`document.querySelectorAll('.explorer-pages button').length`)!==1)throw Error('explorer search failed');
await input('[aria-label="Search explorer"]','');
await click('+ Add');await dragCard('Featured quote');await click('Pages');await waitFor(`document.querySelectorAll('.explorer-pages button').length===3`);
await evaluate(`window.__confirm=false;document.querySelectorAll('.explorer-pages button')[1].click()`);await sleep(60);if(!(await evaluate(`new URL(location.href).searchParams.get('page')==='native-one' && document.querySelector('.simple-save-state').textContent==='Unsaved changes'`)))throw Error('declined switch lost dirty work');
await evaluate(`window.__confirm=true;document.querySelectorAll('.explorer-pages button')[1].click()`);await waitFor(`document.querySelector('.document-title').textContent.includes('Second page')`);
if(!(await evaluate(`new URL(location.href).searchParams.get('page')==='native-two' && document.querySelector('.simple-save-state').textContent==='Saved to local test copy'`)))throw Error('explicit switch failed');
console.log('PASS MOCKED library search/insert, complete native template preview/cancel/apply/undo/redo/save/reload, real page-list shaped explorer/search/archived refusal and dirty switch cancel/confirmed identity');ws.close();
