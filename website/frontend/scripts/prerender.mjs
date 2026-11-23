// Writes every public page of the website as static HTML (ADR-016), after `vite build` (the
// browser bundle in dist/) and `vite build --ssr src/entry-server.tsx` (the renderer in dist-ssr/).
//
//   dist/index.html, dist/<path>/index.html   each page, fully rendered, with its own head
//   dist/404.html, dist/en/404.html            "page not found" (nginx answers with status 404)
//   dist/spa.html                              the empty shell for application pages (signup…)
//   dist/dev.html                              the shell for dev.allmizan.live
//   dist/robots.txt, dist/robots-dev.txt
//   dist/sitemap.xml + dist/sitemaps/{pages,blog,docs}.xml
//
// lastmod: a page's date changes only when its rendered content changes. The dates live in
// src/seo/lastmod.json; `node scripts/prerender.mjs --update-lastmod` (or SEO_UPDATE_LASTMOD=1)
// records today's date for changed pages, so commit the file after changing content. A build
// without the flag gives changed pages today's date without writing the file.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import Beasties from "beasties";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DIST = join(ROOT, "dist");
const LASTMOD_FILE = join(ROOT, "src", "seo", "lastmod.json");
const UPDATE_LASTMOD = process.argv.includes("--update-lastmod") || process.env.SEO_UPDATE_LASTMOD === "1";
const TODAY = new Date().toISOString().slice(0, 10);

// The renderer imports browser-minded modules (stores read localStorage when loaded): an empty
// storage gives the state of a first visit, which is what the HTML must show.
const memoryStorage = () => {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => void m.set(k, String(v)),
    removeItem: (k) => void m.delete(k),
    clear: () => m.clear(),
    key: (i) => [...m.keys()][i] ?? null,
    get length() {
      return m.size;
    },
  };
};
globalThis.localStorage = memoryStorage();
globalThis.sessionStorage = memoryStorage();

const ssr = await import(pathToFileURL(join(ROOT, "dist-ssr", "entry-server.js")).href);
const { render, renderHead, prerenderPages, notFoundPages, robotsTxt, SITE_URL } = ssr;

// dist/index.html becomes the home page; the built template is kept aside so the script can run again.
const TEMPLATE = join(DIST, ".vite", "index.template.html");
if (!existsSync(TEMPLATE)) writeFileSync(TEMPLATE, readFileSync(join(DIST, "index.html")));
const template = readFileSync(TEMPLATE, "utf8");
const manifest = JSON.parse(readFileSync(join(DIST, ".vite", "manifest.json"), "utf8"));
const assets = readdirSync(join(DIST, "assets"));

const SEO_BLOCK = /<!-- seo:start[\s\S]*?<!-- seo:end -->/;
if (!SEO_BLOCK.test(template) || !template.includes('<div id="root"></div>')) {
  throw new Error("dist/index.html lacks the seo markers or the empty root: was it built from index.html?");
}

/** The chunks a page's component needs, besides what the entry already loads. */
const entryKey = Object.keys(manifest).find((k) => manifest[k].isEntry);
const entryFiles = new Set(collect(entryKey));
function collect(key, seen = new Set()) {
  const chunk = manifest[key];
  if (!chunk || seen.has(key)) return [];
  seen.add(key);
  return [chunk.file, ...(chunk.imports ?? []).flatMap((k) => collect(k, seen))];
}
function preloads(module) {
  if (!manifest[module]) throw new Error(`${module} isn't a chunk in the manifest: is it lazy-loaded in App.tsx?`);
  return [...new Set(collect(module))].filter((f) => !entryFiles.has(f));
}

/** The one font the first paint needs (the body text); the rest load as the page uses them. */
const FONT = {
  ar: "ibm-plex-sans-arabic-400-arabic",
  en: "manrope-400-700-latin",
};
function fontHref(lang) {
  const file = assets.find((a) => a.startsWith(`${FONT[lang]}-`) && a.endsWith(".woff2"));
  if (!file) throw new Error(`font ${FONT[lang]} not found in dist/assets`);
  return `/assets/${file}`;
}

const ENTRY_TAG = /<script type="module" crossorigin src="(\/assets\/index-[^"]+\.js)"><\/script>\s*/;
const MODULEPRELOAD = /<link rel="modulepreload" crossorigin href="[^"]+">\s*/g;

/**
 * A pre-rendered page is complete without JavaScript, so its code doesn't compete with the first
 * paint: the app (and the page's own chunk) load once the page has loaded, then React takes over.
 */
function deferredApp(html, chunks) {
  const entry = html.match(ENTRY_TAG)?.[1];
  if (!entry) throw new Error("no entry script in the template");
  const load = [entry, ...chunks.map((c) => `/${c}`)].map((u) => `import(${JSON.stringify(u)})`).join(";");
  const loader = `<script type="module">const go=()=>{${load}};document.readyState==="complete"?go():addEventListener("load",go,{once:true});</script>`;
  return html.replace(ENTRY_TAG, "").replace(MODULEPRELOAD, "").replace("</body>", `  ${loader}\n  </body>`);
}

function page(html, { lang, head, body, preload = [], prerendered = true }) {
  const dir = lang === "ar" ? "rtl" : "ltr";
  const links = `<link rel="preload" href="${fontHref(lang)}" as="font" type="font/woff2" crossorigin />`;
  if (prerendered) html = deferredApp(html, preload.slice(0, 1));
  return html
    .replace(/<html[^>]*>/, `<html lang="${lang}" dir="${dir}"${prerendered ? ' data-locale="url"' : ""}>`)
    .replace(SEO_BLOCK, `${head}\n    ${links}`)
    .replace('<div id="root"></div>', prerendered ? `<div id="root" data-prerendered="1">${body}</div>` : '<div id="root"></div>');
}

// The CSS rules a page's HTML uses go inline, so the first paint doesn't wait for the stylesheet;
// the whole stylesheet still loads (without blocking) for the pages visitors open next.
const beasties = new Beasties({
  path: DIST,
  publicPath: "/",
  preload: "swap",
  inlineFonts: true,
  preloadFonts: false,
  pruneSource: false,
  reduceInlineStyles: false,
  compress: true,
  logLevel: "warn",
});

function write(rel, content) {
  const file = join(DIST, rel);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, content);
}

const fileFor = (path) => (path === "/" ? "index.html" : `${path.slice(1)}/index.html`);

// The shells first: dist/index.html is about to become the home page.
const esc = (s) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
write(
  "spa.html",
  page(template, {
    lang: "ar",
    prerendered: false,
    head: `<title>ميزان ERP</title>\n    <meta name="robots" content="noindex, follow" />`,
  }),
);
write(
  "dev.html",
  page(template, {
    lang: "en",
    prerendered: false,
    head: `<title>Mizan Developers</title>\n    <meta name="description" content="${esc(
      "Build activities, modules and themes for Mizan: the developer portal, the docs and the mizan CLI.",
    )}" />`,
  }),
);

const lastmod = existsSync(LASTMOD_FILE) ? JSON.parse(readFileSync(LASTMOD_FILE, "utf8")) : {};
const nextLastmod = {};
const pages = prerenderPages();
const seen = new Set();
for (const p of pages) {
  if (seen.has(p.path)) throw new Error(`two pages at ${p.path}`);
  seen.add(p.path);
  const body = await render(p.path);
  if (!body.includes("<h1")) throw new Error(`${p.path}: rendered without an <h1> (did a lazy page fail?)`);
  write(fileFor(p.path), await beasties.process(page(template, { lang: p.lang, head: renderHead(p), body, preload: preloads(p.module) })));
  const hash = createHash("sha256").update(body).digest("hex").slice(0, 16);
  const known = lastmod[p.path];
  nextLastmod[p.path] = known && known.hash === hash ? known : { hash, date: TODAY };
}

for (const nf of notFoundPages()) {
  const body = await render(nf.render);
  write(nf.file, await beasties.process(page(template, { lang: nf.lang, head: renderHead(nf), body, preload: preloads(nf.module) })));
}

write("robots.txt", robotsTxt("site"));
write("robots-dev.txt", robotsTxt("dev"));

// Sitemaps: only canonical, indexable pages, with their language versions.
const xmlEsc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const groups = { pages: [], blog: [], docs: [] };
for (const p of pages) if (p.index && p.sitemap) groups[p.sitemap].push(p);
const dateOf = (p) => {
  const dates = [nextLastmod[p.path].date, p.modified].filter(Boolean).sort();
  // The content's own date when it's later than our record (an edited article), else the record.
  return dates[dates.length - 1];
};
rmSync(join(DIST, "sitemaps"), { recursive: true, force: true });
const index = [];
for (const [name, list] of Object.entries(groups)) {
  if (!list.length) continue;
  const urls = list.map((p) => {
    const alts = Object.entries(p.alternates);
    const links =
      alts.length > 1
        ? [...alts, ["x-default", p.alternates.ar]]
            .map(([l, path]) => `\n    <xhtml:link rel="alternate" hreflang="${l}" href="${xmlEsc(SITE_URL + path)}"/>`)
            .join("")
        : "";
    return `  <url>\n    <loc>${xmlEsc(SITE_URL + p.path)}</loc>\n    <lastmod>${dateOf(p)}</lastmod>${links}\n  </url>`;
  });
  write(
    `sitemaps/${name}.xml`,
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n${urls.join("\n")}\n</urlset>\n`,
  );
  const latest = list.map(dateOf).sort().at(-1);
  index.push(`  <sitemap>\n    <loc>${SITE_URL}/sitemaps/${name}.xml</loc>\n    <lastmod>${latest}</lastmod>\n  </sitemap>`);
}
write(
  "sitemap.xml",
  `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${index.join("\n")}\n</sitemapindex>\n`,
);

const changed = Object.keys(nextLastmod).filter((k) => lastmod[k]?.hash !== nextLastmod[k].hash);
if (UPDATE_LASTMOD) {
  const sorted = Object.fromEntries(Object.keys(nextLastmod).sort().map((k) => [k, nextLastmod[k]]));
  writeFileSync(LASTMOD_FILE, JSON.stringify(sorted, null, 2) + "\n");
} else if (changed.length) {
  console.warn(`prerender: ${changed.length} page(s) changed since src/seo/lastmod.json (dated today): ${changed.slice(0, 5).join(", ")}${changed.length > 5 ? "…" : ""}`);
}
rmSync(join(ROOT, "dist-ssr"), { recursive: true, force: true });
// The build's manifest and template aren't for visitors.
rmSync(join(DIST, ".vite"), { recursive: true, force: true });
console.log(`prerender: ${pages.length} pages, ${notFoundPages().length} not-found pages, sitemaps: ${Object.entries(groups).map(([k, v]) => `${k} ${v.length}`).join(", ")}`);
