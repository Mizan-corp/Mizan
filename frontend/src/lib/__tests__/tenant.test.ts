// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { parseTenantFromLocation } from "@/lib/tenant";

describe("parseTenantFromLocation", () => {
  it("ignores literal 'undefined' in /c/undefined/pos", () => {
    const res = parseTenantFromLocation("/c/undefined/pos", "localhost");
    expect(res.slug).toBeNull();
  });

  it("ignores literal 'null' in /c/null/pos", () => {
    const res = parseTenantFromLocation("/c/null/pos", "localhost");
    expect(res.slug).toBeNull();
  });

  it("parses valid tenant slug in /c/my-gym/pos", () => {
    const res = parseTenantFromLocation("/c/my-gym/pos", "localhost");
    expect(res.slug).toBe("my-gym");
    expect(res.root).toBe("/c/my-gym");
    expect(res.isSubdomain).toBe(false);
  });

  it("parses valid direct tenant path /my-gym/dashboard", () => {
    const res = parseTenantFromLocation("/my-gym/dashboard", "localhost");
    expect(res.slug).toBe("my-gym");
    expect(res.root).toBe("/my-gym");
    expect(res.isSubdomain).toBe(false);
  });

  it("does not treat reserved root paths as tenant slugs", () => {
    const res = parseTenantFromLocation("/login", "localhost");
    expect(res.slug).toBeNull();
    const res2 = parseTenantFromLocation("/pos", "localhost");
    expect(res2.slug).toBeNull();
  });
});
