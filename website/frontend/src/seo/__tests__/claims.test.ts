/** Claims the product doesn't support must not come back (the PR's "Truthfulness fixes"). */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("marketing claims", () => {
  const roots = [join(__dirname, "../../features"), join(__dirname, "../../../../../system/core/frontend/src/lib/plans.ts")];
  const files: string[] = [];
  const collect = (p: string) => {
    if (statSync(p).isDirectory()) readdirSync(p).forEach((f) => collect(join(p, f)));
    else if (/\.(ts|tsx)$/.test(p) && !p.includes("__tests__") && !p.includes("/developers/")) files.push(p);
  };
  roots.forEach(collect);
  const banned = [/ZATCA/, /متوافق[ةه]? مع (منظومة )?ETA/, /ETA[- ]?(tax-)?compliant/i, /e-Invoice compliance/i,
    /99\.9/, /1,500\+|\+1,500/, /Neon/, /24\/7/, /مدار الساعة/, /sub-?(10ms|2s|second)/i];
  it("doesn't claim ETA/ZATCA compliance, uptime, customer counts or other unsupported features", () => {
    for (const f of files) {
      const text = readFileSync(f, "utf8");
      for (const b of banned) expect(b.test(text), `${f}: ${b}`).toBe(false);
    }
  });
});
