import { describe, expect, it } from "vitest";
import {
  componentsCost, groupSubcategories, handMovementIssues, imageSrc, movementLabel, parseNumber, signedQty,
} from "../lib";

describe("parseNumber", () => {
  it("reads Latin, Arabic and Persian digits and both decimal points", () => {
    expect(parseNumber("12.5")?.toString()).toBe("12.5");
    expect(parseNumber("١٢٫٥")?.toString()).toBe("12.5");
    expect(parseNumber("۳")?.toString()).toBe("3");
    expect(parseNumber("1,250")?.toString()).toBe("1250");
  });
  it("refuses what isn't a quantity", () => {
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("-3")).toBeNull();
    expect(parseNumber("abc")).toBeNull();
    expect(parseNumber("1.2345")).toBeNull();
    expect(parseNumber("1.234")?.toString()).toBe("1.234");
    expect(parseNumber("1.234", 2)).toBeNull();
  });
});

describe("movements", () => {
  it("label each type and sign its quantity", () => {
    expect(movementLabel("damage")).toEqual({ label: "تالف", inbound: false });
    expect(signedQty("purchase", "4").toString()).toBe("4");
    expect(signedQty("transfer_out", "4").toString()).toBe("-4");
    expect(movementLabel("dispatch_cancel").label).toBe("dispatch_cancel");
  });
});

describe("handMovementIssues", () => {
  const base = { type: "adjustment_in" as const, product_id: "p", warehouse_id: "w", qty: "3", unit_cost: "", note: "" };
  it("accepts a complete adjustment in, with or without a cost", () => {
    expect(handMovementIssues(base)).toEqual([]);
    expect(handMovementIssues({ ...base, unit_cost: "12.50" })).toEqual([]);
  });
  it("asks for a reason for damage and a shortage, and a positive quantity", () => {
    expect(handMovementIssues({ ...base, type: "damage" })).toEqual(["اكتب السبب"]);
    expect(handMovementIssues({ ...base, type: "adjustment_out", note: "عجز جرد" })).toEqual([]);
    expect(handMovementIssues({ ...base, qty: "0" })).toEqual(["أدخل كمية أكبر من صفر"]);
    expect(handMovementIssues({ ...base, product_id: "", unit_cost: "x" })).toEqual(["اختر الصنف", "تكلفة الوحدة غير صحيحة"]);
  });
});

describe("groupSubcategories", () => {
  it("puts each subcategory under its category, keeping the categories' order", () => {
    const cats = [{ id: "b", name: "ب", code: null }, { id: "a", name: "أ", code: null }];
    const subs = [{ id: "1", name: "س", code: null, category_id: "a" }, { id: "2", name: "ص", code: null, category_id: "b" },
      { id: "3", name: "ع", code: null, category_id: "a" }];
    expect(groupSubcategories(cats, subs).map((g) => [g.category.id, g.subcategories.map((s) => s.id)]))
      .toEqual([["b", ["2"]], ["a", ["1", "3"]]]);
  });
});

describe("collections and pictures", () => {
  it("cost the items, or nothing when a cost is hidden", () => {
    expect(componentsCost([{ product_id: "a", qty: "2", avg_cost: "10.5" }, { product_id: "b", qty: "1.5", avg_cost: "4" }])?.toString()).toBe("27");
    expect(componentsCost(null)?.toString()).toBe("0");
    expect(componentsCost([{ product_id: "a", qty: "2", avg_cost: "10.5" }, { product_id: "b", qty: "1", avg_cost: null }])).toBeNull();
  });
  it("serve relative uploads through the API and keep absolute links", () => {
    const api = (p: string) => `https://api.test${p}`;
    expect(imageSrc("/uploads/t/p.png", api)).toBe("https://api.test/uploads/t/p.png");
    expect(imageSrc("https://blob.example/p.png", api)).toBe("https://blob.example/p.png");
    expect(imageSrc(null, api)).toBeNull();
  });
});
