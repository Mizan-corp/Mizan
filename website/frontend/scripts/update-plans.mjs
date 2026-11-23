// Refreshes the plans snapshot the structured data (SoftwareApplication offers) and the pricing
// page's head are built from: the live plans API, the same list the signup and the owner panel use.
//   node scripts/update-plans.mjs [https://web-api.allmizan.live/api]
import { writeFileSync } from "node:fs";

const api = (process.argv[2] || "https://web-api.allmizan.live/api").replace(/\/+$/, "");
const res = await fetch(`${api}/platform/plans`);
if (!res.ok) throw new Error(`${api}/platform/plans: ${res.status}`);
const body = await res.json();
const plans = body.plans.map(({ id, name, price_egp, popular }) => ({ id, name, price_egp, ...(popular ? { popular } : {}) }));
const snapshot = { source: `${api}/platform/plans`, fetched: new Date().toISOString().slice(0, 10), trial_days: body.trial_days, plans };
writeFileSync(new URL("../src/seo/plans.snapshot.json", import.meta.url), JSON.stringify(snapshot, null, 2) + "\n");
console.log(`plans snapshot: ${plans.map((p) => `${p.id} ${p.price_egp} EGP`).join(", ")}`);
