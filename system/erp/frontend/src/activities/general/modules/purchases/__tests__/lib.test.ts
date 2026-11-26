import { describe, expect, it } from "vitest";
import type { PurchaseLine, Suggestion } from "../api";
import { actionsFor, orderIssues, orderTotal, receiveIssues, receivePayload, receiveRows, receiveTotal, suggestionLine } from "../lib";

function line(id: string, ordered: string, received: string, cost = "10"): PurchaseLine {
  const left = Math.max(0, Number(ordered) - Number(received));
  return {
    id, product_id: `p-${id}`, product_name: `صنف ${id}`, sku: null, unit: "قطعة", qty_ordered: ordered, qty_received: received,
    qty_remaining: String(left), unit_cost: cost, current_cost: cost, notes: null,
  };
}

describe("the goods-receipt form", () => {
  it("starts with what is left of each line, at the order's cost", () => {
    const rows = receiveRows([line("a", "10", "4", "12.50"), line("b", "3", "3"), line("c", "2.5", "0")]);
    expect(rows.map((r) => [r.item_id, r.remaining, r.qty, r.unit_cost])).toEqual([["a", "6", "6", "12.5"], ["c", "2.5", "2.5", "10"]]);
    expect(receiveTotal(rows).toString()).toBe("100");
    expect(receiveIssues(rows)).toEqual([]);
  });

  it("refuses more than is left, bad numbers and an empty receipt", () => {
    const rows = receiveRows([line("a", "10", "4"), line("b", "5", "0")]);
    expect(receiveIssues([{ ...rows[0], qty: "7" }, rows[1]])).toEqual(["كمية «صنف a» أكبر من المتبقي (6)"]);
    expect(receiveIssues([{ ...rows[0], qty: "x" }, rows[1]])).toEqual(["كمية «صنف a» غير صحيحة"]);
    expect(receiveIssues([{ ...rows[0], unit_cost: "-1" }, rows[1]])).toEqual(["تكلفة «صنف a» غير صحيحة"]);
    expect(receiveIssues(rows.map((r) => ({ ...r, qty: "0" })))).toEqual(["أدخل كمية صنف واحد على الأقل"]);
  });

  it("sends every line by its id: 0 for what doesn't arrive, cost, batch and expiry for what does", () => {
    const [a, b] = receiveRows([line("a", "10", "4"), line("b", "5", "0")]);
    expect(receivePayload([{ ...a, qty: "٣", unit_cost: "11", batch_number: " L1 ", expiry_date: "2027-01-31" }, { ...b, qty: "" }])).toEqual([
      { item_id: "a", qty_received: "3", unit_cost: "11", batch_number: "L1", expiry_date: "2027-01-31" },
      { item_id: "b", qty_received: "0" },
    ]);
  });
});

describe("orders", () => {
  it("offer only what the order's state allows", () => {
    expect(actionsFor("draft")).toMatchObject({ edit: true, cancel: true, remove: true, receive: true, close: false, returnGoods: false });
    expect(actionsFor("partial")).toMatchObject({ edit: false, receive: true, close: true, returnGoods: true });
    expect(actionsFor("received")).toMatchObject({ receive: false, close: false, returnGoods: true });
    expect(Object.values(actionsFor("cancelled")).some(Boolean)).toBe(false);
  });

  it("total and check the order form's lines", () => {
    const lines = [{ product_id: "a", name: "أ", qty: "2", unit_cost: "12.5" }, { product_id: "b", name: "ب", qty: "1.5", unit_cost: "4" }];
    expect(orderTotal(lines).toString()).toBe("31");
    expect(orderIssues(lines)).toEqual([]);
    expect(orderIssues([])).toEqual(["أضف صنفاً واحداً على الأقل"]);
    expect(orderIssues([{ ...lines[0], qty: "0", unit_cost: "x" }])).toEqual(["كمية «أ»", "تكلفة «أ»"]);
  });

  it("turn a suggestion into a line: its reorder quantity, else back above the point", () => {
    const s: Suggestion = { id: "p", name: "صنف", sku: null, cost_price: "8", reorder_point: "10", reorder_qty: "0", total_stock: "3", unit: "قطعة" };
    expect(suggestionLine(s)).toEqual({ product_id: "p", name: "صنف", qty: "17", unit_cost: "8" });
    expect(suggestionLine({ ...s, reorder_qty: "24" }).qty).toBe("24");
    expect(suggestionLine({ ...s, total_stock: "-5", cost_price: null })).toMatchObject({ qty: "25", unit_cost: "0" });
  });
});
