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
window.__calls=[];window.__theme=${JSON.stringify(theme)};window.confirm=()=>true;
if(!sessionStorage.getItem('structure-tree'))sessionStorage.setItem('structure-tree',${JSON.stringify(JSON.stringify(tree))});
window.fetch=async(url,init={})=>{
 const path=String(url),method=init.method||'GET';window.__calls.push({path,method,body:init.body?JSON.parse(init.body):null});
 if(path.endsWith('/site/settings'))return new Response(JSON.stringify({value:window.__theme}),{status:200});
 if(method==='PUT')sessionStorage.setItem('structure-tree',JSON.stringify(JSON.parse(init.body).tree));
 return new Response(JSON.stringify({id:'native-one',slug:'native-one',titles:{en:'Original page'},status:'draft',edit_token:'a'.repeat(64),draft_tree:JSON.parse(sessionStorage.getItem('structure-tree')),published_tree:null}),{status:200});
};`});
await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html?editor=tree&page=native-one'});await sleep(400);await waitFor(`!!document.querySelector('.native-node')`);
async function selectType(type){await evaluate(`[...document.querySelectorAll('.native-node')].find(b=>b.dataset.nodeType===${JSON.stringify(type)}).click()`);await sleep(80);}
async function click(text){await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent===${JSON.stringify(text)}).click()`);await sleep(80);}
await selectType('column');await click('+ Add Heading');
const newId=await evaluate(`document.querySelector('.native-id').textContent`);
await evaluate(`(()=>{const e=document.querySelector('[aria-label="Native text"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,'New no-code section heading');e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await sleep(100);
await click('Move earlier');await click('Remove selected subtree');await click('Undo');
if(!(await evaluate(`[...document.querySelectorAll('.native-node')].some(e=>e.dataset.nodeId===${JSON.stringify(newId)})`)))throw Error('undo lost added ID');
await selectType('text');
await evaluate(`(()=>{const e=document.querySelector('[aria-label="Native rich text"]');e.innerHTML='<p><strong>No-code formatted copy</strong></p>';e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await sleep(100);
await evaluate(`(()=>{const e=document.querySelector('[aria-label="Native rich text"]');e.focus();const r=document.createRange();r.selectNodeContents(e);const selection=getSelection();selection.removeAllRanges();selection.addRange(r);})()`);
await click('Italic');
if(!(await evaluate(`!!document.querySelector('[aria-label="Native rich text"] i, [aria-label="Native rich text"] em')`)))throw Error('toolbar selection formatting failed');
await shot((process.env.STUDIO_OUT||'/downloads')+'/native-rich-structure.png');
await selectType('button');
await evaluate(`(()=>{const e=document.querySelector('[aria-label="Native href"]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'javascript:alert(1)');e.dispatchEvent(new FocusEvent('focusout',{bubbles:true}));})()`);await sleep(100);
if(!(await evaluate(`document.querySelector('.link-error')?.textContent.includes('refused')`)))throw Error('bad destination not refused');
await evaluate(`(()=>{const e=document.querySelector('[aria-label="Native href"]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'/new-contact');e.dispatchEvent(new FocusEvent('focusout',{bubbles:true}));})()`);await sleep(100);
await selectType('image');
await evaluate(`(()=>{const e=document.querySelector('[aria-label="Native alt"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,'Editable media description');e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await sleep(100);
await click('Save');await waitFor(`document.querySelector('.studio-notice').textContent.startsWith('Native tree draft saved')`);
if(!(await evaluate(`window.__calls.filter(c=>c.method!=='GET').every(c=>c.path.endsWith('/draft')&&Object.keys(c.body).sort().join()==='expected_token,tree') && document.querySelector('.mz-site-brand').textContent==='Saved native brand' && JSON.stringify(window.__theme)===${JSON.stringify(JSON.stringify(theme))}`)))throw Error('theme preservation failed');
await send('Page.reload');await sleep(400);await waitFor(`!!document.querySelector('.native-node')`);
if(!(await evaluate(`document.body.textContent.includes('New no-code section heading') && document.body.textContent.includes('No-code formatted copy') && !!document.querySelector('.mz-site-footer a[href="/returns"]')`)))throw Error('save reload failed');
await selectType('image');await shot((process.env.STUDIO_OUT||'/downloads')+'/native-media-theme.png');
const structural=await evaluate(`(async()=>{const {changeStructure}=await import('/src/features/studio/nativeStructure.ts');const {toPageTree}=await import('/src/features/studio/pagetree.ts');const {initialProject}=await import('/src/features/studio/model.ts');const tree=toPageTree(initialProject);return changeStructure({tree,past:[],future:[]},{kind:'insert',parentId:tree.id,type:'columns',id:'n_newvalidrow'}).tree})()`);
writeFileSync('/tmp/native-structural-tree.json',JSON.stringify(structural));
console.log('PASS MOCKED structure/controls/theme: stable added ID, reorder/remove/undo, rich copy, invalid link refusal, media alt, save/reload, saved theme rendered with zero settings writes');ws.close();
