// @vitest-environment jsdom
// Website tab orders section: lists site-origin orders, moves an order along its
// lifecycle through /site/orders, and keeps empty/error states explicit.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const state = vi.hoisted(() => ({
  listOrders: vi.fn(),
  updateStatus: vi.fn(),
}));

vi.mock("./siteOrders", () => ({
  createSiteOrdersClient: () => ({
    listOrders: state.listOrders,
    updateStatus: state.updateStatus,
  }),
}));

import WebsiteOrders from "./WebsiteOrders";

const STATUSES = ["pending", "confirmed", "preparing", "out_for_delivery", "completed", "cancelled"];

const order = {
  id: "o1",
  order_number: "WEB-1001",
  customer_name: "عميل تجريبي",
  customer_phone: "01000000000",
  customer_email: null,
  delivery_type: "delivery",
  delivery_address: "عنوان",
  table_number: null,
  notes: null,
  subtotal: 100,
  delivery_fee: 30,
  discount_amount: 0,
  coupon_code: null,
  total_amount: 130,
  status: "pending",
  payment_method: "cod",
  payment_status: "unpaid",
  created_at: "2026-11-25T12:00:00+00:00",
  items: [{ product_name: "عصير", unit_price: 25, quantity: 2, total_price: 50, notes: null }],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("WebsiteOrders", () => {
  it("lists orders with customer, total and lifecycle select", async () => {
    state.listOrders.mockResolvedValue({ items: [order], page: 1, page_size: 50, statuses: STATUSES });
    render(<WebsiteOrders apiBase="/api" />);
    expect(await screen.findByText("WEB-1001")).toBeTruthy();
    expect(screen.getByText("عميل تجريبي")).toBeTruthy();
    const select = screen.getByRole("combobox", { name: "حالة الطلب WEB-1001" }) as HTMLSelectElement;
    expect(select.value).toBe("pending");
    expect(within_options(select)).toEqual(STATUSES);
  });

  it("moves an order to a new status and reflects the server result", async () => {
    state.listOrders.mockResolvedValue({ items: [order], page: 1, page_size: 50, statuses: STATUSES });
    state.updateStatus.mockResolvedValue({ ok: true, status: "completed", payment_status: "paid" });
    render(<WebsiteOrders apiBase="/api" />);
    const select = (await screen.findByRole("combobox", { name: "حالة الطلب WEB-1001" })) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "completed" } });
    await waitFor(() => expect(state.updateStatus).toHaveBeenCalledWith("o1", "completed"));
    await waitFor(() => expect(select.value).toBe("completed"));
    expect(await screen.findByText("مدفوع")).toBeTruthy();
  });

  it("shows the empty state when there are no orders", async () => {
    state.listOrders.mockResolvedValue({ items: [], page: 1, page_size: 50, statuses: STATUSES });
    render(<WebsiteOrders apiBase="/api" />);
    expect(await screen.findByText("لسه مفيش طلبات")).toBeTruthy();
  });

  it("shows the retry state on failure and reloads", async () => {
    state.listOrders.mockRejectedValueOnce(new Error("boom"));
    render(<WebsiteOrders apiBase="/api" />);
    const retry = await screen.findByRole("button", { name: /إعادة المحاولة/ });
    state.listOrders.mockResolvedValueOnce({ items: [order], page: 1, page_size: 50, statuses: STATUSES });
    fireEvent.click(retry);
    expect(await screen.findByText("WEB-1001")).toBeTruthy();
    expect(state.listOrders).toHaveBeenCalledTimes(2);
  });
});

function within_options(select: HTMLSelectElement): string[] {
  return Array.from(select.options).map((o) => o.value);
}
