#!/usr/bin/env node
// Fail-closed check: the deployed studio app must be a HOSTED build
// (VITE_STUDIO_API=/api), not the local-prototype build.
//
// Background: vite statically replaces import.meta.env.VITE_STUDIO_API at
// build time. In a hosted build the bundle contains the API base assignment
//   ="/api",<mangled>=<mangled>!=="/__studio/api"
// In a local-prototype build the same site reads
//   ="/__studio/api",<mangled>=<mangled>!=="/__studio/api"
// A local-prototype build on the deployment silently disables backend
// save/load in the editor ("Local prototype" mode), which once caused a
// wrong-mode deploy. This script refuses to let that ship again.
//
// usage: check-studio-hosted-build.mjs <studio-build-dir>
//        check-studio-hosted-build.mjs --self-test
import { readdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import { join } from 'node:path';

const HOSTED_MARKER = /="\/api",[\w$]+=[\w$]+!=="\/__studio\/api"/;
const LOCAL_MARKER = /="\/__studio\/api",[\w$]+=[\w$]+!=="\/__studio\/api"/;

export function scanJs(source) {
  if (HOSTED_MARKER.test(source)) return 'hosted';
  if (LOCAL_MARKER.test(source)) return 'local';
  return 'unknown';
}

function* jsFiles(dir) {
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) yield* jsFiles(p);
    else if (entry.endsWith('.js')) yield p;
  }
}

function selfTest() {
  const cases = [
    ['hosted snippet', 'x=function(){}const Sd="/api",mc=Sd!=="/__studio/api",y=1', 'hosted'],
    ['local snippet', 'const Sd="/__studio/api",mc=Sd!=="/__studio/api",y=1', 'local'],
    ['unrelated bundle', 'function f(){return "/api health endpoint"}', 'unknown'],
  ];
  let failed = 0;
  for (const [name, src, want] of cases) {
    const got = scanJs(src);
    const ok = got === want;
    if (!ok) failed++;
    console.log(`${ok ? 'ok' : 'FAIL'}: ${name} -> ${got} (want ${want})`);
  }
  if (scanJs('="/api",a=a!=="/__studio/api"') !== 'hosted') { console.log('FAIL: minified hosted form'); failed++; }
  process.exit(failed ? 1 : 0);
}

if (process.argv[2] === '--self-test') selfTest();

const dir = process.argv[2];
if (!dir) { console.error('usage: check-studio-hosted-build.mjs <studio-build-dir>'); process.exit(2); }
if (!existsSync(dir)) { console.error(`DEPLOY BLOCKED: studio build dir missing: ${dir}`); process.exit(1); }

let hosted = 0, local = 0, files = 0;
for (const f of jsFiles(dir)) {
  files++;
  const verdict = scanJs(readFileSync(f, 'utf8'));
  if (verdict === 'hosted') hosted++;
  if (verdict === 'local') local++;
}

if (local > 0 || hosted === 0) {
  console.error(`DEPLOY BLOCKED: studio build is not a hosted build (hosted markers: ${hosted}, local-prototype markers: ${local}, js files: ${files}).`);
  console.error('Rebuild the studio with VITE_STUDIO_API=/api (and VITE_STUDIO_BASE=/studio/) or the deployed editor will fall back to local-prototype mode with no backend saves.');
  process.exit(1);
}
console.log(`ok: hosted studio build verified (${hosted} marker file(s), ${files} js files scanned)`);
