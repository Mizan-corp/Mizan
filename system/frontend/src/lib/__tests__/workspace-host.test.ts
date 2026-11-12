// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

// Workspaces on their own subdomain (ADR-008): the domain comes from VITE_WORKSPACE_DOMAIN,
// read when the modules load, so each case loads them fresh.
async function load(domain: string) {
  vi.resetModules();
  vi.stubEnv("VITE_WORKSPACE_DOMAIN", domain);
  vi.stubEnv("VITE_SYSTEM_URL", "https://app.example");
  const tenant = await import("@app/lib/tenant");
  const urls = await import("@/lib/urls");
  return { ...tenant, ...urls };
}

afterEach(() => vi.unstubAllEnvs());

describe("workspace addresses", () => {
  it("reads the workspace from its subdomain", async () => {
    const { workspaceFromHost, parseTenantFromLocation } = await load("allmizan.live");
    expect(workspaceFromHost("acme.allmizan.live")).toBe("acme");
    expect(workspaceFromHost("ACME.AllMizan.live")).toBe("acme");
    expect(parseTenantFromLocation("/pos", "acme.allmizan.live")).toEqual({ slug: "acme", root: "", isSubdomain: true });
  });

  it("ignores the apex, reserved names, deeper hosts and other domains", async () => {
    const { workspaceFromHost } = await load("allmizan.live");
    for (const host of ["allmizan.live", "www.allmizan.live", "dev.allmizan.live", "admin.allmizan.live",
                        "a.b.allmizan.live", "acme.allmizan.live.evil.com", "acme.vercel.app"]) {
      expect(workspaceFromHost(host), host).toBeNull();
    }
  });

  it("builds workspace links on the domain, or under /c/ without one", async () => {
    let { workspaceUrl } = await load("allmizan.live");
    expect(workspaceUrl("acme")).toBe("https://acme.allmizan.live/");
    expect(workspaceUrl("acme", "/login")).toBe("https://acme.allmizan.live/login");
    ({ workspaceUrl } = await load(""));
    expect(workspaceUrl("acme")).toBe("https://app.example/c/acme");
    expect(workspaceUrl("acme", "/login")).toBe("https://app.example/c/acme/login");
  });
});
