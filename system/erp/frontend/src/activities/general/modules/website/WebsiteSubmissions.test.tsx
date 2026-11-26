// @vitest-environment jsdom
// Website tab form-submissions inbox: lists visitor messages, filters unread,
// and marks a message read through /site/forms, with explicit empty/error states.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const state = vi.hoisted(() => ({
  listSubmissions: vi.fn(),
  markRead: vi.fn(),
}));

vi.mock("./siteForms", () => ({
  createSiteFormsClient: () => ({
    listSubmissions: state.listSubmissions,
    markRead: state.markRead,
  }),
}));

import WebsiteSubmissions from "./WebsiteSubmissions";

const unread = {
  id: "s1",
  page_id: "p1",
  page_slug: "contact",
  block_id: "n_form01",
  payload: { name: "Ammar", email: "ammar@example.com", message: "عايز أسأل عن منتج" },
  created_at: "2026-11-26T00:00:00+00:00",
  read_at: null,
};

const read = {
  ...unread,
  id: "s2",
  payload: { email: "reader@example.com", message: "hello" },
  read_at: "2026-11-26T01:00:00+00:00",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("WebsiteSubmissions", () => {
  it("lists messages with sender, text, page and read state", async () => {
    state.listSubmissions.mockResolvedValue({ submissions: [unread, read] });
    render(<WebsiteSubmissions apiBase="/api" />);
    expect(await screen.findByText("Ammar")).toBeTruthy();
    expect(screen.getByText("عايز أسأل عن منتج")).toBeTruthy();
    expect(screen.getAllByText("/contact").length).toBe(2);
    expect(screen.getByText("مقروءة")).toBeTruthy();
    expect(screen.getByRole("button", { name: "تحديد رسالة Ammar كمقروءة" })).toBeTruthy();
  });

  it("marks an unread message read through the API", async () => {
    state.listSubmissions.mockResolvedValue({ submissions: [unread] });
    state.markRead.mockResolvedValue({ ...unread, read_at: "2026-11-26T02:00:00+00:00" });
    render(<WebsiteSubmissions apiBase="/api" />);
    const button = await screen.findByRole("button", { name: "تحديد رسالة Ammar كمقروءة" });
    fireEvent.click(button);
    await waitFor(() => expect(state.markRead).toHaveBeenCalledWith("s1"));
    expect(await screen.findByText("مقروءة")).toBeTruthy();
  });

  it("falls back to the email when no name was asked", async () => {
    state.listSubmissions.mockResolvedValue({ submissions: [read] });
    render(<WebsiteSubmissions apiBase="/api" />);
    expect(await screen.findByText("reader@example.com")).toBeTruthy();
  });

  it("toggles the unread-only filter and reloads", async () => {
    state.listSubmissions.mockResolvedValue({ submissions: [] });
    render(<WebsiteSubmissions apiBase="/api" />);
    await screen.findByText("لسه مفيش رسائل");
    fireEvent.click(screen.getByRole("button", { name: "غير المقروءة بس" }));
    await waitFor(() => expect(state.listSubmissions).toHaveBeenLastCalledWith(true));
  });

  it("shows the empty and error states", async () => {
    state.listSubmissions.mockResolvedValue({ submissions: [] });
    render(<WebsiteSubmissions apiBase="/api" />);
    expect(await screen.findByText("لسه مفيش رسائل")).toBeTruthy();
    cleanup();
    state.listSubmissions.mockRejectedValue(new Error("down"));
    render(<WebsiteSubmissions apiBase="/api" />);
    await waitFor(() => expect(screen.getByRole("button", { name: /حاول|retry|تحديث/i })).toBeTruthy());
  });
});
