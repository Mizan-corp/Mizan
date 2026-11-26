import { describe, expect, it } from "vitest";
import {
  CASH_NEEDS_SHIFT, SHIFT_REQUIRED, canApprove, canCancelTx, canOverridePrice, closeDifference, linePrice, lineTotal, nextDayIssue,
  paymentGate, posSettings, priceChanged,
} from "../lib";

const holder = (...perms: string[]) => (p: string) => p.split("|").some((x) => perms.includes(x));
const product = { retail_price: "100", wholesale_price: "85" };

describe("posSettings", () => {
  it("falls back to the manifest's defaults and reads saved strings", () => {
    expect(posSettings(undefined)).toEqual({ requireActiveShift: true, allowPriceOverride: false, autoPrintReceipt: false, enableQuickNumpad: true });
    expect(posSettings({ require_active_shift: "false", auto_print_receipt: true, enable_quick_numpad: "0", allow_price_override: "true" }))
      .toEqual({ requireActiveShift: false, allowPriceOverride: true, autoPrintReceipt: true, enableQuickNumpad: false });
  });
});

describe("price override", () => {
  it("needs the setting and the permission", () => {
    expect(canOverridePrice({ allowPriceOverride: true }, holder("sales:override_price"))).toBe(true);
    expect(canOverridePrice({ allowPriceOverride: true }, holder("pos"))).toBe(false);
    expect(canOverridePrice({ allowPriceOverride: false }, holder("sales:override_price"))).toBe(false);
  });
  it("uses the typed price only when allowed", () => {
    const line = { product, qty: 2, discount: "10", price: "90" };
    expect(linePrice(line, "retail", true).toString()).toBe("90");
    expect(linePrice(line, "retail", false).toString()).toBe("100");
    expect(linePrice(line, "wholesale", false).toString()).toBe("85");
    expect(lineTotal(line, "retail", true).toString()).toBe("170");
    expect(priceChanged(line, "retail", true)).toBe(true);
    expect(priceChanged(line, "retail", false)).toBe(false);
    // An empty or bad price falls back to the product's.
    expect(linePrice({ ...line, price: "" }, "retail", true).toString()).toBe("100");
    expect(linePrice({ ...line, price: "-1" }, "retail", true).toString()).toBe("100");
  });
});

describe("paymentGate", () => {
  it("follows require_active_shift", () => {
    expect(paymentGate(undefined, true).canPay).toBe(false);
    expect(paymentGate(true, true)).toEqual({ canPay: true, cashAllowed: true, message: null });
    expect(paymentGate(false, true)).toEqual({ canPay: false, cashAllowed: false, message: SHIFT_REQUIRED });
    expect(paymentGate(false, false)).toEqual({ canPay: true, cashAllowed: false, message: CASH_NEEDS_SHIFT });
  });
});

describe("the drawer", () => {
  it("approvers are supervisors or managers with shifts", () => {
    expect(canApprove(false, holder("supervise"))).toBe(true);
    expect(canApprove(true, holder("shifts"))).toBe(true);
    expect(canApprove(true, holder("pos"))).toBe(false);
    expect(canApprove(false, holder("shifts"))).toBe(false);
  });
  it("cancels only rows entered by hand in an open shift", () => {
    const row = { id: "1", type: "expense", ref_id: null, cancelled_at: null };
    expect(canCancelTx(row, true, true)).toBe(true);
    expect(canCancelTx(row, true, false)).toBe(false);
    expect(canCancelTx(row, false, true)).toBe(false);
    expect(canCancelTx({ ...row, type: "sale", ref_id: "s" }, true, true)).toBe(false);
    expect(canCancelTx({ ...row, type: "revenue_delivery" }, true, true)).toBe(false);
    expect(canCancelTx({ ...row, cancelled_at: "2026-01-01" }, true, true)).toBe(false);
  });
  it("names the difference at closing and bounds what stays", () => {
    expect(closeDifference("", 100)).toBeNull();
    expect(closeDifference("90", "100")).toMatchObject({ label: "عجز" });
    expect(closeDifference("100", "100.00")?.label).toBe("مطابق");
    expect(closeDifference("120", 100)?.value.toString()).toBe("20");
    expect(nextDayIssue("100", "")).toBeNull();
    expect(nextDayIssue("100", "150")).toContain("أكبر");
    expect(nextDayIssue("100", "-1")).not.toBeNull();
    expect(nextDayIssue("100", "50")).toBeNull();
  });
});
