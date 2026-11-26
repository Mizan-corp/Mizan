// Inventory: logic the screens share, kept free of React so it is tested on its own.
import Decimal from "decimal.js";
import { D } from "@/lib/format";
import type { Category, CollectionItem, Subcategory } from "./api";

const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";
const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/** A quantity or amount typed by hand: Arabic or Persian digits, "٫" or "," as the decimal point.
 * null: not a number, negative, or more decimals than `places`. "" is null too (nothing typed). */
export function parseNumber(raw: string | null | undefined, places = 3): Decimal | null {
  let s = (raw ?? "").trim();
  if (!s) return null;
  s = s.replace(/[٠-٩]/g, (c) => String(ARABIC_DIGITS.indexOf(c))).replace(/[۰-۹]/g, (c) => String(PERSIAN_DIGITS.indexOf(c)));
  s = s.replace(/٬/g, "").replace(/\s/g, "").replace(/٫/g, ".");
  if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(s)) s = s.replace(/,/g, "");
  else s = s.replace(/,/g, ".");
  if (!/^\d+(\.\d+)?$/.test(s)) return null;
  const v = D(s);
  return v.decimalPlaces() > places ? null : v;
}

/** How each stock movement reads, and whether it brings stock in. */
export const MOVEMENT_LABEL: Record<string, { label: string; inbound: boolean }> = {
  opening_stock: { label: "رصيد افتتاحي", inbound: true },
  purchase: { label: "استلام مشتريات", inbound: true },
  return_in: { label: "مرتجع مبيعات", inbound: true },
  adjustment_in: { label: "تسوية بالزيادة", inbound: true },
  transfer_in: { label: "تحويل وارد", inbound: true },
  sale: { label: "بيع", inbound: false },
  damage: { label: "تالف", inbound: false },
  adjustment_out: { label: "تسوية بالنقص", inbound: false },
  transfer_out: { label: "تحويل صادر", inbound: false },
  return_out: { label: "مرتجع للمورد", inbound: false },
};

export function movementLabel(type: string): { label: string; inbound: boolean } {
  return MOVEMENT_LABEL[type] ?? { label: type, inbound: true };
}

/** The signed quantity of a movement: positive in, negative out. */
export function signedQty(type: string, qty: string | number): Decimal {
  const q = D(qty);
  return movementLabel(type).inbound ? q : q.neg();
}

/** Movements entered by hand (the server refuses the others): what each means for the books. */
export const HAND_MOVEMENTS = [
  { type: "adjustment_in", label: "تسوية بالزيادة", hint: "وُجدت كمية زائدة في الجرد: تدخل المخزن وتُسجَّل ربح تسوية." },
  { type: "adjustment_out", label: "تسوية بالنقص", hint: "عجز في الجرد: تخرج من المخزن وتُسجَّل خسارة مخزون." },
  { type: "damage", label: "تالف", hint: "بضاعة تالفة أو منتهية: تخرج من المخزن وتُسجَّل خسارة مخزون." },
  { type: "opening_stock", label: "رصيد افتتاحي", hint: "ما كان في المخزن عند بدء العمل على ميزان (صلاحية الرصيد الافتتاحي)." },
] as const;

export type HandMovement = (typeof HAND_MOVEMENTS)[number]["type"];

/** What a hand movement still lacks before it can be sent (Arabic, empty when ready). */
export function handMovementIssues(m: { type: HandMovement; product_id: string; warehouse_id: string; qty: string; unit_cost: string; note: string }): string[] {
  const out: string[] = [];
  if (!m.product_id) out.push("اختر الصنف");
  if (!m.warehouse_id) out.push("اختر المخزن");
  const q = parseNumber(m.qty);
  if (!q || q.lte(0)) out.push("أدخل كمية أكبر من صفر");
  if (m.unit_cost.trim() && parseNumber(m.unit_cost, 2) === null) out.push("تكلفة الوحدة غير صحيحة");
  if ((m.type === "damage" || m.type === "adjustment_out") && !m.note.trim()) out.push("اكتب السبب");
  return out;
}

export interface CategoryGroup { category: Category; subcategories: Subcategory[] }

/** Categories in order, each with its subcategories (for grouped pickers and the categories screen). */
export function groupSubcategories(categories: Category[], subcategories: Subcategory[]): CategoryGroup[] {
  return categories.map((category) => ({
    category,
    subcategories: subcategories.filter((s) => s.category_id === category.id),
  }));
}

/** What one collection's items cost (each at its average cost, as stock is valued, × its quantity);
 *  null when a cost is hidden from the user (or unknown), so no partial figure is shown. */
export function componentsCost(items: CollectionItem[] | null | undefined): Decimal | null {
  let sum = D(0);
  for (const i of items ?? []) {
    if (i.avg_cost === null || i.avg_cost === undefined) return null;
    sum = sum.plus(D(i.qty).times(D(i.avg_cost)));
  }
  return sum;
}

export const WAREHOUSE_TYPE_LABEL: Record<string, string> = { warehouse: "مخزن", showroom: "معرض / فرع بيع" };

/** A stored picture's address for an <img>: relative uploads are served by the API. */
export function imageSrc(url: string | null | undefined, apiUrl: (path: string) => string): string | null {
  if (!url) return null;
  return /^https?:\/\//.test(url) ? url : apiUrl(url);
}
