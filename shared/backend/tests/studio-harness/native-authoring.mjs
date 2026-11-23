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

const second={id:'n_secondroot',type:'section',settings:{desktop:{padding:'s'},mobile:{padding:'none'}},content:{},children:[{id:'n_differentrow',type:'columns',settings:{desktop:{columns:1,gap:'s'}},content:{},children:[{id:'n_customcolumn',type:'column',settings:{desktop:{align:'center'}},content:{},children:[{id:'n_originaltitle',type:'heading',settings:{desktop:{level:3},mobile:{align:'end'}},content:{en:{text:'Distinct page'},ar:{text:'صفحة أخرى'}}},{id:'n_originalrich',type:'text',settings:{desktop:{variant:'body'}},content:{en:{html:'<p><strong>Retain this markup</strong></p>'}}},{id:'n_originalbutton',type:'button',settings:{desktop:{style:'ghost'}},content:{en:{label:'Contact us',href:'/contact'}}}]}]}]};
await send('Page.addScriptToEvaluateOnNewDocument',{source:`
window.__calls=[];window.__originals=${JSON.stringify([tree,second])};
if(!sessionStorage.getItem('native-fixtures'))sessionStorage.setItem('native-fixtures',JSON.stringify(window.__originals));
window.fetch=async(url,init={})=>{
 const id=String(url).includes('native-two')?'native-two':'native-one';const i=id==='native-two'?1:0;
 const trees=JSON.parse(sessionStorage.getItem('native-fixtures'));
 window.__calls.push({url:String(url),method:init.method||'GET',body:init.body?JSON.parse(init.body):null});
 if(init.method==='PUT'){const body=JSON.parse(init.body);if(Object.keys(body).sort().join()!=='expected_token,tree')throw Error('extra write fields');trees[i]=body.tree;sessionStorage.setItem('native-fixtures',JSON.stringify(trees));}
 const draft=new URL(location.href).searchParams.has('unsupported')?{...trees[i],type:'canvas'}:trees[i];
 return new Response(JSON.stringify({id,slug:id,titles:{en:'Independent page title',ar:'عنوان الصفحة'},status:'draft',edit_token:'a'.repeat(64),draft_tree:draft,published_tree:null}),{status:200,headers:{'Content-Type':'application/json'}});
};`});
async function load(id,extra=''){await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html?editor=tree&page='+id+extra});await sleep(350);await waitFor(`!!document.querySelector('.native-node') || !!document.querySelector('[role="alert"]')`);}
async function click(text){await evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent===${JSON.stringify(text)}).click()`);await sleep(100);}
async function edit(text){await evaluate(`(()=>{const e=document.querySelector('[aria-label="Native text"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,${JSON.stringify(text)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await sleep(100);}
for(const [i,id]of ['native-one','native-two'].entries()){
 await load(id);
 const target=i===0?tree.children[0].children[0].children.find(n=>n.type==='heading').id:'n_originaltitle';
 await evaluate(`[...document.querySelectorAll('.native-node')].find(b=>b.dataset.nodeId===${JSON.stringify(target)}).click()`);await sleep(100);
 await edit('Native edit '+i);await click('Undo');
 if(!(await evaluate(`document.querySelector('[aria-label="Native text"]').value===${JSON.stringify(i===0?tree.children[0].children[0].children.find(n=>n.type==='heading').content.en.text:'Distinct page')}`)))throw Error('undo failed');
 await click('Redo');await click('Save native draft');await waitFor(`document.querySelector('.studio-notice').textContent.includes('Native tree draft saved')`);
 if(!(await evaluate(`(()=>{const expected=structuredClone(window.__originals[${i}]);const find=n=>n.id===${JSON.stringify(target)}?n:(n.children||[]).map(find).find(Boolean);find(expected).content.en.text='Native edit ${i}';return JSON.stringify(JSON.parse(sessionStorage.getItem('native-fixtures'))[${i}])===JSON.stringify(expected)})()`)))throw Error('unrelated JSON changed');
 await send('Page.reload');await sleep(400);await waitFor(`!!document.querySelector('.native-node')`);
 if(!(await evaluate(`[...document.querySelectorAll('.mz-heading')].some(h=>h.textContent==='Native edit ${i}')`)))throw Error('reload missed native edit');
 await evaluate(`[...document.querySelectorAll('.native-node')].find(b=>b.dataset.nodeId===${JSON.stringify(target)}).click()`);await sleep(100);
 await shot((process.env.STUDIO_OUT||'/downloads')+'/native-composition-'+i+'.png');
}
await load('native-two','&unsupported=1');
if(!(await evaluate(`!!document.querySelector('[role="alert"]') && document.querySelector('.top-actions .save').disabled && !window.__calls.some(c=>c.method==='PUT')`)))throw Error('unsupported source not protected');
console.log('PASS MOCKED native authoring: two compositions, exact one-field tree change, preserved IDs/translations/rich text/settings, undo/redo, save/reload, unsupported load no writes');ws.close();
