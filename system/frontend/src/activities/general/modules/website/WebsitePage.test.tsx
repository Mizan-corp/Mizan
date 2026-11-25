// @vitest-environment jsdom
// Website tab (user decisions 2026-11-25): pages managed from the ERP Website
// module; design edits launch the standalone Studio in a NEW full browser tab
// (target _blank + noopener) with the page id in the query string, never a token.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const state = vi.hoisted(() => ({
  listPages: vi.fn(),
  open: vi.fn(),
}));

vi.mock("@app/features/studio/sitePages", async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>();
  return { ...actual, createSitePagesClient: () => ({ listPages: state.listPages }) };
});
vi.mock("@app/features/studio/WebsiteModuleSettings", () => ({ default: () => null }));
// The orders panel has its own suite (WebsiteOrders.test.tsx); keep it inert here.
vi.mock("./siteOrders", () => ({
  createSiteOrdersClient: () => ({
    listOrders: vi.fn().mockResolvedValue({ items: [], page: 1, page_size: 50, statuses: [] }),
    updateStatus: vi.fn(),
  }),
}));

import WebsitePage, { studioLaunchUrl } from "./WebsitePage";

const published = {
  id: "p1",
  slug: "home",
  titles: { ar: "الرئيسية" },
  status: "published",
  has_draft: false,
  published: true,
  created_at: null,
  updated_at: null,
};
const draft = {
  id: "p2",
  slug: "about",
  titles: { ar: "عنّا" },
  status: "draft",
  has_draft: true,
  published: false,
  created_at: null,
  updated_at: null,
};
const archived = {
  id: "p3",
  slug: "old",
  titles: { ar: "قديمة" },
  status: "archived",
  has_draft: false,
  published: false,
  created_at: null,
  updated_at: null,
};

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
  it("lists non-archived pages with their status", async () => {
    state.listPages.mockResolvedValue({ items: [published, draft, archived] });
    render(<WebsitePage />);
    expect(await screen.findByText("الرئيسية")).toBeTruthy();
    expect(screen.getByText("عنّا")).toBeTruthy();
    expect(screen.queryByText("قديمة")).toBeNull();
    expect(screen.getByText("منشورة")).toBeTruthy();
    expect(screen.getByText("مسودة")).toBeTruthy();
  });

  it("opens the standalone Studio in a new tab with the page loaded", async () => {
    state.listPages.mockResolvedValue({ items: [published] });
    vi.stubGlobal("open", state.open);
    render(<WebsitePage />);
    const edit = await screen.findByRole("button", { name: /تعديل في Studio/ });
    fireEvent.click(edit);
    expect(state.open).toHaveBeenCalledWith("/studio/?page=p1", "_blank", "noopener,noreferrer");
  });

  it("opens Studio without a page from the header action", async () => {
    state.listPages.mockResolvedValue({ items: [published] });
    vi.stubGlobal("open", state.open);
    render(<WebsitePage />);
    const open = await screen.findAllByRole("button", { name: /فتح Studio/ });
    fireEvent.click(open[0]);
    expect(state.open).toHaveBeenCalledWith("/studio/", "_blank", "noopener,noreferrer");
  });

  it("shows the retry state on failure and reloads", async () => {
    state.listPages.mockRejectedValueOnce(new Error("boom"));
    render(<WebsitePage />);
    const retry = await screen.findByRole("button", { name: /إعادة المحاولة/ });
    state.listPages.mockResolvedValueOnce({ items: [published] });
    fireEvent.click(retry);
    expect(await screen.findByText("الرئيسية")).toBeTruthy();
    expect(state.listPages).toHaveBeenCalledTimes(2);
  });

  it("shows the empty state when there are no pages", async () => {
    state.listPages.mockResolvedValue({ items: [] });
    render(<WebsitePage />);
    expect(await screen.findByText("لسه مفيش صفحات")).toBeTruthy();
  });
});
