// @vitest-environment jsdom
// Website tab published-products summary: read-only view over the existing consent
// endpoints - which products are on the site and under which website attributes.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import WebsitePublishedProducts from "./WebsitePublishedProducts";

const CARDS = {
  value: {
    products: ["p1", "p2"],
    show_price: true,
    show_image: false,
    show_description: true,
    currency: "EGP",
  },
};
const CHOICES = {
  products: {
    items: [
      { id: "p1", name: "عصير ليمون" },
      { id: "p2", name: "تشيز كيك" },
    ],
    truncated: false,
  },
};

function stubFetch(cards: unknown = CARDS, choices: unknown = CHOICES, fail = false) {
  vi.stubGlobal("fetch", vi.fn(async (input: string) => {
    if (fail) return { ok: false, status: 500, json: async () => ({}) } as Response;
    const payload = input.includes("/cards") ? cards : choices;
    return { ok: true, status: 200, json: async () => payload } as Response;
  }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("WebsitePublishedProducts", () => {
  it("lists published product names with the website attribute policy", async () => {
    stubFetch();
    render(<WebsitePublishedProducts apiBase="/api" />);
    expect(await screen.findByText("عصير ليمون")).toBeTruthy();
    expect(screen.getByText("تشيز كيك")).toBeTruthy();
    expect(screen.getByText("2 منتج")).toBeTruthy();
    expect(screen.getByText("السعر ظاهر")).toBeTruthy();
    expect(screen.getByText("الصورة مخفية")).toBeTruthy();
    expect(screen.getByText("الوصف ظاهر")).toBeTruthy();
    expect(screen.getByText("EGP")).toBeTruthy();
  });

  it("shows the empty state when nothing is published", async () => {
    stubFetch({ value: { products: [], show_price: false, show_image: false, show_description: false, currency: null } });
    render(<WebsitePublishedProducts apiBase="/api" />);
    expect(await screen.findByText("لسه مفيش منتجات منشورة")).toBeTruthy();
  });

  it("shows the retry state on failure and reloads", async () => {
    stubFetch(undefined, undefined, true);
    render(<WebsitePublishedProducts apiBase="/api" />);
    const retry = await screen.findByRole("button", { name: /إعادة المحاولة/ });
    stubFetch();
    fireEvent.click(retry);
    expect(await screen.findByText("عصير ليمون")).toBeTruthy();
  });
});
