import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
// Local-only preview bridge. Never part of the production service or ERP routes.
// Local-only backend bridge. Never part of the production service or ERP routes.
// Forwards to a developer-specified LOOPBACK API only (MIZAN_SITE_API, e.g. a locally
// booted test backend) with a developer-supplied token (MIZAN_SITE_TOKEN). With either
// unset the bridge answers 503 and the studio stays in local-only mode - it fails
// closed rather than implying a server save happened. The vite server itself binds
// 127.0.0.1 and the bridge rejects non-same-origin callers, so nothing is exposed.
const apiTarget = process.env.MIZAN_SITE_API || '';
const apiToken = process.env.MIZAN_SITE_TOKEN || '';
const apiOk = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(apiTarget) && apiToken.length > 0;
export default defineConfig({ base: process.env.VITE_STUDIO_BASE || '/', plugins: [react(), { name:'experimental-python-preview', configureServer(server) {
 server.middlewares.use('/__studio/api', (req,res) => {
  if(req.headers.host!=='127.0.0.1:5188' || (req.headers.origin && req.headers.origin!=='http://127.0.0.1:5188')) {res.statusCode=403;res.end('Local POST only');return;}
  res.setHeader('Cache-Control','no-store');
  if(!apiOk) {res.statusCode=503;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({detail:'Local backend not configured'}));return;}
  // Raw passthrough: bytes and Content-Type go through untouched, so JSON saves and
  // multipart media uploads both work, and binary media responses keep their type.
  const chunks:Buffer[]=[];let size=0;req.on('data',chunk=>{chunks.push(chunk);size+=chunk.length;if(size>8*1024*1024){res.statusCode=413;res.end('Request too large');req.destroy();}});
  req.on('end',async()=>{if(res.writableEnded)return;
   try{
    const method=req.method||'GET';
    const headers:Record<string,string>={Authorization:`Bearer ${apiToken}`};
    if(req.headers['content-type'])headers['Content-Type']=req.headers['content-type'];
    const response=await fetch(apiTarget+(req.url||'/'),{method,headers,body:['GET','HEAD'].includes(method)?undefined:Buffer.concat(chunks)});
    res.statusCode=response.status;
    const ct=response.headers.get('content-type');if(ct)res.setHeader('Content-Type',ct);
    res.end(Buffer.from(await response.arrayBuffer()));
   }catch{res.statusCode=502;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({detail:'Local backend unreachable'}));}
  });
 });
 // Uploaded images (/uploads/...) live on the backend origin; the local studio canvas
 // shows them through this loopback-only proxy, mirroring hosted same-origin serving.
 server.middlewares.use('/uploads', (req,res) => {
  if(req.headers.host!=='127.0.0.1:5188') {res.statusCode=403;res.end('Local only');return;}
  if(!apiOk) {res.statusCode=404;res.end('Not found');return;}
  // connect strips the mount prefix; the backend serves files under /uploads itself.
  fetch(apiTarget+'/uploads'+(req.url||'/'),{headers:{Authorization:`Bearer ${apiToken}`}}).then(async response=>{
   res.statusCode=response.status;const ct=response.headers.get('content-type');if(ct)res.setHeader('Content-Type',ct);
   res.setHeader('Cache-Control','no-store');res.end(Buffer.from(await response.arrayBuffer()));
  }).catch(()=>{res.statusCode=502;res.end('Local backend unreachable')});
 });
 server.middlewares.use('/__studio/preview', (req,res) => {
  if(req.headers.host!=='127.0.0.1:5188' || req.method!=='POST' || (req.headers.origin && req.headers.origin!=='http://127.0.0.1:5188')) {res.statusCode=403;res.end('Local POST only');return;}
  let body='';req.on('data',chunk=>{body+=chunk;if(Buffer.byteLength(body)>200000){res.statusCode=413;res.end('Preview too large');req.destroy();}});
  req.on('end',()=>{if(res.writableEnded)return;const child=spawn('python3',[fileURLToPath(new URL('./studio-preview.py',import.meta.url))],{env:process.env});let output='';let error='';const timer=setTimeout(()=>child.kill(),5000);child.stdout.on('data',c=>{output+=c;});child.stderr.on('data',c=>{error+=c;});child.on('error',()=>{clearTimeout(timer);res.statusCode=503;res.end('Python preview could not start');});child.on('close',code=>{clearTimeout(timer);if(res.writableEnded)return;res.statusCode=code===0?200:422;res.setHeader('Content-Type',code===0?'text/html; charset=utf-8':'text/plain');res.setHeader('Cache-Control','no-store');res.end(code===0?output:'Shared renderer rejected preview. Check local server log.');if(code!==0)console.error(error);});child.stdin.end(body);});
 });
} }], build: { rollupOptions: { input: fileURLToPath(new URL('./studio.html', import.meta.url)) } }, server: { host: '127.0.0.1', port: 5188, strictPort: true } });
