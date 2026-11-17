import { describe, expect, it } from "vitest";
import type { AccountNode } from "../api";
import {
  type AccountInfo, emptyLine, fiscalYearOf, fiscalYearRange, flattenChart, type LineForm, lineIssues, monthLabel, natural, parseAmount,
  postable, printHtml, requiredParty, sourceLabel, toCsv, toPayload, totals,
} from "../lib";

const ACC: Record<string, AccountInfo> = {
  cash: { id: "cash", code: "1251001", name: "خزنة", type: "asset", is_group: false, active: true, role: null, money_kind: "safe" },
  ar: { id: "ar", code: "122", name: "العملاء", type: "asset", is_group: false, active: true, role: "receivables" },
  ap: { id: "ap", code: "21", name: "الموردون", type: "liability", is_group: false, active: true, role: "payables" },
  inv: { id: "inv", code: "121", name: "المخزون", type: "asset", is_group: false, active: true, role: "inventory" },
  grp: { id: "grp", code: "12", name: "أصول متداولة", type: "asset", is_group: true, active: true, role: null },
  rent: { id: "rent", code: "522", name: "الإيجارات", type: "expense", is_group: false, active: true, role: "rent_expense" },
  adv: { id: "adv", code: "123", name: "سلف الموظفين", type: "asset", is_group: false, active: true, role: "employee_advances" },
  drawer: { id: "drawer", code: "1251002", name: "درج", type: "asset", is_group: false, active: true, role: null, money_kind: "drawer" },
  off: { id: "off", code: "599", name: "موقوف", type: "expense", is_group: false, active: false, role: null },
};
const accounts = new Map(Object.entries(ACC));

function line(account_id: string, debit = "", credit = "", extra: Partial<LineForm> = {}): LineForm {
  return { ...emptyLine(), account_id, debit, credit, ...extra };
}

describe("parseAmount", () => {
  it("reads Latin, Arabic and Persian digits and both decimal points", () => {
    expect(parseAmount("150.5")?.toString()).toBe("150.5");
    expect(parseAmount("١٥٠٫٧٥")?.toString()).toBe("150.75");
    expect(parseAmount("۱۲۳")?.toString()).toBe("123");
    expect(parseAmount("1,250.00")?.toString()).toBe("1250");
    expect(parseAmount("12,5")?.toString()).toBe("12.5");
    expect(parseAmount(" ")?.toString()).toBe("0");
  });
  it("refuses negatives, words and more than two decimals", () => {
    expect(parseAmount("-5")).toBeNull();
    expect(parseAmount("abc")).toBeNull();
    expect(parseAmount("1.234")).toBeNull();
  });
});

describe("totals: the balance indicator", () => {
  it("adds debits and credits exactly (no float drift) and says when they balance", () => {
    const t = totals([line("rent", "0.1"), line("rent", "0.2"), line("cash", "", "0.3")]);
    expect(t.debit.toString()).toBe("0.3");
    expect(t.credit.toString()).toBe("0.3");
    expect(t.balanced).toBe(true);
    expect(t.filled).toBe(3);
  });
  it("shows the difference while unbalanced; an empty form is not balanced", () => {
    const t = totals([line("rent", "100"), line("cash", "", "60")]);
    expect(t.balanced).toBe(false);
    expect(t.difference.toString()).toBe("40");
    expect(totals([emptyLine(), emptyLine()]).balanced).toBe(false);
  });
});

describe("lineIssues: the posting rules of a manual entry (ADR-014 D9)", () => {
  it("passes a balanced entry with a customer on receivables", () => {
    expect(lineIssues([line("ar", "50", "", { party_type: "customer", party_id: "c1" }), line("cash", "", "50")], accounts)).toEqual([]);
  });
  it("needs a customer on receivables and a supplier on payables", () => {
    const issues = lineIssues([line("ar", "50"), line("ap", "", "50", { party_type: "customer", party_id: "c1" })], accounts);
    expect(issues.some((i) => i.includes("حدد العميل"))).toBe(true);
    expect(issues.some((i) => i.includes("حدد المورد"))).toBe(true);
  });
  it("refuses inventory, groups, drawers, stopped accounts and parties where they don't belong", () => {
    const issues = lineIssues([
      line("inv", "10"), line("grp", "10"), line("drawer", "10"), line("off", "10"),
      line("rent", "10", "", { party_type: "customer", party_id: "c1" }), line("cash", "", "50"),
    ], accounts);
    expect(issues.some((i) => i.includes("المخزون"))).toBe(true);
    expect(issues.some((i) => i.includes("تجميعي"))).toBe(true);
    expect(issues.some((i) => i.includes("درج الكاشير"))).toBe(true);
    expect(issues.some((i) => i.includes("موقوف"))).toBe(true);
    expect(issues.some((i) => i.includes("لا يُذكر العميل"))).toBe(true);
  });
  it("allows an employee on advances, and asks for one when the type is chosen", () => {
    expect(lineIssues([line("adv", "10", "", { party_type: "employee", party_id: "e1" }), line("cash", "", "10")], accounts)).toEqual([]);
    expect(lineIssues([line("adv", "10", "", { party_type: "employee" }), line("cash", "", "10")], accounts)[0]).toContain("اختر الموظف");
  });
  it("flags unbalanced entries, a missing account, both sides on a line, a single line and bad amounts", () => {
    expect(lineIssues([line("rent", "100"), line("cash", "", "60")], accounts).at(-1)).toContain("الفرق 40.00");
    expect(lineIssues([line("", "10"), line("cash", "", "10")], accounts)[0]).toContain("اختر الحساب");
    expect(lineIssues([line("rent", "5", "5"), line("cash", "", "0")], accounts).some((i) => i.includes("لا الاثنان"))).toBe(true);
    expect(lineIssues([line("rent", "10")], accounts).some((i) => i.includes("سطرين"))).toBe(true);
    expect(lineIssues([line("rent", "1.234"), line("cash", "", "1")], accounts)[0]).toContain("المبلغ غير صحيح");
  });
  it("ignores the empty lines of the form", () => {
    expect(lineIssues([line("rent", "10"), emptyLine(), line("cash", "", "10"), emptyLine()], accounts)).toEqual([]);
  });
});

describe("toPayload", () => {
  it("drops empty lines, fixes amounts to 2 decimals and clears a party with no type", () => {
    const body = toPayload({ date: "2026-11-01", memo: "  ", warehouse_id: "", lines: [
      line("rent", "١٠٠"), emptyLine(), line("cash", "", "100", { party_id: "stale" }),
    ] });
    expect(body.memo).toBeNull();
    expect(body.warehouse_id).toBeNull();
    expect(body.lines).toEqual([
      { account_id: "rent", debit: "100.00", credit: "0.00", party_type: null, party_id: null, warehouse_id: null },
      { account_id: "cash", debit: "0.00", credit: "100.00", party_type: null, party_id: null, warehouse_id: null },
    ]);
  });
});

describe("the chart", () => {
  const node = (id: string, code: string, children: AccountNode[] = [], extra: Partial<AccountNode> = {}): AccountNode => ({
    id, code, name: id, name_en: null, type: "asset", parent_id: null, is_group: children.length > 0, role: null, active: true,
    money_kind: null, children, ...extra,
  });
  const tree = [node("assets", "1", [node("b", "12", [node("ar", "122", [], { role: "receivables" }), node("inv", "121", [], { role: "inventory" })]),
                                     node("a", "11")])];
  it("flattens in code order with depth, and hides collapsed children", () => {
    expect(flattenChart(tree).map((r) => [r.code, r.level])).toEqual([["1", 0], ["11", 1], ["12", 1], ["121", 2], ["122", 2]]);
    expect(flattenChart(tree, new Set(["b"])).map((r) => r.code)).toEqual(["1", "11", "12"]);
  });
  it("offers only postable accounts to a manual line", () => {
    expect(postable(flattenChart(tree)).map((r) => r.code)).toEqual(["11", "122"]);
  });
  it("shows balances in the account's natural direction", () => {
    expect(natural("asset", 50)).toBe(50);
    expect(natural("liability", -50)).toBe(50);
    expect(natural("income", -10)).toBe(10);
  });
  it("knows which party an account needs", () => {
    expect(requiredParty("receivables")).toBe("customer");
    expect(requiredParty("payables")).toBe("supplier");
    expect(requiredParty("rent_expense")).toBeNull();
  });
});

describe("months, fiscal years and sources", () => {
  it("labels months in Arabic", () => {
    expect(monthLabel("2026-03")).toBe("مارس 2026");
  });
  it("works out fiscal years starting in any month", () => {
    expect(fiscalYearRange(2026, 1)).toEqual({ from: "2026-01-01", to: "2026-12-31" });
    expect(fiscalYearRange(2025, 7)).toEqual({ from: "2025-07-01", to: "2026-06-30" });
    expect(fiscalYearRange(2023, 3)).toEqual({ from: "2023-03-01", to: "2024-02-29" });
    expect(fiscalYearOf("2026-03-05", 7)).toBe(2025);
    expect(fiscalYearOf("2026-08-05", 7)).toBe(2026);
  });
  it("names an entry's source, and its reversal", () => {
    expect(sourceLabel("sale", "confirm")).toBe("فاتورة بيع");
    expect(sourceLabel("manual", "reverse")).toBe("عكس — قيد يومية يدوي");
    expect(sourceLabel("unknown_kind")).toBe("unknown_kind");
  });
});

describe("export", () => {
  it("writes CSV with 2-decimal numbers and quotes where needed", () => {
    expect(toCsv(["الحساب", "مدين"], [["نقدية, رئيسية", 10], ['قال "نعم"', null]])).toBe(
      'الحساب,مدين\r\n"نقدية, رئيسية",10.00\r\n"قال ""نعم""",',
    );
  });
  it("prints an RTL page with the cells escaped", () => {
    const html = printHtml("ميزان <المراجعة>", "2026", ["الحساب"], [["<b>x</b>"]]);
    expect(html).toContain('dir="rtl"');
    expect(html).toContain("&lt;b&gt;x&lt;/b&gt;");
    expect(html).not.toContain("<b>x</b>");
  });
});
