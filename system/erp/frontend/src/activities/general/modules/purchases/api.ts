// Purchases & Procurement: the shapes of this module's API (paths under /purchases), used by its
// screens. Money and quantities come as strings (Decimal on the server); dates as ISO strings.

export type POStatus = "draft" | "partial" | "received" | "cancelled";

export interface PurchaseRow {
  id: string;
  po_number: string;
  status: POStatus;
  supplier_id: string | null;
  supplier_name: string | null;
  warehouse_id: string;
  warehouse_name: string | null;
  created_by_name?: string | null;
  amount_paid: string | null;
  /** What was received (with VAT) once received in whole or in part; what was ordered before. */
  total: string | null;
  tax_amount?: string | null;
  notes: string | null;
  created_at: string;
  received_at: string | null;
}

export interface PurchaseLine {
  id: string;
  product_id: string;
  product_name: string;
  sku: string | null;
  unit: string;
  qty_ordered: string;
  qty_received: string;
  qty_remaining: string;
  unit_cost: string;
  current_cost: string;
  notes: string | null;
}

export interface ReceiptLine {
  id: string;
  product_id: string;
  product_name: string;
  qty: string;
  unit_cost: string;
  batch_number: string | null;
  expiry_date: string | null;
  tax_amount: string;
  net_amount: string | null;
}

export interface Receipt {
  id: string;
  receipt_number: string;
  seq: number;
  total: string;
  tax_amount: string;
  amount_paid: string;
  safe_name: string | null;
  wallet_name: string | null;
  notes: string | null;
  created_by_name: string | null;
  created_at: string;
  items: ReceiptLine[];
}

export interface SupplierMove {
  id: string;
  type: "debit" | "credit";
  amount: string;
  reference_doc: string | null;
  notes: string | null;
  safe_name: string | null;
  wallet_name: string | null;
  created_at: string;
}

export interface ReturnRow {
  id: string;
  return_number: string;
  total: string;
  tax_amount: string;
  refund_amount: string;
  notes: string | null;
  created_by_name: string | null;
  created_at: string;
}

export interface PurchaseDetail extends PurchaseRow {
  ordered_total: string;
  prices_include_vat: boolean | null;
  invoice_image_url?: string | null;
  items: PurchaseLine[];
  receipts: Receipt[];
  payments: SupplierMove[];
  returns: ReturnRow[];
}

export interface Returnable {
  product_id: string;
  product_name: string | null;
  unit_cost: string;
  unit_tax?: string;
  received: string;
  returned: string;
  returnable: string;
}

export interface Suggestion {
  id: string;
  name: string;
  sku: string | null;
  cost_price: string | null;
  reorder_point: string;
  reorder_qty: string;
  total_stock: string;
  unit: string;
}

export interface Supplier { id: string; name: string }
