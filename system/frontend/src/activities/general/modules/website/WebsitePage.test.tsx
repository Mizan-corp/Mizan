// @vitest-environment jsdom
// Website tab (user decisions 2026-11-25, revised split approved 19:05): the full
// page lifecycle lives in Studio; the Website tab owns modules data/access/orders
// and launches the standalone Studio in a NEW full browser tab (target _blank +
// noopener) with the page id in the query string, never a token.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

const state = vi.hoisted(() => ({
  open: vi.fn(),
}));

vi.mock("@app/features/studio/WebsiteModuleSettings", () => ({ default: () => null }));
// Orders and published-products panels have their own suites.
vi.mock("./WebsiteOrders", () => ({ default: () => <div data-testid="orders-panel" /> }));
vi.mock("./WebsitePublishedProducts", () => ({ default: () => <div data-testid="products-panel" /> }));

import WebsitePage, { studioLaunchUrl } from "./WebsitePage";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("studioLaunchUrl", () => {
  it("carries only the page id in the query string", () => {
    expect(studioLaunchUrl("p1")).toBe("/studio/?page=p1");
    expect(studioLaunchUrl()).toBe("/studio/");
  });
});

describe("WebsitePage", () => {
  it("launches the standalone Studio in a new tab from the header action", () => {
    vi.stubGlobal("open", state.open);
    render(<WebsitePage />);
    fireEvent.click(screen.getByRole("button", { name: /فتح Studio/ }));
    expect(state.open).toHaveBeenCalledWith("/studio/", "_blank", "noopener,noreferrer");
  });

  it("mounts the orders and published-products surfaces", () => {
    render(<WebsitePage />);
    expect(screen.getByTestId("orders-panel")).toBeTruthy();
    expect(screen.getByTestId("products-panel")).toBeTruthy();
  });

  it("has no pages management list (page lifecycle lives in Studio)", () => {
    render(<WebsitePage />);
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByText("الصفحات")).toBeNull();
  });
});
