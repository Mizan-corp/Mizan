// Batches and expiry (FEFO): this module's API calls (paths under /modules/batches), used by its screens and widgets.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface ExpiringBatch {
  id: string; product_id: string; product_name: string; warehouse_id: string; warehouse_name: string;
  batch_number: string; expiry_date: string; qty: string; status: string; days_left: number;
}

/** Expired batches with stock, then those expiring within `days`, soonest first. */
export function useExpiringBatches(warehouseId: string | null | undefined, days = 90) {
  return useQuery({
    queryKey: ["batches", "expiring", warehouseId, days],
    queryFn: () => api.get<ExpiringBatch[]>("/modules/batches/expiring", { days, ...(warehouseId ? { warehouse_id: warehouseId } : {}) }),
  });
}
