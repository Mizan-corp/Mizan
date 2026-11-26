// The point of sale's and the shifts screen's rules, kept apart from the screens so they are
// tested: the workspace's POS settings, a cart line's price (the product's, or another one for
// those allowed), whether a sale can be paid without a shift, and the drawer's rows.
import type Decimal from "decimal.js";
import { D } from "@/lib/format";

export type Can = (perm: string) => boolean;

// ── Settings (manifest settings_schema; the server enforces the first two) ────────────────────

export interface PosSettings {
  requireActiveShift: boolean;
  allowPriceOverride: boolean;
  autoPrintReceipt: boolean;
  enableQuickNumpad: boolean;
}

const on = (v: unknown, fallback: boolean): boolean => {
  if (v === undefined || v === null || v === "") return fallback;
  if (typeof v === "string") return ["1", "true", "yes", "on"].includes(v.trim().toLowerCase());
  return Boolean(v);
};

/** The values of GET /modules/pos/settings, with the manifest's defaults. */
export function posSettings(values?: Record<string, unknown> | null): PosSettings {
  const v = values ?? {};
  return {
    requireActiveShift: on(v.require_active_shift, true),
    allowPriceOverride: on(v.allow_price_override, false),
    autoPrintReceipt: on(v.auto_print_receipt, false),
    enableQuickNumpad: on(v.enable_quick_numpad, true),
  };
}

/** Another price than the product's: the setting is on and the user holds the permission (the
 * server checks the same, SAL-1). */
export const canOverridePrice = (s: Pick<PosSettings, "allowPriceOverride">, can: Can): boolean =>
  s.allowPriceOverride && can("sales:override_price");

// ── Cart lines ────────────────────────────────────────────────────────────────────────────────

export interface PricedProduct { retail_price: string; wholesale_price: string }
export interface Line<P extends PricedProduct = PricedProduct> { product: P; qty: number; discount: string; price?: string }

/** The product's price: wholesale in wholesale mode when it has one, else retail. */
export function listedPrice(p: PricedProduct, mode: "retail" | "wholesale"): Decimal {
  return mode === "wholesale" && D(p.wholesale_price || "0").gt(0) ? D(p.wholesale_price) : D(p.retail_price || "0");
}

/** The price a line is sold at: the one typed (when allowed) or the product's. */
export function linePrice(l: Line, mode: "retail" | "wholesale", override: boolean): Decimal {
  if (override && l.price !== undefined && l.price !== "" && Number.isFinite(Number(l.price)) && Number(l.price) >= 0) {
    return D(l.price);
  }
  return listedPrice(l.product, mode);
}

export const lineTotal = (l: Line, mode: "retail" | "wholesale", override: boolean): Decimal =>
  linePrice(l, mode, override).times(l.qty).minus(D(l.discount || "0"));

/** Whether a line is sold at another price than the product's. */
export const priceChanged = (l: Line, mode: "retail" | "wholesale", override: boolean): boolean =>
  !linePrice(l, mode, override).eq(listedPrice(l.product, mode));

// ── Paying without a shift (require_active_shift) ─────────────────────────────────────────────

export interface PaymentGate { canPay: boolean; cashAllowed: boolean; message: string | null }

export const SHIFT_REQUIRED = "إعدادات نقطة البيع تشترط وردية مفتوحة للبيع — افتح وردية أولاً";
export const CASH_NEEDS_SHIFT = "لا توجد وردية مفتوحة: يُقبل الدفع بالمحفظة أو البنك أو الآجل فقط — النقدي يحتاج وردية";

/** `hasShift` undefined: still loading. Cash always needs the user's open shift in the branch;
 * with require_active_shift on, every sale does. */
export function paymentGate(hasShift: boolean | undefined, requireActiveShift: boolean): PaymentGate {
  if (hasShift === undefined) return { canPay: false, cashAllowed: false, message: null };
  if (hasShift) return { canPay: true, cashAllowed: true, message: null };
  if (requireActiveShift) return { canPay: false, cashAllowed: false, message: SHIFT_REQUIRED };
  return { canPay: true, cashAllowed: false, message: CASH_NEEDS_SHIFT };
}

// ── The drawer ────────────────────────────────────────────────────────────────────────────────

export const TX_LABEL: Record<string, string> = {
  sale: "بيع",
  return: "مرتجع",
  expense: "مصروف",
  deposit: "إيداع",
  withdrawal: "سحب",
  revenue_delivery: "توريد إلى خزنة",
};

export const MANUAL_TYPES = ["deposit", "expense", "withdrawal"] as const;

/** Money into the drawer (+) or out of it (−). */
export const txIn = (type: string): boolean => type === "sale" || type === "deposit";

export interface DrawerTx { id: string; type: string; ref_id: string | null; cancelled_at: string | null }

/** Who approves at the counter (closing with a manager, revenue delivery) and cancels drawer
 * rows: `supervise`, or a manager flag with `shifts` (the server's can_approve). */
export const canApprove = (isManager: boolean, can: Can): boolean => can("supervise") || (isManager && can("shifts"));

/** A row can be cancelled when it was entered by hand, isn't cancelled, its shift is open and the
 * user approves at the counter; sales and returns are changed through their invoice. */
export const canCancelTx = (tx: DrawerTx, shiftOpen: boolean, approver: boolean): boolean =>
  approver && shiftOpen && !tx.ref_id && !tx.cancelled_at && (MANUAL_TYPES as readonly string[]).includes(tx.type);

/** The count against what the drawer should hold: shortage (−), surplus (+) or none. */
export function closeDifference(counted: string, expected: string | number): { value: Decimal; label: string } | null {
  if (counted.trim() === "" || !Number.isFinite(Number(counted))) return null;
  const value = D(counted).minus(D(expected));
  return { value, label: value.isZero() ? "مطابق" : value.lt(0) ? "عجز" : "زيادة" };
}

/** What stays for the next shift: between zero and the count (POS-5). */
export function nextDayIssue(counted: string, keep: string): string | null {
  if (keep.trim() === "") return null;
  const k = Number(keep);
  if (!Number.isFinite(k) || k < 0) return "المبلغ المتروك في الدرج غير صحيح";
  if (Number.isFinite(Number(counted)) && k > Number(counted)) return "المبلغ المتروك أكبر من الرصيد المعدود";
  return null;
}
