// Migration step 2: the ERP route table must not change when routes move from App.tsx into
// module index.ts files. routeTable.baseline.json is the table as it was before the move
// (path, route guard permission, required module). Moving a route is fine; changing or losing
// one fails here.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import baseline from "./routeTable.baseline.json";
import { moduleDefinitions } from "./registry";

interface Row { path: string; perm: string | null; module: string | null }

const app = readFileSync(join(__dirname, "../App.tsx"), "utf8");
const fromApp: Row[] = [...app.matchAll(/<Route path="([^"]*)" element=\{(.*?)\} \/>/g)].map((m) => {
  const g = m[2].match(/<Guard perm="([^"]*)"(?: module="([^"]*)")?>/);
  return { path: m[1], perm: g ? g[1] : null, module: g?.[2] ?? null };
});
const fromModules: Row[] = moduleDefinitions.flatMap((m) => m.routes ?? []).map((r) => ({ path: r.path, perm: r.perm, module: r.module ?? null }));
const byPath = (a: Row, b: Row) => a.path.localeCompare(b.path);
const expected = (baseline as Row[]).map(({ path, perm, module }) => ({ path, perm, module })).sort(byPath);

describe("ERP route table", () => {
  it("is the same table after routes moved into modules", () => {
    expect([...fromApp, ...fromModules].sort(byPath)).toEqual(expected);
  });

  it("has no path declared twice", () => {
    // Top-level shell routes ("/login", "*" ...) legitimately repeat across the host variants.
    const paths = [...fromApp, ...fromModules].map((r) => r.path).filter((p) => !p.startsWith("/") && p !== "*");
    expect(paths.length).toBe(new Set(paths).size);
  });

  it("moved at least the pilot modules' routes into their index.ts", () => {
    const ids = moduleDefinitions.filter((m) => (m.routes ?? []).length > 0).map((m) => m.id).sort();
    expect(ids).toEqual(expect.arrayContaining(["accounting", "website"]));
  });
});
