import { describe, expect, it } from "vitest";
import { safeInternalPath } from "@/lib/urls";

describe("return paths stay on the site", () => {
  it.each(["/", "/workspaces/1?plan=pro", "/invoices#paid", "/a/b/../c"])("keeps %s", (p) =>
    expect(safeInternalPath(p)).toBe(new URL(p, "http://h").pathname + new URL(p, "http://h").search + new URL(p, "http://h").hash));

  it.each([null, "", "workspaces", "//evil.com", "/\\evil.com", "https://evil.com/x", "javascript:alert(1)",
    "/\t/evil.com", " /x", "\\\\evil.com"])("rejects %s", (p) => expect(safeInternalPath(p)).toBe("/"));

  it("uses the fallback given", () => expect(safeInternalPath("//x", "/login")).toBe("/login"));
});
