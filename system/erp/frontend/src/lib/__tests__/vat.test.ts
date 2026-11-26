import { describe, expect, it } from "vitest";
import { allocate, documentTaxes, lineTax, sumTaxes, type VatSettings } from "../vat";
import Decimal from "decimal.js";

const codes: VatSettings["codes"] = [
  { code: "standard", label: "", rate: 14 },
  { code: "zero", label: "", rate: 0 },
  { code: "exempt", label: "", rate: 0 },
];
const settings = (registered: boolean, inclusive: boolean): VatSettings => ({
  vat_registered: registered, prices_include_vat: inclusive, tax_number: "", tax_number_display: "", codes, default_code: "standard",
});
const s = (d: Decimal) => d.toFixed(2);

// The same cases as the server's tests (system/backend/tests/test_accounting_vat.py): both sides
// must agree to the piastre, or a sale with prices excluding VAT would be refused.
describe("VAT math mirrors the server", () => {
  it("includes or adds the tax per line, rounding half up", () => {
    const inc = lineTax("10", "standard", 14, true, true);
    expect([s(inc.net), s(inc.tax), s(inc.gross)]).toEqual(["8.77", "1.23", "10.00"]);
    const exc = lineTax("9.99", "standard", 14, true, false);
    expect([s(exc.net), s(exc.tax), s(exc.gross)]).toEqual(["9.99", "1.40", "11.39"]);
    expect(s(lineTax("0.25", "standard", 14, true, false).tax)).toBe("0.04");
    expect(s(lineTax("114", "standard", 14, false, true).tax)).toBe("0.00");
    expect(lineTax("114", "standard", 14, false, true).code).toBeNull();
  });

  it("takes discounts first and shares the invoice discount", () => {
    const lines = [{ amount: "100", code: "standard" as const }, { amount: "50", code: "exempt" as const }];
    const inc = documentTaxes(lines, "10", settings(true, true));
    expect(inc.map((t) => [s(t.net), s(t.tax)])).toEqual([["81.87", "11.46"], ["46.67", "0.00"]]);
    expect(s(sumTaxes(inc).gross)).toBe("140.00");
    const exc = documentTaxes(lines, "10", settings(true, false));
    expect(exc.map((t) => [s(t.net), s(t.tax)])).toEqual([["93.33", "13.07"], ["46.67", "0.00"]]);
    expect(allocate([new Decimal(1), new Decimal(1), new Decimal(1)], "1").map(s)).toEqual(["0.34", "0.33", "0.33"]);
    const weighed = documentTaxes([{ amount: "0.125", code: "standard" }, { amount: "6.999", code: "standard" }], 0, settings(true, true));
    expect(s(sumTaxes(weighed).gross)).toBe("7.12");
  });

  it("charges nothing on zero-rated and exempt lines, or when the workspace isn't registered", () => {
    const t = documentTaxes([{ amount: "100", code: "zero" }, { amount: "100", code: "exempt" }], 0, settings(true, false));
    expect(t.map((x) => [x.code, s(x.tax)])).toEqual([["zero", "0.00"], ["exempt", "0.00"]]);
    const none = documentTaxes([{ amount: "114", code: "standard" }], 0, settings(false, false));
    expect([none[0].code, s(none[0].tax), s(none[0].gross)]).toEqual([null, "0.00", "114.00"]);
  });
});
