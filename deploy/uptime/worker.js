// Mizan uptime (ADR-011): a Cloudflare Worker that checks production from outside the server every
// 5 minutes and emails the owner when something goes down, every hour while it stays down, and
// when it recovers. It also serves the latest result at https://status.allmizan.live.
//
// Bindings (deploy/uptime/deploy.sh): STATE (KV namespace), BREVO_API_KEY (secret), RUN_KEY (secret,
// for /run), ALERT_TO (the address alerts go to).
import { connect } from "cloudflare:sockets";

const PAGES = ["https://allmizan.live/", "https://owner.allmizan.live/", "https://admin.allmizan.live/",
               "https://dev.allmizan.live/", "https://mail.allmizan.live/"];
const APIS = ["https://api.allmizan.live/api/health", "https://owner-api.allmizan.live/api/health",
              "https://admin-api.allmizan.live/api/health", "https://web-api.allmizan.live/api/health"];
const PORTS = [["mail.allmizan.live", 587], ["mail.allmizan.live", 993]];  // Workers can't open port 25
const REMIND_EVERY_MIN = 60;

async function withTimeout(promise, ms) {
  let t;
  try {
    return await Promise.race([promise, new Promise((_, no) => { t = setTimeout(() => no(new Error("timeout")), ms); })]);
  } finally {
    clearTimeout(t);
  }
}

async function checkPage(url) {
  const r = await withTimeout(fetch(url, { redirect: "manual", headers: { "user-agent": "mizan-uptime" } }), 15000);
  if (r.status !== 200) throw new Error(`HTTP ${r.status}`);
}

async function checkApi(url) {
  const r = await withTimeout(fetch(url, { headers: { "user-agent": "mizan-uptime" } }), 15000);
  const body = await r.text();
  if (r.status !== 200) throw new Error(`HTTP ${r.status}`);
  if (!body.includes('"status":"ok"')) throw new Error("degraded (database?)");  // 200 even when the DB is down
}

async function checkPort([host, port]) {
  const socket = connect({ hostname: host, port }, { secureTransport: "off" });
  try {
    await withTimeout(socket.opened, 10000);
  } finally {
    socket.close();
  }
}

/** Two tries, 5 s apart: a blip isn't an outage. */
async function probe(label, fn) {
  let last;
  for (let i = 0; i < 2; i++) {
    try {
      await fn();
      return null;
    } catch (e) {
      last = e;
      if (i === 0) await new Promise((r) => setTimeout(r, 5000));
    }
  }
  return `${label} (${last && last.message})`;
}

async function runChecks(simulateDown = false) {
  const results = await Promise.all([
    ...(simulateDown ? [probe("simulated outage (test)", async () => { throw new Error("test"); })] : []),
    ...PAGES.map((u) => probe(u, () => checkPage(u))),
    ...APIS.map((u) => probe(u, () => checkApi(u))),
    ...PORTS.map((p) => probe(`${p[0]}:${p[1]}`, () => checkPort(p))),
  ]);
  return results.filter(Boolean);
}

async function email(env, subject, lines) {
  const res = await fetch("https://api.brevo.com/v3/smtp/email", {
    method: "POST",
    headers: { "api-key": env.BREVO_API_KEY, "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify({
      sender: { name: "Mizan uptime", email: "no-reply@allmizan.live" },
      to: [{ email: env.ALERT_TO }],
      subject,
      textContent: lines.join("\n") + "\n\nhttps://status.allmizan.live",
    }),
  });
  if (!res.ok) console.log("alert email failed", res.status, await res.text());
}

async function tick(env, simulateDown = false) {
  const now = Date.now();
  const down = await runChecks(simulateDown);
  const prev = JSON.parse((await env.STATE.get("state")) || '{"down":[],"since":null,"reminded":null}');
  const state = { down, since: prev.since, reminded: prev.reminded, checked: now };
  const when = new Date(now).toISOString().replace("T", " ").slice(0, 16) + " UTC";

  if (down.length && !prev.down.length) {
    state.since = now;
    state.reminded = now;
    await email(env, `Mizan DOWN: ${down.length} check(s) failing`, [`Down since ${when}:`, ...down.map((d) => `- ${d}`)]);
  } else if (down.length) {
    if (now - (prev.reminded || 0) >= REMIND_EVERY_MIN * 60000 || down.join() !== prev.down.join()) {
      state.reminded = now;
      const mins = Math.round((now - prev.since) / 60000);
      await email(env, `Mizan still down (${mins} min)`, [`Still failing at ${when}:`, ...down.map((d) => `- ${d}`)]);
    }
  } else if (prev.down.length) {
    const mins = Math.round((now - prev.since) / 60000);
    state.since = null;
    state.reminded = null;
    await email(env, `Mizan recovered after ${mins} min`, [`Everything answers again at ${when}.`, "", "Was failing:", ...prev.down.map((d) => `- ${d}`)]);
  }
  await env.STATE.put("state", JSON.stringify(state));
  return state;
}

function page(state) {
  const ok = state && !state.down.length;
  const checked = state && state.checked ? new Date(state.checked).toISOString().replace("T", " ").slice(0, 16) + " UTC" : "not yet";
  const items = state && state.down.length ? `<ul>${state.down.map((d) => `<li>${d.replace(/</g, "&lt;")}</li>`).join("")}</ul>` : "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mizan status</title><meta http-equiv="refresh" content="60"><style>
body{margin:0;font:15px/1.6 system-ui,sans-serif;background:#f6f3f0;color:#1d1b1a;display:grid;place-items:center;min-height:100vh}
main{background:#fff;border:1px solid #e9e3de;border-radius:16px;padding:28px 32px;max-width:480px;width:90%}
h1{margin:0 0 6px;font-size:20px}.dot{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:8px;background:${ok ? "#2f7d4f" : "#b3261e"}}
p{color:#6f6964;margin:4px 0}</style></head><body><main>
<h1><span class="dot"></span>${ok ? "All systems working" : "Some services are down"}</h1>
<p>Mizan: apps, APIs, database and mail. Checked every 5 minutes from outside.</p>${items}<p>Last check: ${checked}</p>
</main></body></html>`;
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(tick(env));
  },
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/run") {  // a manual check: /run?key=<RUN_KEY>[&simulate=down to test the alerts]
      if (url.searchParams.get("key") !== env.RUN_KEY) return new Response("forbidden", { status: 403 });
      return Response.json(await tick(env, url.searchParams.get("simulate") === "down"));
    }
    if (url.pathname === "/status.json") {
      return Response.json(JSON.parse((await env.STATE.get("state")) || "null"), { headers: { "cache-control": "no-store" } });
    }
    const state = JSON.parse((await env.STATE.get("state")) || "null");
    return new Response(page(state), { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
  },
};
