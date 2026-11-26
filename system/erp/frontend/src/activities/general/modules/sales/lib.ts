// The sales screen's rules, kept apart from the screen so they are tested: a document's status in
// words, which actions a user may take on it (their effective permissions, as the server checks
// them), the body of a quotation's confirmation and of a draft's or quotation's edit.
import { D } from "@/lib/format";
import type { Destination, SaleRow } from "./api";

export type Can = (perm: string) => boolean;

export const PERM = {
  /** Making and confirming drafts: the sales screen or the POS. */
  draft: "sales|pos",
  /** Making, editing and confirming quotations. */
  quotation: "quotations|sales",
  cancel: "sales:cancel",
  return: "sales:return",
  /** Sending the invoice by email. */
  email: "sales",
  /** The Excel export of the sales (the reports module's). */
  export: "reports",
  overridePrice: "sales:override_price",
} as const;

export const fullyReturned = (s: Pick<SaleRow, "status" | "returns_total" | "net_total">): boolean =>
  s.status === "confirmed" && D(s.returns_total ?? 0).gt(0) && D(s.returns_total ?? 0).gte(D(s.net_total ?? 0));

export function statusLabel(s: Pick<SaleRow, "status" | "returns_total" | "net_total" | "is_credit">): string {
  if (s.status === "cancelled") return "ملغاة";
  if (s.status === "quotation") return "عرض سعر";
  if (s.status === "draft") return "مسودة";
  if (s.status === "returned") return "مستند مرتجع";
  if (fullyReturned(s)) return "مرتجعة بالكامل";
  if (D(s.returns_total ?? 0).gt(0)) return "مرتجعة جزئياً";
  return s.is_credit ? "آجل" : "مكتملة";
}

/** How a document was paid; a quotation isn't paid until it is confirmed. */
export function paymentLabel(s: Pick<SaleRow, "payment_method" | "is_credit"> & { status?: string }): string {
  if (s.status === "quotation") return "—";
  if (s.is_credit) return "آجل";
  switch (s.payment_method) {
    case "cash": return "نقدي";
    case "wallet": return "محفظة";
    case "bank": return "تحويل بنكي";
    case "cheque": return "شيك";
    case "credit": return "آجل";
    default: return "—";
  }
}

export interface SaleActions {
  confirm: boolean;
  edit: boolean;
  remove: boolean;
  cancel: boolean;
  returnSale: boolean;
  email: boolean;
}

/** What the user may do with a document: shown only when the server would allow it. */
export function saleActions(s: Pick<SaleRow, "status" | "returns_total" | "net_total">, can: Can): SaleActions {
  const open = s.status === "draft" ? can(PERM.draft) : s.status === "quotation" ? can(PERM.quotation) : false;
  const confirmed = s.status === "confirmed";
  return {
    confirm: open,
    edit: open,
    remove: open,
    cancel: confirmed && D(s.returns_total ?? 0).isZero() && can(PERM.cancel),
    returnSale: confirmed && !fullyReturned(s) && can(PERM.return),
    email: (confirmed || s.status === "quotation") && can(PERM.email),
  };
}

/** The body of POST /sales/{id}/confirm-quotation. `source` is PaySourceSelect's value
 * ("safe:<id>" or "wallet:<id>") when the money goes into a safe or a wallet. */
export function confirmBody(destination: Destination | "source", source = ""): {
  destination: Destination; safe_id?: string; wallet_id?: string;
} {
  if (destination !== "source") return { destination };
  const [kind, id] = source.split(":");
  if (kind === "safe" && id) return { destination: "safe", safe_id: id };
  if (kind === "wallet" && id) return { destination: "wallet", wallet_id: id };
  throw new Error("اختر الخزنة أو المحفظة");
}

export interface EditLine {
  product_id: string;
  product_name: string;
  qty: string;
  /** The price shown; sent only when the user may sell at another price. */
  unit_price: string;
  discount: string;
}

/** Valid quantity, price and discount of a line (Latin digits). */
export function lineIssue(l: EditLine): string | null {
  const q = Number(l.qty), p = Number(l.unit_price), d = Number(l.discount || 0);
  if (!Number.isFinite(q) || q <= 0) return `كمية «${l.product_name}» غير صحيحة`;
  if (!Number.isFinite(p) || p < 0) return `سعر «${l.product_name}» غير صحيح`;
  if (!Number.isFinite(d) || d < 0) return `خصم «${l.product_name}» غير صحيح`;
  if (D(d).gt(D(q).times(p))) return `خصم «${l.product_name}» أكبر من قيمة البند`;
  return null;
}

/** The document's value before VAT is worked out (the server recomputes it on saving). */
export function editTotal(lines: EditLine[], discount: string): string {
  const gross = lines.reduce((s, l) => s.plus(D(Number(l.qty) || 0).times(Number(l.unit_price) || 0)).minus(Number(l.discount) || 0), D(0));
  return gross.minus(Number(discount) || 0).toFixed(2);
}

/** The body of PUT /sales/{id}. Without the right to another price, lines go without one and
 * the server prices them at the product's price now. */
export function editBody(form: { lines: EditLine[]; discount: string; notes: string; customer_id: string }, overridePrice: boolean) {
  return {
    items: form.lines.map((l) => ({
      product_id: l.product_id,
      qty: l.qty,
      discount: l.discount || "0",
      ...(overridePrice ? { unit_price: l.unit_price } : {}),
    })),
    discount_amount: form.discount || "0",
    notes: form.notes.trim() || null,
    customer_id: form.customer_id || null,
  };
}

/** The quantities typed for a partial return, those above zero. */
export function returnItems(qty: Record<string, string>): { product_id: string; qty: number }[] {
  return Object.entries(qty)
    .map(([product_id, q]) => ({ product_id, qty: Number(q) }))
    .filter((i) => Number.isFinite(i.qty) && i.qty > 0);
}

export const pagesOf = (total: number, pageSize: number): number => Math.max(1, Math.ceil(total / pageSize));
