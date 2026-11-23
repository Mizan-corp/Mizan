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

await click('+ Add');
const col=tree.children[0].children[0].id;
async function rect(selector){return evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}})()`)}
async function dragTo(source,target){const a=await rect(source);await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:a.x+a.width/2,y:a.y+a.height/2});await send('Input.dispatchMouseEvent',{type:'mousePressed',x:a.x+a.width/2,y:a.y+a.height/2,button:'left',clickCount:1});const b=await rect(target);await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:b.x+20,y:b.y+2,button:'left',buttons:1});await sleep(100);if(!(await evaluate(`!!document.querySelector('.native-drop-marker')`)))throw Error('drop marker missing');await shot('/downloads/native-drag-position.png');await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:b.x+20,y:b.y+2,button:'left',clickCount:1});await sleep(120);}
const before=await evaluate(`document.querySelectorAll('.native-node').length`);
await dragTo('.native-element-grid button:nth-child(3)','#'+col);
if(await evaluate(`document.querySelectorAll('.native-node').length`)!==before+1)throw Error('pointer palette insertion failed');
await click('Undo');if(await evaluate(`document.querySelectorAll('.native-node').length`)!==before)throw Error('pointer insert undo failed');
// Keyboard-only selection and activation of a drop position.
await evaluate(`document.querySelector('.native-element-grid button:nth-child(3)').focus()`);await send('Input.dispatchKeyEvent',{type:'keyDown',text:'\r',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await sleep(80);
await evaluate(`document.querySelector('.native-drop-options summary').focus()`);await send('Input.dispatchKeyEvent',{type:'keyDown',text:'\r',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await send('Input.dispatchKeyEvent',{type:'keyDown',text:'\r',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});await sleep(100);
if(await evaluate(`document.querySelectorAll('.native-node').length`)!==before+1)throw Error('keyboard insertion failed');
await click('Undo');
const moving=tree.children[0].children[0].children.find(n=>n.type==='heading').id,targetCol=tree.children[0].children[1].id;
await dragTo('#'+moving,'#'+targetCol);
if(!(await evaluate(`document.querySelector('#${targetCol} #${moving}')!==null`)))throw Error('cross-container pointer move failed');
await click('Undo');if(!(await evaluate(`document.querySelector('#${col} #${moving}')!==null`)))throw Error('cross-container undo failed');
await dragTo('#'+moving,'#'+tree.children[0].children[0].children[0].id);if(!(await evaluate(`document.querySelector('#${col} .mz-column').firstElementChild.id===${JSON.stringify(moving)}`)))throw Error('same-container reorder failed');await click('Undo');
// Escape cancels an active pointer move without adding a node.
const cancelStart=await rect('.native-element-grid button:nth-child(3)');await send('Input.dispatchMouseEvent',{type:'mousePressed',x:cancelStart.x+10,y:cancelStart.y+10,button:'left',clickCount:1});await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:cancelStart.x+10,y:cancelStart.y+10,button:'left',clickCount:1});if(await evaluate(`document.querySelectorAll('.native-node').length`)!==before)throw Error('cancel changed tree');

// Touch uses the same pointer flow, with CDP touch events rather than mouse emulation.
await send('Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:1});
const a=await rect('.native-element-grid button:nth-child(4)');await send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:a.x+a.width/2,y:a.y+a.height/2,id:1}]});
const b=await rect('#'+col);await send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:b.x+30,y:b.y+30,id:1}]});await sleep(120);
if(!(await evaluate(`!!document.querySelector('.native-drop-marker')`)))throw Error('touch drop position absent');
await send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await sleep(120);
if(await evaluate(`document.querySelectorAll('.native-node').length`)!==before+1)throw Error('touch insertion failed');
// Touch move uses explicit handle so normal preview swipes stay available.
await selectType('heading');const h=await rect('.native-palette button:first-child');await send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:h.x+h.width/2,y:h.y+h.height/2,id:2}]});const t=await rect('#'+targetCol);await send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:t.x+20,y:t.y+2,id:2}]});await sleep(80);await send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await sleep(100);if(!(await evaluate(`document.querySelector('#${targetCol} #${moving}')!==null`)))throw Error('touch handle move failed');await click('Undo');
await evaluate(`document.querySelector('.studio-canvas').scrollTop=0`);await shot('/downloads/native-drag-result.png');

await click('Save');await waitFor(`document.querySelector('.studio-notice').textContent.startsWith('Native tree draft saved')`);await send('Page.reload');await sleep(300);await waitFor(`!!document.querySelector('.native-node')`);if(await evaluate(`document.querySelectorAll('.native-node').length`)!==before+1)throw Error('drag save/reload failed');
console.log('PASS MOCKED pointer palette insertion/cross-container move, visible position, undo, keyboard insertion and emulated touch insertion');ws.close();
