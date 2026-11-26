import { describe, expect, it } from "vitest";
import { amountOrNull, expenseActions, pageCount, recurrenceBody } from "../lib";

describe("expenseActions", () => {
  it("lets only a draft be decided or edited in full", () => {
    expect(expenseActions({ status: "draft" })).toEqual({ edit: "full", approve: true, reject: true, remove: true, cancel: false });
  });
  it("keeps a decided expense to its notes", () => {
    expect(expenseActions({ status: "approved", payment_method: "cash" })).toEqual({ edit: "notes", approve: false, reject: false, remove: false, cancel: true });
    expect(expenseActions({ status: "rejected" })).toMatchObject({ edit: "notes", approve: false, remove: true, cancel: false });
    expect(expenseActions({ status: "cancelled" })).toMatchObject({ edit: "notes", remove: false, cancel: false });
  });
  it("leaves the payroll's expense to the payroll screen", () => {
    expect(expenseActions({ status: "approved", payment_method: "payroll" }).cancel).toBe(false);
  });
});

describe("amountOrNull", () => {
  it("reads typed amounts", () => {
    expect(amountOrNull("1500")).toBe("1500.00");
    expect(amountOrNull(" ١٢٫٥ ")).toBe("12.50");
    expect(amountOrNull("1,250.75")).toBe("1250.75");
  });
  it("refuses what isn't a positive amount of piastres", () => {
    for (const bad of ["", "0", "-5", "1.234", "abc", "1e3"]) expect(amountOrNull(bad)).toBeNull();
  });
});

describe("recurrenceBody", () => {
  it("sends the interval and end only when the expense recurs", () => {
    expect(recurrenceBody({ is_recurring: true, recurring_interval: "weekly", recurring_end_date: "" }))
      .toEqual({ is_recurring: true, recurring_interval: "weekly", recurring_end_date: null });
    expect(recurrenceBody({ is_recurring: false, recurring_interval: "monthly", recurring_end_date: "2026-12-31" }))
      .toEqual({ is_recurring: false, recurring_interval: null, recurring_end_date: null });
  });
});

describe("pageCount", () => {
  it("has at least one page", () => {
    expect(pageCount(0, 25)).toBe(1);
    expect(pageCount(25, 25)).toBe(1);
    expect(pageCount(26, 25)).toBe(2);
  });
});
