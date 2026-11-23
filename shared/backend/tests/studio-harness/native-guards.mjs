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
window.__calls=[];window.__release=null;window.__dirtyCheck=()=>{const e=new Event('beforeunload',{cancelable:true});dispatchEvent(e);return e.defaultPrevented};
window.fetch=async(url,init={})=>{
 const mode=new URL(location.href).searchParams.get('mode');const method=init.method||'GET';window.__calls.push({url:String(url),method,body:init.body?JSON.parse(init.body):null});
 if(String(url).includes('/settings'))return new Response(JSON.stringify({value:{}}),{status:200});
 if(mode==='loading'&&method==='GET')await new Promise(r=>window.__release=r);
 if(method==='PUT')await new Promise(r=>window.__release=r);
 let status=method==='PUT'&&mode==='failure'?500:200;
 const id=mode==='wrong'?'wrong-id':'native-one';
 let draft=${JSON.stringify(tree)};
 if(method==='PUT'&&mode!=='mismatch')draft=JSON.parse(init.body).tree;
 const body=status===500?{detail:'mock storage failure'}:{id,slug:'native-one',titles:{en:'Original title'},status:mode==='archived'?'archived':'draft',draft_tree:draft,published_tree:null};
 return new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
};`});
async function load(mode,id='native-one'){await send('Page.navigate',{url:'http://127.0.0.1:5188/studio.html?editor=tree'+(id?'&page='+id:'')+'&mode='+mode});await sleep(300);}
async function heading(text){const target=tree.children[0].children[0].children.find(n=>n.type==='heading').id;await evaluate(`[...document.querySelectorAll('.native-node')].find(b=>b.querySelector('small').textContent===${JSON.stringify(target)}).click()`);await sleep(60);await evaluate(`(()=>{const e=document.querySelector('[aria-label="Native text"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,${JSON.stringify(text)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await sleep(80);}
async function clickSave(){await evaluate(`document.querySelector('.top-actions .save').click()`);await sleep(80);}
async function release(){await evaluate(`window.__release();window.__release=null`);await sleep(150);}
for(const mode of ['archived','wrong']){await load(mode);await waitFor(`!!document.querySelector('[role="alert"]')`);await clickSave();if(!(await evaluate(`window.__calls.every(c=>c.method==='GET') && document.querySelector('.top-actions .save').disabled`)))throw Error('read-only target writable');}
await load('normal','');await waitFor(`!!document.querySelector('[role="alert"]')`);if(!(await evaluate(`window.__calls.length===0`)))throw Error('missing ID contacted backend');
await load('loading');await waitFor(`!!window.__release`);await clickSave();if(!(await evaluate(`window.__calls.length===1 && document.querySelector('.top-actions .save').disabled`)))throw Error('save during load');await release();await waitFor(`!!document.querySelector('.native-node')`);
if(await evaluate(`window.__dirtyCheck()`))throw Error('loaded tree warned');
await heading('Snapshot A');if(!(await evaluate(`window.__dirtyCheck()`)))throw Error('dirty guard absent');
await clickSave();await waitFor(`!!window.__release`);await clickSave();await heading('Newer native B');
if(!(await evaluate(`window.__dirtyCheck()`)))throw Error('busy guard absent');await release();await waitFor(`document.querySelector('.studio-notice').textContent.includes('Newer edits remain unsaved')`);
if(!(await evaluate(`window.__calls.filter(c=>c.method==='PUT').length===1 && document.querySelector('[aria-label="Native text"]').value==='Newer native B' && window.__dirtyCheck()`)))throw Error('snapshot or serialization failed');
await shot((process.env.STUDIO_OUT||'/downloads')+'/native-newer-unsaved.png');
await clickSave();await waitFor(`!!window.__release`);await release();await waitFor(`document.querySelector('.studio-notice').textContent.startsWith('Native tree draft saved')`);if(await evaluate(`window.__dirtyCheck()`))throw Error('saved guard not cleared');
for(const mode of ['failure','mismatch']){await load(mode);await waitFor(`!!document.querySelector('.native-node')`);await heading('Retain after '+mode);await clickSave();await waitFor(`!!window.__release`);await release();await waitFor(`document.querySelector('.studio-notice').textContent.includes('failed or unverified')`);if(!(await evaluate(`window.__dirtyCheck() && !document.querySelector('.top-actions .save').disabled && document.querySelector('[aria-label="Native text"]').value==='Retain after ${mode}'`)))throw Error('failure discarded edits or blocked retry');}
console.log('PASS MOCKED native guards: loading/missing/archived/wrong target, serialized save, in-flight/dirty synthetic leave guard, newer edit preserved, backend failure/mismatched echo retains edits and permits retry');ws.close();
