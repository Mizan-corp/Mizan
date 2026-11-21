// Reporting engine: this module's API calls (paths under /reports), used by its screens and widgets.
// Money comes as decimal strings ("1234.50", REP-15).
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type MoneyStr = string;

export interface DailySales { date: string; total_sales: MoneyStr; total_items: number | string; invoice_count: number }
export interface MonthlySales { total_sales?: MoneyStr; invoice_count?: number }
export interface TrendDay { date: string; total_sales: MoneyStr; invoice_count: number }

export interface ProfitReport {
  from_date: string; to_date: string; source: "ledger" | "operations"; ledger_start: string | null;
  total_revenue: MoneyStr; total_returns: MoneyStr; net_revenue: MoneyStr; total_cogs: MoneyStr; gross_profit: MoneyStr;
  total_expenses: MoneyStr; other_income: MoneyStr; net_profit: MoneyStr; gross_margin: number; net_margin: number;
  expenses_detail: { note: string; amount: MoneyStr }[];
}

export interface CashFlowLine { key: string; in: MoneyStr; out: MoneyStr; net: MoneyStr }
export interface CashFlowAccount { code: string; name: string; kind: string; opening: MoneyStr; in: MoneyStr; out: MoneyStr; closing: MoneyStr }
export interface CashFlowReport {
  from_date: string; to_date: string; source: "ledger" | "operations"; ledger_start: string | null;
  lines: CashFlowLine[]; total_in: MoneyStr; total_out: MoneyStr; net_cash_flow: MoneyStr;
  opening_balance: MoneyStr | null; closing_balance: MoneyStr | null; accounts: CashFlowAccount[];
  sales_by_method?: Record<string, MoneyStr>;
}

export type Bucket = "0-30" | "30-60" | "60-90" | "90+";
export interface AgingParty {
  id: string; name: string; total_debt: MoneyStr; buckets: Record<Bucket, MoneyStr>;
  invoices?: { invoice: string; date: string; total: MoneyStr; remaining: MoneyStr; bucket: Bucket }[];
}
export interface AgingSide { items: AgingParty[]; totals: Record<Bucket | "total", MoneyStr>; count: number; included?: boolean }
export interface AgingReport { as_of: string; customers: AgingSide; suppliers: AgingSide }

export interface DailyItems {
  date: string;
  items: { product_id: string; name: string; unit: string | null; price: MoneyStr; qty: number; total: MoneyStr; returns: MoneyStr }[];
  expenses: { note: string; total: MoneyStr }[];
}
export interface PeriodRow { period: string; income: MoneyStr; returns: MoneyStr; expenses: MoneyStr; net: MoneyStr }

export interface Overview {
  period: { from: string; to: string };
  summary: {
    total_revenue: MoneyStr; total_profit: MoneyStr; profit_margin: number; total_stock_cost: MoneyStr; total_stock_retail: MoneyStr;
    total_customer_debt: MoneyStr; total_supplier_debt: MoneyStr; total_cash_in_drawers: MoneyStr; total_safes_balance: MoneyStr;
    net_capital: MoneyStr;
  };
  branches: { id: string; name: string; invoice_count: number; revenue: MoneyStr; gross_profit: MoneyStr; credit_sales: MoneyStr; cash_sales: MoneyStr }[];
  stock_per_warehouse: { id: string; name: string; stock_cost_value: MoneyStr; stock_retail_value: MoneyStr; total_units: number }[];
  low_stock: { name: string; unit: string | null; reorder_point: number; total_qty: number }[];
  customer_debts: { id: string; name: string; phone: string | null; balance_due: MoneyStr }[];
  supplier_debts: { id: string; name: string; phone: string | null; balance: MoneyStr }[];
  cash_drawers: { name: string; cashier: string | null; initial_amount: MoneyStr; net_movement: MoneyStr; expected: MoneyStr }[];
}

export function useDailySales() {
  return useQuery({ queryKey: ["report", "daily"], queryFn: () => api.get<DailySales>("/reports/sales/daily") });
}

export function useMonthlySales() {
  const now = new Date();
  return useQuery({
    queryKey: ["report", "monthly", now.getFullYear(), now.getMonth() + 1],
    queryFn: () => api.get<MonthlySales>("/reports/sales/monthly", { year: now.getFullYear(), month: now.getMonth() + 1 }),
  });
}

/** Net sales per day, oldest first, today last. */
export function useSalesTrend(days = 14) {
  return useQuery({ queryKey: ["report", "trend", days], queryFn: () => api.get<TrendDay[]>("/reports/sales/trend", { days }) });
}
