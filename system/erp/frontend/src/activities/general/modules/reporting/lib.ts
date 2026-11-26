// Reporting: the screens' logic that isn't drawing (tested in __tests__/lib.test.ts): labels, and
// the rows each report exports or prints. Money arrives as decimal strings and is added up with
// Decimal; the export cells are numbers (two decimals in CSV and print).
import { D } from "@/lib/format";
import { type Cell, SOURCE_LABEL } from "@activities/general/modules/accounting/lib";
import type { AgingSide, Bucket, CashFlowReport, ProfitReport } from "./api";

export const BUCKETS: Bucket[] = ["0-30", "30-60", "60-90", "90+"];
export const BUCKET_LABEL: Record<Bucket, string> = { "0-30": "حتى 30 يوماً", "30-60": "30–60", "60-90": "60–90", "90+": "أكثر من 90" };

/** What moved the money, by the ledger's source (and the documents' names for the same things). */
export const FLOW_LABEL: Record<string, string> = {
  ...SOURCE_LABEL,
  sale: "مبيعات محصلة", sale_return: "مرتجعات مبيعات مدفوعة", customer_payment: "تحصيلات من العملاء",
  purchase: "مشتريات مدفوعة", purchase_return: "مرتجعات مشتريات مستردة", supplier_tx: "مدفوعات الموردين",
  expense: "المصروفات", payroll: "الرواتب", hr_advance: "سلف الموظفين", drawer_tx: "حركات الأدراج اليدوية",
  safe_movement: "إيداعات وسحوبات يدوية بالخزائن", wallet_movement: "تسويات المحافظ", shift: "فروق إغلاق الورديات",
  manual: "قيود يدوية",
};

export const MONEY_KIND: Record<string, string> = { safe: "خزنة / بنك", wallet: "محفظة", drawer: "درج كاشير", default_bank: "بنك افتراضي" };

export const METHOD_LABEL: Record<string, string> = {
  cash: "نقدي", card: "بطاقة", bank: "تحويل بنكي", cheque: "شيك", wallet: "محفظة", credit: "آجل",
};

/** A money string as an export cell. */
export const n = (v: string | number | null | undefined): number => Number(D(v ?? 0).toFixed(2));

export function flowLabel(key: string): string {
  return FLOW_LABEL[key] ?? key;
}

/** The income statement's lines of the profit report, in order. */
export function profitRows(p: ProfitReport): { label: string; amount: string; kind: "line" | "result" }[] {
  return [
    { label: "المبيعات (بدون الضريبة)", amount: p.total_revenue, kind: "line" },
    { label: "مرتجعات المبيعات", amount: D(p.total_returns).neg().toFixed(2), kind: "line" },
    { label: "صافي المبيعات", amount: p.net_revenue, kind: "result" },
    { label: "تكلفة البضاعة المباعة", amount: D(p.total_cogs).neg().toFixed(2), kind: "line" },
    { label: "مجمل الربح", amount: p.gross_profit, kind: "result" },
    ...p.expenses_detail.map((e) => ({ label: e.note, amount: D(e.amount).neg().toFixed(2), kind: "line" as const })),
    ...(D(p.other_income).isZero() ? [] : [{ label: "إيرادات أخرى", amount: p.other_income, kind: "line" as const }]),
    { label: D(p.net_profit).gte(0) ? "صافي الربح" : "صافي الخسارة", amount: p.net_profit, kind: "result" },
  ];
}

export function cashFlowRows(cf: CashFlowReport): Cell[][] {
  const rows: Cell[][] = cf.lines.map((l) => [flowLabel(l.key), n(l.in), n(l.out), n(l.net)]);
  rows.push(["الإجمالي", n(cf.total_in), n(cf.total_out), n(cf.net_cash_flow)]);
  if (cf.opening_balance != null) {
    rows.unshift(["رصيد النقدية أول المدة", null, null, n(cf.opening_balance)]);
    rows.push(["رصيد النقدية آخر المدة", null, null, n(cf.closing_balance)]);
  }
  return rows;
}

export function agingRows(side: AgingSide): Cell[][] {
  const rows: Cell[][] = side.items.map((p) => [p.name, ...BUCKETS.map((b) => n(p.buckets[b])), n(p.total_debt)]);
  rows.push(["الإجمالي", ...BUCKETS.map((b) => n(side.totals[b])), n(side.totals.total)]);
  return rows;
}

/** The share of a bucket in the total, in percent (0 when nothing is owed). */
export function bucketShare(side: AgingSide, b: Bucket): number {
  const total = D(side.totals.total);
  return total.isZero() ? 0 : Number(D(side.totals[b]).div(total).times(100).toFixed(1));
}

/** The first of this month and today, in Egypt (the server's days). */
export function monthToDate(now: Date = new Date()): { from: string; to: string } {
  const to = new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Cairo", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  return { from: `${to.slice(0, 8)}01`, to };
}
