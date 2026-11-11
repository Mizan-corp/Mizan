// Point of Sale (POS): this module's API calls, used by its screens and widgets.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

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
