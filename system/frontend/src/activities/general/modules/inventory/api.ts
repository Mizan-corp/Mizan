// Inventory & Supply: this module's API calls, used by its screens and widgets.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface LowStockRow { product_id: string; product_name: string; current_qty: number; unit: string }

export function useLowStock(warehouseId: string | null | undefined) {
  return useQuery({
    queryKey: ["dash", "low", warehouseId],
    queryFn: () => api.get<LowStockRow[]>("/stock/low-stock", { warehouse_id: warehouseId! }),
    enabled: !!warehouseId,
  });
}
