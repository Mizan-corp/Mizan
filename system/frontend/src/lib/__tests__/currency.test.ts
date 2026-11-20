import { describe, expect, it } from "vitest";
import { currencyLabel, moneyIn } from "../currency";

describe("currencyLabel", () => {
  it("is the workspace's currency, the Egyptian pound by default", () => {
    expect(currencyLabel(undefined)).toBe("ج.م");
    expect(currencyLabel(" egp ")).toBe("ج.م");
    expect(currencyLabel("SAR")).toBe("ر.س");
    expect(currencyLabel("دينار")).toBe("دينار");
  });
  it("writes an amount with it", () => {
    expect(moneyIn("1234.5", "ر.س")).toBe("1,234.50 ر.س");
  });
});
