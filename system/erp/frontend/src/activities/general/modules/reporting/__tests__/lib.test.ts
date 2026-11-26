import { describe, expect, it } from "vitest";
import type { AgingSide, CashFlowReport, ProfitReport } from "../api";
import { agingRows, bucketShare, cashFlowRows, flowLabel, monthToDate, profitRows } from "../lib";

const profit: ProfitReport = {
  from_date: "2026-05-01", to_date: "2026-05-31", source: "operations", ledger_start: null, total_revenue: "580.00", total_returns: "100.00",
  net_revenue: "480.00", total_cogs: "300.00", gross_profit: "180.00", total_expenses: "90.00", other_income: "0.00", net_profit: "90.00",
  gross_margin: 37.5, net_margin: 18.8, expenses_detail: [{ note: "إيجار", amount: "50.00" }, { note: "شاي", amount: "40.00" }],
};

describe("profitRows", () => {
  it("lays the profit out as an income statement, costs negative", () => {
    const rows = profitRows(profit);
    expect(rows.map((r) => [r.label, r.amount])).toEqual([
      ["المبيعات (بدون الضريبة)", "580.00"], ["مرتجعات المبيعات", "-100.00"], ["صافي المبيعات", "480.00"],
      ["تكلفة البضاعة المباعة", "-300.00"], ["مجمل الربح", "180.00"], ["إيجار", "-50.00"], ["شاي", "-40.00"], ["صافي الربح", "90.00"],
    ]);
    expect(profitRows({ ...profit, net_profit: "-5.00" }).at(-1)?.label).toBe("صافي الخسارة");
  });
});

describe("cashFlowRows", () => {
  const cf: CashFlowReport = {
    from_date: "", to_date: "", source: "ledger", ledger_start: "2026-01-01", total_in: "680.00", total_out: "110.00", net_cash_flow: "570.00",
    opening_balance: "1000.00", closing_balance: "1570.00", accounts: [],
    lines: [{ key: "sale", in: "680.00", out: "0.00", net: "680.00" }, { key: "drawer_tx", in: "0.00", out: "110.00", net: "-110.00" }],
  };
  it("labels each line and adds the totals and balances", () => {
    expect(cashFlowRows(cf)).toEqual([
      ["رصيد النقدية أول المدة", null, null, 1000], ["مبيعات محصلة", 680, 0, 680], ["حركات الأدراج اليدوية", 0, 110, -110],
      ["الإجمالي", 680, 110, 570], ["رصيد النقدية آخر المدة", null, null, 1570],
    ]);
    expect(cashFlowRows({ ...cf, opening_balance: null, closing_balance: null })).toHaveLength(3);
  });
  it("falls back to the ledger's source labels, then the key", () => {
    expect(flowLabel("clinic_invoice")).toBe("فاتورة عيادة");
    expect(flowLabel("something_new")).toBe("something_new");
  });
});

describe("aging", () => {
  const side: AgingSide = {
    count: 1, items: [{ id: "c", name: "عميل", total_debt: "300.00", buckets: { "0-30": "200.00", "30-60": "100.00", "60-90": "0.00", "90+": "0.00" } }],
    totals: { "0-30": "200.00", "30-60": "100.00", "60-90": "0.00", "90+": "0.00", total: "300.00" },
  };
  it("exports a row per party and the totals", () => {
    expect(agingRows(side)).toEqual([["عميل", 200, 100, 0, 0, 300], ["الإجمالي", 200, 100, 0, 0, 300]]);
  });
  it("gives each bucket's share", () => {
    expect(bucketShare(side, "0-30")).toBe(66.7);
    expect(bucketShare({ ...side, totals: { ...side.totals, total: "0.00" } }, "0-30")).toBe(0);
  });
});

describe("monthToDate", () => {
  it("runs from the first of the month to today in Egypt", () => {
    expect(monthToDate(new Date("2026-03-31T22:30:00Z"))).toEqual({ from: "2026-04-01", to: "2026-04-01" });
  });
});
