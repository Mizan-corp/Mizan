import { describe, expect, it } from "vitest";
import { confirmBody, editBody, editTotal, lineIssue, pagesOf, paymentLabel, returnItems, saleActions, statusLabel, type EditLine } from "../lib";

const holder = (...perms: string[]) => (p: string) => p.split("|").some((x) => perms.includes(x));
const doc = (status: string, extra: Record<string, unknown> = {}) =>
  ({ status, net_total: "100", returns_total: 0, is_credit: false, ...extra });

describe("saleActions", () => {
  it("shows cancel and return only to their holders, on confirmed invoices", () => {
    const sale = doc("confirmed");
    expect(saleActions(sale, holder("sales"))).toMatchObject({ cancel: false, returnSale: false, email: true, edit: false });
    expect(saleActions(sale, holder("sales", "sales:cancel", "sales:return"))).toMatchObject({ cancel: true, returnSale: true });
    // A returned invoice can't be cancelled; a fully returned one can't be returned again.
    expect(saleActions(doc("confirmed", { returns_total: "40" }), holder("sales:cancel", "sales:return")))
      .toMatchObject({ cancel: false, returnSale: true });
    expect(saleActions(doc("confirmed", { returns_total: "100" }), holder("sales:return")).returnSale).toBe(false);
    expect(saleActions(doc("cancelled"), holder("sales", "sales:cancel", "sales:return"))).toMatchObject({ cancel: false, returnSale: false });
  });

  it("lets drafts be changed by sales or POS users and quotations by quotation makers", () => {
    expect(saleActions(doc("draft"), holder("pos"))).toMatchObject({ confirm: true, edit: true, remove: true });
    expect(saleActions(doc("draft"), holder("quotations"))).toMatchObject({ confirm: false, edit: false, remove: false });
    expect(saleActions(doc("quotation"), holder("quotations"))).toMatchObject({ confirm: true, edit: true, remove: true, email: false });
    expect(saleActions(doc("quotation"), holder("pos"))).toMatchObject({ confirm: false, edit: false });
  });
});

describe("statusLabel", () => {
  it("names returns and credit", () => {
    expect(statusLabel(doc("confirmed", { returns_total: "100" }))).toBe("مرتجعة بالكامل");
    expect(statusLabel(doc("confirmed", { returns_total: "1" }))).toBe("مرتجعة جزئياً");
    expect(statusLabel(doc("confirmed", { is_credit: true }))).toBe("آجل");
    expect(statusLabel(doc("returned"))).toBe("مستند مرتجع");
  });
});

describe("confirmBody", () => {
  it("sends the safe or the wallet chosen", () => {
    expect(confirmBody("drawer")).toEqual({ destination: "drawer" });
    expect(confirmBody("credit")).toEqual({ destination: "credit" });
    expect(confirmBody("source", "safe:s1")).toEqual({ destination: "safe", safe_id: "s1" });
    expect(confirmBody("source", "wallet:w1")).toEqual({ destination: "wallet", wallet_id: "w1" });
    expect(() => confirmBody("source", "")).toThrow();
  });
});

describe("editing a draft or a quotation", () => {
  const lines: EditLine[] = [
    { product_id: "p1", product_name: "أ", qty: "2", unit_price: "100", discount: "10" },
    { product_id: "p2", product_name: "ب", qty: "1.5", unit_price: "20", discount: "0" },
  ];
  it("adds the lines, less their discounts and the invoice's", () => {
    expect(editTotal(lines, "5")).toBe("215.00");
  });
  it("sends a price only for those who may sell at another one", () => {
    const form = { lines, discount: "5", notes: " ", customer_id: "" };
    expect(editBody(form, false).items[0]).toEqual({ product_id: "p1", qty: "2", discount: "10" });
    expect(editBody(form, true).items[0]).toEqual({ product_id: "p1", qty: "2", discount: "10", unit_price: "100" });
    expect(editBody(form, false)).toMatchObject({ notes: null, customer_id: null, discount_amount: "5" });
  });
  it("refuses bad lines", () => {
    expect(lineIssue({ ...lines[0], qty: "0" })).toContain("كمية");
    expect(lineIssue({ ...lines[0], discount: "500" })).toContain("أكبر");
    expect(lineIssue(lines[1])).toBeNull();
  });
});

describe("returns and paging", () => {
  it("keeps the quantities above zero", () => {
    expect(returnItems({ a: "1", b: "", c: "0", d: "x", e: "2.5" })).toEqual([{ product_id: "a", qty: 1 }, { product_id: "e", qty: 2.5 }]);
  });
  it("counts pages from the total", () => {
    expect(pagesOf(0, 25)).toBe(1);
    expect(pagesOf(26, 25)).toBe(2);
  });
});

describe("paymentLabel", () => {
  it("names the method, none for a quotation", () => {
    expect(paymentLabel({ payment_method: "wallet", is_credit: false })).toBe("محفظة");
    expect(paymentLabel({ payment_method: "cash", is_credit: true })).toBe("آجل");
    expect(paymentLabel({ payment_method: "cash", is_credit: false, status: "quotation" })).toBe("—");
  });
});
