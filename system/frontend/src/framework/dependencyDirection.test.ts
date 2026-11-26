// Migration step 2b (docs/modular-core-exploration.md, section 12): the dependency direction.
//   shared (becoming system/core)  imports no app.
//   owner, admin, website          import shared only, never the ERP app (system_api, system/frontend).
// Pure file scan. It pins today's direction before shared/ is merged into system/.
import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";

const ROOT = resolve(__dirname, "../../../..");
const SKIP = new Set(["node_modules", ".venv", "__pycache__", "build", "dist", "dist-studio", ".git", "uploads", "private_uploads", "updates"]);

function files(dir: string, exts: string[], out: string[] = []): string[] {
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    if (SKIP.has(name) || name.endsWith(".egg-info")) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) files(p, exts, out);
    else if (exts.some((e) => name.endsWith(e))) out.push(p);
  }
  return out;
}

function pyImports(file: string, pkgs: string[]): string[] {
  const re = new RegExp(`^\\s*(?:from|import)\\s+(${pkgs.join("|")})\\b`, "gm");
  return [...readFileSync(file, "utf8").matchAll(re)].map((m) => `${file.replace(ROOT, "")}: ${m[1]}`);
}

function tsImports(file: string, forbidden: RegExp): string[] {
  const src = readFileSync(file, "utf8");
  return [...src.matchAll(/(?:from|import)\s*\(?\s*["']([^"']+)["']/g)]
    .map((m) => m[1])
    .filter((spec) => forbidden.test(spec))
    .map((spec) => `${file.replace(ROOT, "")}: ${spec}`);
}

describe("dependency direction", () => {
  it("shared backend imports no app package", () => {
    const bad = files(join(ROOT, "shared/backend/app"), [".py"]).flatMap((f) => pyImports(f, ["system_api", "owner_api", "admin_api", "website_api"]));
    expect(bad).toEqual([]);
  });

  it("owner, admin and website backends never import the ERP API", () => {
    const bad = ["owner/backend", "admin/backend", "website/backend"].flatMap((d) => files(join(ROOT, d), [".py"]).flatMap((f) => pyImports(f, ["system_api"])));
    expect(bad).toEqual([]);
  });

  it("shared frontend imports no app (no @app alias, no path into an app)", () => {
    const forbidden = /^@app\/|(^|\/)(system|owner|admin|website)\/(frontend|backend)\//;
    const bad = files(join(ROOT, "shared/frontend/src"), [".ts", ".tsx"]).flatMap((f) => tsImports(f, forbidden));
    expect(bad).toEqual([]);
  });

  it("owner, admin and website frontends never import the ERP frontend", () => {
    const forbidden = /system\/frontend|\.\.\/\.\.\/system\//;
    const bad = ["owner/frontend/src", "admin/frontend/src", "website/frontend/src"].flatMap((d) => files(join(ROOT, d), [".ts", ".tsx"]).flatMap((f) => tsImports(f, forbidden)));
    expect(bad).toEqual([]);
  });

  it("scans real files (guard against an empty scan passing)", () => {
    expect(files(join(ROOT, "shared/backend/app"), [".py"]).length).toBeGreaterThan(100);
    expect(files(join(ROOT, "shared/frontend/src"), [".ts", ".tsx"]).length).toBeGreaterThan(20);
  });
});
