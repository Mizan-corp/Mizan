// The screen builder's API (ADR-006 phase 5): /settings/designer, /settings/fields.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { FieldType } from "@app/framework/forms";

export interface DesignerOverview {
  roles: { id: string; code: string; name: string; standard: boolean; custom: boolean }[];
  forms: { record: string; label: string; custom: boolean }[];
  field_records: string[];
}

export interface MenuItemDraft { screen: string; label?: string; icon?: string }
export interface MenuGroupDraft { id: string; label: string; items: MenuItemDraft[] }
export interface DashboardEntry { id: string; size: "s" | "m" | "l" | null }
export interface RoleLayoutDraft { home: string | null; menu: MenuGroupDraft[]; dashboard: DashboardEntry[] }

export interface CatalogueScreen { id: string; label: string; path: string; icon: string | null; module: string; allowed: boolean }
export interface CatalogueWidget { id: string; label: string; size: "s" | "m" | "l"; module: string; allowed: boolean }
export interface RoleLayoutResponse {
  role: { id: string; code: string; name: string; standard: boolean };
  custom: boolean;
  layout: { home: string | null; menu: MenuGroupDraft[]; dashboard: (DashboardEntry | string)[] };
  screens: CatalogueScreen[];
  widgets: CatalogueWidget[];
}

export interface FieldDefinition {
  key: string;
  label?: string;
  label_en?: string;
  type: FieldType;
  required?: boolean;
  searchable?: boolean;
  options?: string[];
  readonly?: boolean;
  hidden: boolean;
  source: string; // "workspace", or the variant that declares it ("pharmacy.pharmacy")
}

export const RECORD_LABELS: Record<string, string> = {
  product: "المنتج",
  sale: "الفاتورة",
  sale_line: "بند الفاتورة",
  customer: "العميل",
  supplier: "المورد",
  purchase_line: "بند أمر الشراء",
};

export const SIZE_LABELS: Record<string, string> = { s: "صغير", m: "متوسط", l: "بعرض الصفحة" };

export const TYPE_LABELS: Record<FieldType, string> = {
  text: "نص",
  number: "رقم",
  date: "تاريخ",
  boolean: "نعم / لا",
  select: "اختيار من قائمة",
};

export function useDesignerOverview() {
  return useQuery({ queryKey: ["designer"], queryFn: () => api.get<DesignerOverview>("/settings/designer") });
}

/** Move an item one place up (-1) or down (+1) in a list, returning a new list. */
export function move<T>(list: T[], index: number, delta: -1 | 1): T[] {
  const to = index + delta;
  if (to < 0 || to >= list.length) return list;
  const next = [...list];
  [next[index], next[to]] = [next[to], next[index]];
  return next;
}

/** An id for a new menu group or form section (lowercase letters, digits and _). */
export function newId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}`;
}
