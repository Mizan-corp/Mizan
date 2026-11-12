import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ signOutSession: vi.fn() }));

const replace = vi.fn();
function at(pathname: string, search = "") {
  vi.stubGlobal("window", { location: { pathname, search, replace } });
}

describe("sending owners to sign in", () => {
  beforeEach(() => {
    vi.resetModules();
    replace.mockReset();
  });

  it("keeps the page in next", async () => {
    at("/workspaces/abc", "?plan=pro");
    const { goToSignIn } = await import("@app/lib/session");
    goToSignIn();
    const url = new URL(replace.mock.calls[0][0], "http://x");
    expect(url.pathname.endsWith("/login")).toBe(true);
    expect(url.searchParams.get("next")).toBe("/workspaces/abc?plan=pro");
  });

  it("no next from the panel's home", async () => {
    at("/");
    const { goToSignIn } = await import("@app/lib/session");
    goToSignIn();
    expect(new URL(replace.mock.calls[0][0], "http://x").searchParams.has("next")).toBe(false);
  });

  it("signing out ends the session and doesn't come back to the page", async () => {
    at("/invoices");
    const api = await import("@/lib/api");
    const { signOut } = await import("@app/lib/session");
    signOut();
    expect(api.signOutSession).toHaveBeenCalledWith("/account/logout");
    const url = String(replace.mock.calls[0][0]);
    expect(url).toContain("/signout?to=login");
    expect(url).not.toContain("next=");
  });
});
