// Reporting engine: this module's API calls (paths under /reports), used by its screens and widgets.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface DailySales { date: string; total_sales: number | string; total_items: number | string; invoice_count: number }
export interface MonthlySales { total_sales?: string | number; invoice_count?: number }
export interface TrendDay { date: string; total_sales: number | string; invoice_count: number }

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
