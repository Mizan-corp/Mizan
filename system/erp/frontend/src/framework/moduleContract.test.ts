// Contract between the backend module manifests and the ERP frontend (docs/modular-core-exploration.md,
// migration step 1). Pure checks over files: no behaviour change.
//  1. every screen an active manifest declares has a route (App.tsx or its module);
//  2. every active module has a frontend index.ts (ModuleDefinition) in the expected folder.
import { describe, expect, it } from "vitest";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { moduleDefinitions } from "./registry";

const ROOT = resolve(__dirname, "../../../../..");
const BACKEND = join(ROOT, "system/core/backend/app");
const FRONTEND = join(ROOT, "system/erp/frontend/src");

interface Manifest { id: string; kind?: string; activity?: string; status?: string; screens?: { id: string; path: string }[] }

function manifests(dir: string, out: Manifest[] = []): Manifest[] {
  for (const name of readdirSync(dir)) {
    if (name === "__pycache__" || name === "module_template" || name === "node_modules") continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) manifests(p, out);
    else if (name === "manifest.json") out.push(JSON.parse(readFileSync(p, "utf8")) as Manifest);
  }
  return out;
}

const active = manifests(BACKEND).filter((m) => m.status === "active" && m.id);
const appSource = readFileSync(join(FRONTEND, "App.tsx"), "utf8");
// Routes live in App.tsx or, since migration step 2, in a module's index.ts (ModuleDefinition.routes).
const routes = new Set([
  ...[...appSource.matchAll(/path="([^"]*)"/g)].map((m) => m[1]),
  ...moduleDefinitions.flatMap((m) => m.routes ?? []).map((r) => r.path),
]);

function indexPath(m: Manifest): string | null {
  if (m.kind === "business") return join(FRONTEND, "activities", m.activity ?? "general", "modules", m.id, "index.ts");
  if (m.kind === "platform") return join(FRONTEND, "platform", m.id, "index.ts");
  if (m.kind === "integration") return join(FRONTEND, "integrations", m.id, "index.ts");
  return null;
}

describe("module contract", () => {
  it("finds the active manifests", () => {
    expect(active.length).toBeGreaterThan(5);
  });

  it("every declared screen has a route (App.tsx or its module)", () => {
    const missing = active.flatMap((m) =>
      (m.screens ?? []).filter((s) => !routes.has(s.path.replace(/^\/+/, ""))).map((s) => `${m.id}: ${s.path}`),
    );
    expect(missing).toEqual([]);
  });

  it("every active module has a frontend index.ts", () => {
    const missing = active.filter((m) => indexPath(m) && !existsSync(indexPath(m) as string)).map((m) => `${m.id} (${m.kind})`);
    expect(missing).toEqual([]);
  });
});
