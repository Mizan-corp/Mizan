// Inventory & Supply: this module's API shapes and calls, used by its screens and widgets.
// Quantities and money come as strings (Decimal on the server); dates are ISO strings.
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

export interface Category { id: string; name: string; code: string | null }
export interface Subcategory { id: string; name: string; code: string | null; category_id: string }

export interface WarehouseRow {
  id: string;
  code: string;
  name: string;
  warehouse_type: "warehouse" | "showroom" | string;
  is_active?: boolean;
}

export interface ProductRow {
  id: string;
  name: string;
  code: string | null;
  barcode: string | null;
  unit: string;
  retail_price: string;
  wholesale_price: string;
  /** null for a user who may not see costs. */
  cost_price: string | null;
  avg_cost?: string | null;
  company: string | null;
  is_active: boolean;
  subcategory_id: string | null;
  image_url?: string | null;
  stock_status?: string;
  reorder_level?: number;
  current_qty?: string;
}

export interface ProductBarcode { id: string; barcode: string; is_primary: boolean; created_at: string }
export interface ProductDetail extends ProductRow { barcodes: ProductBarcode[] }

export interface Paged<T> { items: T[]; total: number; page: number; pages: number }

export interface MovementRow {
  id: string;
  product_id: string;
  product_name?: string | null;
  warehouse_id: string;
  warehouse_name?: string | null;
  movement_type: string;
  qty: string;
  unit_cost: string;
  ref_type: string | null;
  note: string | null;
  created_by_name?: string | null;
  created_at: string;
}

export interface CollectionItem {
  product_id: string;
  qty: string;
  product_name?: string;
  unit?: string;
  retail_price?: string;
  cost_price?: string | null;
  /** The average cost (ADR-014 D5), what stock is valued at; null without the cost permission. */
  avg_cost?: string | null;
}
export interface Collection {
  id: string;
  name: string;
  description: string | null;
  retail_price: string;
  wholesale_price: string;
  items: CollectionItem[] | null;
}

export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: () => api.get<Category[]>("/categories") });
}

export function useSubcategories() {
  return useQuery({ queryKey: ["subcategories"], queryFn: () => api.get<Subcategory[]>("/subcategories") });
}

/** The active warehouses (every screen's branch pickers). */
export function useWarehouses() {
  return useQuery({ queryKey: ["warehouses"], queryFn: () => api.get<WarehouseRow[]>("/stock/warehouses") });
}
