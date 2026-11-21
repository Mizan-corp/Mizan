// Sales & Invoicing: the types of the sales API (historical URLs under /sales), used by its screens.

export interface SaleItemRow {
  id?: string;
  product_id: string;
  product_name: string;
  qty: number | string;
  unit_price: string | number;
  discount: string | number;
  returned_qty?: number;
}

export interface SaleRow {
  id: string;
  invoice_number: string;
  total: string;
  net_total: string;
  paid_amount: string | null;
  status: string;
  is_credit: boolean;
  created_at: string;
  customer_id: string | null;
  customer_name: string | null;
  created_by_name?: string | null;
  warehouse_id: string;
  payment_method: string | null;
  wallet_id?: string | null;
  sale_mode: string;
  notes?: string | null;
  discount_amount?: string | number;
  return_of?: string | null;
  returns_total?: string | number | null;
  /** VAT stored on the document (ADR-014 D6). */
  tax_amount?: string | number | null;
  items?: SaleItemRow[];
}

export interface SaleReturnRef { id: string; invoice_number: string; net_total: number; created_at: string | null }

export interface SaleDetail extends SaleRow {
  items?: SaleItemRow[];
  returns?: SaleReturnRef[];
  return_of_number?: string | null;
  remaining?: number;
}

/** GET /sales/page: one page of a filter, with the number of documents it matches. */
export interface SalesPage { items: SaleRow[]; total: number; page: number; page_size: number }

/** GET /sales/summary: values net of VAT, returns taken off (as the reports count them). */
export interface SalesSummary {
  net_sales: string;
  gross_sales: string;
  returns_total: string;
  tax_total: string;
  outstanding: string;
  invoice_count: number;
  returns_count: number;
  cancelled_count: number;
  quotation_count: number;
  draft_count: number;
}

/** Where a confirmed quotation's money goes (POST /sales/{id}/confirm-quotation). */
export type Destination = "drawer" | "safe" | "wallet" | "credit";
