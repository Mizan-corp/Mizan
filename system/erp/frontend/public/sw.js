/* Mizan service worker: the app shell works offline; data never comes from the cache.
   Served from the app's base (registered in main.tsx), so its scope covers /c/<slug>/ (#115).
   - API calls, other origins (uploaded files on Vercel Blob) and non-GET requests: untouched.
   - Pages: network first; offline, the last app shell (one copy: every page is the same SPA).
   - Hashed build files (assets/…): cache first (a new build has new names).
   - Anything else (icon, manifest): network first, cache as fallback, so it never goes stale.
   Bump CACHE when this file's behaviour changes. */
const CACHE = "mizan-shell-v4";
const BASE = new URL("./", self.location).pathname;
const SHELL_KEY = BASE + "index.html";

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll([SHELL_KEY, BASE + "manifest.webmanifest", BASE + "icon.svg"]).catch(() => {}))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

const OFFLINE = `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"/><title>ميزان — وضع عدم الاتصال</title><meta name="viewport" content="width=device-width,initial-scale=1"/></head><body style="font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#35151D;color:#F5EBDD;text-align:center;"><div style="padding:24px;border:1px solid rgba(255,255,255,0.1);border-radius:16px;background:rgba(255,255,255,0.05);"><h1 style="margin:0 0 8px;">ميزان</h1><p style="opacity:0.8;">تعذر تحميل الصفحة — تحقق من اتصال الإنترنت.</p><button onclick="location.reload()" style="margin-top:16px;padding:8px 18px;border-radius:8px;border:none;background:#651E2C;color:#fff;cursor:pointer;font-weight:bold;">إعادة المحاولة</button></div></body></html>`;

function put(key, res) {
  if (res && res.ok && res.type === "basic") {
    const copy = res.clone();
    caches.open(CACHE).then((c) => c.put(key, copy)).catch(() => {});
  }
  return res;
}

self.addEventListener("fetch", (e) => {
  let url;
  try {
    url = new URL(e.request.url);
  } catch {
    return;
  }
  if (e.request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith(BASE + "api/") ||
      url.pathname.startsWith("/api/") || url.pathname.startsWith("/uploads/")) {
    return;
  }

  if (e.request.mode === "navigate") {
    e.respondWith(
      fetch(e.request)
        .then((res) => put(SHELL_KEY, res))
        .catch(async () => (await caches.match(SHELL_KEY)) ||
          new Response(OFFLINE, { headers: { "Content-Type": "text/html; charset=utf-8" } })),
    );
    return;
  }

  if (url.pathname.startsWith(BASE + "assets/")) {
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => put(e.request, res))),
    );
    return;
  }

  e.respondWith(
    fetch(e.request)
      .then((res) => put(e.request, res))
      .catch(async () => (await caches.match(e.request)) || new Response("", { status: 504 })),
  );
});
