// Purchases: logic the screens share (statuses, the goods-receipt form, order lines), free of React
// so it is tested on its own.
import Decimal from "decimal.js";
import { D } from "@/lib/format";
import { parseNumber } from "@activities/general/modules/inventory/lib";
import type { POStatus, PurchaseLine, Suggestion } from "./api";

export const STATUS: Record<POStatus, { label: string; tone: "muted" | "success" | "warning" | "danger" | "brand" }> = {
  draft: { label: "مسودة", tone: "brand" },
  partial: { label: "مستلم جزئياً", tone: "warning" },
  received: { label: "مستلم", tone: "success" },
  cancelled: { label: "ملغي", tone: "danger" },
};

/** What can be done with an order in its state (the server decides; this hides what it refuses). */
export function actionsFor(status: POStatus) {
  return {
    edit: status === "draft",
    cancel: status === "draft",
    remove: status === "draft",
    receive: status === "draft" || status === "partial",
    close: status === "partial",
    returnGoods: status === "partial" || status === "received",
  };
}

/** One line of the goods-receipt form: what arrives now of an order line. */
export interface ReceiveRow {
  item_id: string;
  product_name: string;
  unit: string;
  remaining: string;
  qty: string;
  unit_cost: string;
  batch_number: string;
  expiry_date: string;
}

/** The form's starting point: every line with something left, all of it arriving at the order's cost. */
export function receiveRows(lines: PurchaseLine[]): ReceiveRow[] {
  return lines
    .filter((l) => D(l.qty_remaining).gt(0))
    .map((l) => ({
      item_id: l.id, product_name: l.product_name, unit: l.unit, remaining: String(D(l.qty_remaining)),
      qty: String(D(l.qty_remaining)), unit_cost: String(D(l.unit_cost)), batch_number: "", expiry_date: "",
    }));
}

/** Problems that stop the receipt (Arabic), one per line at most, plus "nothing arrives". */
export function receiveIssues(rows: ReceiveRow[]): string[] {
  const out: string[] = [];
  let any = false;
  for (const r of rows) {
    const q = r.qty.trim() === "" ? D(0) : parseNumber(r.qty);
    if (q === null) { out.push(`كمية «${r.product_name}» غير صحيحة`); continue; }
    if (q.gt(D(r.remaining))) { out.push(`كمية «${r.product_name}» أكبر من المتبقي (${D(r.remaining).toString()})`); continue; }
    if (q.gt(0)) {
      any = true;
      if (parseNumber(r.unit_cost, 2) === null) out.push(`تكلفة «${r.product_name}» غير صحيحة`);
    }
  }
  if (!any && !out.length) out.push("أدخل كمية صنف واحد على الأقل");
  return out;
}

/** The receipt's lines for the server: every line named by its id (0 for what doesn't arrive now). */
export function receivePayload(rows: ReceiveRow[]) {
  return rows.map((r) => {
    const q = r.qty.trim() === "" ? D(0) : parseNumber(r.qty) ?? D(0);
    if (q.lte(0)) return { item_id: r.item_id, qty_received: "0" };
    return {
      item_id: r.item_id,
      qty_received: q.toString(),
      unit_cost: (parseNumber(r.unit_cost, 2) ?? D(0)).toString(),
      batch_number: r.batch_number.trim() || null,
      expiry_date: r.expiry_date || null,
    };
  });
}

/** The value of what arrives now (before VAT is worked out by the server). */
export function receiveTotal(rows: ReceiveRow[]): Decimal {
  return rows.reduce((sum, r) => {
    const q = parseNumber(r.qty) ?? D(0);
    const c = parseNumber(r.unit_cost, 2) ?? D(0);
    return sum.plus(q.times(c));
  }, D(0));
}

/** An order line in the order form. */
export interface OrderLine { product_id: string; name: string; qty: string; unit_cost: string }

export function orderTotal(lines: OrderLine[]): Decimal {
  return lines.reduce((s, l) => s.plus((parseNumber(l.qty) ?? D(0)).times(parseNumber(l.unit_cost, 2) ?? D(0))), D(0));
}

export function orderIssues(lines: OrderLine[]): string[] {
  if (!lines.length) return ["أضف صنفاً واحداً على الأقل"];
  const out: string[] = [];
  for (const l of lines) {
    const q = parseNumber(l.qty);
    if (!q || q.lte(0)) out.push(`كمية «${l.name}»`);
    if (parseNumber(l.unit_cost, 2) === null) out.push(`تكلفة «${l.name}»`);
  }
  return out;
}

/** A purchase suggestion as an order line: what brings the stock back above its reorder point (the
 * product's reorder quantity when it has one). */
export function suggestionLine(s: Suggestion): OrderLine {
  const stock = D(s.total_stock);
  const point = D(s.reorder_point);
  const wanted = D(s.reorder_qty).gt(0) ? D(s.reorder_qty) : Decimal.max(point.times(2).minus(stock), D(1));
  return { product_id: s.id, name: s.name, qty: wanted.toDecimalPlaces(3).toString(), unit_cost: String(D(s.cost_price ?? 0)) };
}
