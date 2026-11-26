// Point of Sale (POS): this module's API calls, used by its screens and widgets.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { type PosSettings, posSettings } from "./lib";

export interface CurrentShift { id: string; started_at: string }
export interface SaleRow { id: string; invoice_number: string; customer_name: string | null; total: string; status: string; created_at: string }

export function useCurrentShift(warehouseId: string | null | undefined) {
  return useQuery({
    queryKey: ["shift", "dash", warehouseId],
    queryFn: () => api.get<CurrentShift | null>("/shifts/current", { warehouse_id: warehouseId! }),
    enabled: !!warehouseId,
    retry: false,
  });
}

export function useRecentSales(limit = 7) {
  return useQuery({
    queryKey: ["dash", "recent", limit],
    queryFn: async () => {
      const data = await api.get<SaleRow[] | { items: SaleRow[] }>("/sales", { page: 1, page_size: limit });
      return Array.isArray(data) ? data : data.items ?? [];
    },
  });
}

/** The workspace's POS settings (module centre), with the manifest's defaults until loaded or
 * when they can't be read. */
export function usePosSettings(): PosSettings & { loaded: boolean } {
  const q = useQuery({
    queryKey: ["module-settings", "pos"],
    queryFn: () => api.get<{ values: Record<string, unknown> }>("/modules/pos/settings"),
    staleTime: 60_000,
    retry: false,
  });
  return { ...posSettings(q.data?.values), loaded: q.isSuccess };
}
