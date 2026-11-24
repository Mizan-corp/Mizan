// Prune stale hashed assets from a built static/ tree before deploy.
// Keeps every asset referenced by any HTML entry (directly, or transitively
// through JS dynamic imports and CSS url() refs); deletes the rest so old
// bundles (and any debug residue in them) stop being served.
// Usage: node scripts/prune-static-assets.mjs <static-dir>
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] ?? '');
if (!root || !fs.existsSync(root)) { console.error('usage: node prune-static-assets.mjs <static-dir>'); process.exit(2); }

const walk = (dir, out = []) => {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out); else out.push(p);
  }
  return out;
};

const keep = new Set();
const resolveRef = (ref, fromFile) => {
  if (!ref || ref.startsWith('data:') || ref.startsWith('http')) return null;
  const clean = ref.split(/[?#]/)[0];
  if (!/\.(js|css|woff2?|png|jpe?g|svg|webp|json|webmanifest)$/.test(clean)) return null;
  if (clean.startsWith('/')) {
    const abs = path.join(root, clean);
    return fs.existsSync(abs) ? abs : null;
  }
  // Relative refs can be resolved by the runtime against any ancestor base
  // (entry dir, section dir, or site root) — try each before giving up.
  for (let d = path.dirname(fromFile); ; d = path.dirname(d)) {
    const abs = path.resolve(d, clean);
    if (abs.startsWith(root) && fs.existsSync(abs)) return abs;
    if (d === root || d === path.dirname(d)) break;
  }
  return null;
};

const htmlFiles = walk(root).filter(f => f.endsWith('.html'));
for (const html of htmlFiles) {
  const text = fs.readFileSync(html, 'utf8');
  for (const m of text.matchAll(/(?:src|href)="([^"]+)"/g)) {
    const abs = resolveRef(m[1], html);
    if (abs) keep.add(abs);
  }
}

// Transitive: JS import()/import refs and CSS url() refs inside kept files.
const queue = [...keep];
while (queue.length) {
  const file = queue.pop();
  if (!/\.(js|css)$/.test(file)) continue;
  const text = fs.readFileSync(file, 'utf8');
  const refs = new Set();
  for (const m of text.matchAll(/["'(]([^"')]+\.(?:js|css|woff2?|png|jpe?g|svg|webp))["')]/g)) refs.add(m[1]);
  for (const ref of refs) {
    const abs = resolveRef(ref, file);
    if (abs && !keep.has(abs)) { keep.add(abs); queue.push(abs); }
  }
}

const assetDirs = walk(root).filter(f => /assets[/\\]/.test(f));
let removed = 0;
for (const file of assetDirs) {
  if (!keep.has(file)) { fs.rmSync(file); removed++; console.log('pruned', path.relative(root, file)); }
}
console.log(`prune OK: ${removed} stale asset(s) removed, ${keep.size} kept`);
