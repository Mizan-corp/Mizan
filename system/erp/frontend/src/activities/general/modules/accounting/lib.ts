// Accounting: the screens' logic that isn't drawing (tested in __tests__/lib.test.ts): the manual
// entry's totals and checks (the same rules the server applies when posting, ADR-014 D9), the
// chart as rows, months and fiscal years, source labels, and CSV / print export.
import type Decimal from "decimal.js";
import { D } from "@/lib/format";
import type { AccountNode, AccountType, DraftPayload, PartyType } from "./api";

// ── the manual entry form ────────────────────────────────────────────────────────────────────

export interface LineForm {
  key: string;
  account_id: string;
  debit: string;
  credit: string;
  party_type: PartyType | "";
  party_id: string;
  warehouse_id: string;
}

let seq = 0;
export function emptyLine(): LineForm {
  seq += 1;
  return { key: `l${seq}-${Date.now()}`, account_id: "", debit: "", credit: "", party_type: "", party_id: "", warehouse_id: "" };
}

const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";
const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/** An amount typed by hand: Arabic or Persian digits, "٫" or "," as the decimal point, spaces. null: not a number. */
export function parseAmount(raw: string): Decimal | null {
  let s = (raw ?? "").trim();
  if (!s) return D(0);
  s = s.replace(/[٠-٩]/g, (c) => String(ARABIC_DIGITS.indexOf(c))).replace(/[۰-۹]/g, (c) => String(PERSIAN_DIGITS.indexOf(c)));
  s = s.replace(/٬/g, "").replace(/\s/g, "").replace(/٫/g, ".");
  if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(s)) s = s.replace(/,/g, "");
  else s = s.replace(/,/g, ".");
  if (!/^\d+(\.\d+)?$/.test(s)) return null;
  const v = D(s);
  return v.decimalPlaces() > 2 ? null : v;
}

export interface Totals {
  debit: Decimal;
  credit: Decimal;
  difference: Decimal;
  balanced: boolean;
  /** Lines that carry an amount. */
  filled: number;
}

export function totals(lines: LineForm[]): Totals {
  let debit = D(0);
  let credit = D(0);
  let filled = 0;
  for (const ln of lines) {
    const d = parseAmount(ln.debit) ?? D(0);
    const c = parseAmount(ln.credit) ?? D(0);
    debit = debit.plus(d);
    credit = credit.plus(c);
    if (d.gt(0) || c.gt(0)) filled += 1;
  }
  const difference = debit.minus(credit);
  return { debit, credit, difference, balanced: difference.isZero() && debit.gt(0), filled };
}

/** The account facts the checks need. */
export interface AccountInfo {
  id: string;
  code: string;
  name: string;
  type: AccountType;
  is_group: boolean;
  active: boolean;
  role: string | null;
  /** A safe/wallet/drawer sub-account: "drawer" ones can't be posted by hand. */
  money_kind?: AccountNode["money_kind"];
}

/** The party a line on this account must carry (receivables: a customer, payables: a supplier). */
export function requiredParty(role: string | null | undefined): PartyType | null {
  return role === "receivables" ? "customer" : role === "payables" ? "supplier" : null;
}

/** The parties a line on this account may carry. */
export function allowedParties(role: string | null | undefined): PartyType[] {
  if (role === "receivables") return ["customer"];
  if (role === "payables") return ["supplier"];
  if (role === "employee_advances" || role === "salaries_payable") return ["employee"];
  return [];
}

export const PARTY_LABEL: Record<PartyType, string> = { customer: "العميل", supplier: "المورد", employee: "الموظف" };

/** What stops these lines from being posted, worked out in the browser as the form is filled in
 *  (the server checks again, and also the date: closed month, future, before the opening entry). */
export function lineIssues(lines: LineForm[], accounts: Map<string, AccountInfo>): string[] {
  const out: string[] = [];
  const used = lines.filter((ln) => {
    const d = parseAmount(ln.debit);
    const c = parseAmount(ln.credit);
    return ln.account_id || (d && d.gt(0)) || (c && c.gt(0));
  });
  used.forEach((ln, i) => {
    const where = `السطر ${i + 1}`;
    const d = parseAmount(ln.debit);
    const c = parseAmount(ln.credit);
    if (d === null || c === null) out.push(`${where}: المبلغ غير صحيح (رقم موجب بحد أقصى منزلتين عشريتين)`);
    else if (d.gt(0) && c.gt(0)) out.push(`${where}: السطر إما مدين أو دائن، لا الاثنان معاً`);
    else if (d.isZero() && c.isZero()) out.push(`${where}: أدخل المبلغ مديناً أو دائناً`);
    if (!ln.account_id) {
      out.push(`${where}: اختر الحساب`);
      return;
    }
    const acc = accounts.get(ln.account_id);
    if (!acc) {
      out.push(`${where}: الحساب غير موجود في دليل الحسابات`);
      return;
    }
    const label = `${where} (${acc.code} ${acc.name})`;
    if (acc.is_group) out.push(`${label}: لا يمكن الترحيل على حساب تجميعي، اختر حساباً فرعياً`);
    if (!acc.active) out.push(`${label}: الحساب موقوف`);
    if (acc.role === "inventory") out.push(`${label}: لا يُرحَّل على المخزون يدوياً — استخدم تسوية المخزون`);
    if (acc.money_kind === "drawer") out.push(`${label}: درج الكاشير يتحرك من الوردية فقط`);
    const required = requiredParty(acc.role);
    if (required && !(ln.party_type === required && ln.party_id)) out.push(`${label}: حدد ${PARTY_LABEL[required]}`);
    else if (ln.party_type && !allowedParties(acc.role).includes(ln.party_type)) out.push(`${label}: لا يُذكر ${PARTY_LABEL[ln.party_type]} على هذا الحساب`);
    else if (ln.party_type && !ln.party_id) out.push(`${label}: اختر ${PARTY_LABEL[ln.party_type]}`);
  });
  if (used.length < 2) out.push("القيد يحتاج سطرين على الأقل: مدين ودائن");
  const t = totals(used);
  if (!t.difference.isZero()) out.push(`القيد غير متوازن: الفرق ${t.difference.abs().toFixed(2)}`);
  return out;
}

/** The form as the API takes it: empty lines dropped, amounts as strings with 2 decimals. */
export function toPayload(form: { date: string; memo: string; warehouse_id: string; lines: LineForm[] }): DraftPayload {
  return {
    date: form.date,
    memo: form.memo.trim() || null,
    warehouse_id: form.warehouse_id || null,
    lines: form.lines
      .filter((ln) => ln.account_id && ((parseAmount(ln.debit) ?? D(0)).gt(0) || (parseAmount(ln.credit) ?? D(0)).gt(0)))
      .map((ln) => ({
        account_id: ln.account_id,
        debit: (parseAmount(ln.debit) ?? D(0)).toFixed(2),
        credit: (parseAmount(ln.credit) ?? D(0)).toFixed(2),
        party_type: ln.party_type || null,
        party_id: ln.party_type ? ln.party_id || null : null,
        warehouse_id: ln.warehouse_id || null,
      })),
  };
}

// ── the chart ────────────────────────────────────────────────────────────────────────────────

export interface ChartRow extends AccountInfo {
  name_en: string | null;
  parent_id: string | null;
  level: number;
  hasChildren: boolean;
}

/** The tree as rows in code order, each with its depth; `collapsed` hides the children of those ids. */
export function flattenChart(nodes: AccountNode[], collapsed: Set<string> = new Set(), level = 0): ChartRow[] {
  const out: ChartRow[] = [];
  for (const n of [...nodes].sort((a, b) => a.code.localeCompare(b.code, "en", { numeric: true }))) {
    out.push({ id: n.id, code: n.code, name: n.name, name_en: n.name_en, type: n.type, is_group: n.is_group, active: n.active,
               role: n.role, money_kind: n.money_kind ?? null, parent_id: n.parent_id, level, hasChildren: n.children.length > 0 });
    if (n.children.length && !collapsed.has(n.id)) out.push(...flattenChart(n.children, collapsed, level + 1));
  }
  return out;
}

/** Accounts a manual line may use: active, not groups, not inventory or a drawer (the picker hides the rest). */
export function postable(rows: ChartRow[]): ChartRow[] {
  return rows.filter((r) => !r.is_group && r.active && r.role !== "inventory" && r.money_kind !== "drawer");
}

export const TYPE_LABEL: Record<AccountType, string> = {
  asset: "أصول", liability: "خصوم", equity: "حقوق ملكية", income: "إيرادات", expense: "مصروفات",
};

/** Debit minus credit shown in the account's natural direction (assets and expenses by debit). */
export function natural(type: AccountType, debitMinusCredit: number): number {
  return type === "asset" || type === "expense" ? debitMinusCredit : -debitMinusCredit;
}

// ── months and fiscal years ──────────────────────────────────────────────────────────────────

export const MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];

/** "2026-03" → "مارس 2026" */
export function monthLabel(month: string): string {
  const m = Number(month.slice(5, 7));
  return `${MONTHS_AR[m - 1] ?? month} ${month.slice(0, 4)}`;
}

/** "2026-02" → the month's first and last day (a VAT return is filed per month). */
export function monthRange(month: string): { from: string; to: string } {
  const y = Number(month.slice(0, 4));
  const m = Number(month.slice(5, 7));
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  return { from: `${month}-01`, to: `${month}-${String(last).padStart(2, "0")}` };
}

/** Today in Egypt as YYYY-MM-DD (the posting date the server uses). */
export function todayCairo(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Cairo", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

/** The first and last day of the fiscal year starting in `year` on month `firstMonth`. */
export function fiscalYearRange(year: number, firstMonth: number): { from: string; to: string } {
  const pad = (n: number) => String(n).padStart(2, "0");
  const endYear = firstMonth === 1 ? year : year + 1;
  const endMonth = firstMonth === 1 ? 12 : firstMonth - 1;
  const lastDay = new Date(Date.UTC(endYear, endMonth, 0)).getUTCDate();
  return { from: `${year}-${pad(firstMonth)}-01`, to: `${endYear}-${pad(endMonth)}-${pad(lastDay)}` };
}

/** The fiscal year (by its starting calendar year) that a date falls in. */
export function fiscalYearOf(isoDate: string, firstMonth: number): number {
  const y = Number(isoDate.slice(0, 4));
  const m = Number(isoDate.slice(5, 7));
  return m >= firstMonth ? y : y - 1;
}

export function fiscalYearLabel(year: number, firstMonth: number): string {
  return firstMonth === 1 ? String(year) : `${year}/${year + 1}`;
}

// ── where an entry comes from ────────────────────────────────────────────────────────────────

export const SOURCE_LABEL: Record<string, string> = {
  sale: "فاتورة بيع", sale_return: "مرتجع مبيعات", customer_payment: "تحصيل من عميل", customer_adjustment: "تسوية رصيد عميل",
  drawer_tx: "حركة درج", shift: "فرق إغلاق وردية", expense: "مصروف", safe_movement: "حركة خزنة", wallet_movement: "حركة محفظة",
  purchase: "استلام مشتريات", purchase_return: "مرتجع مشتريات", supplier_tx: "حركة مورد", stock_movement: "تسوية مخزون",
  payroll: "رواتب", hr_advance: "سلفة موظف", clinic_invoice: "فاتورة عيادة", clinic_payment: "دفعة عيادة",
  opening: "قيد افتتاحي", year_end: "إقفال سنة مالية", manual: "قيد يومية يدوي",
};

export function sourceLabel(sourceType: string, event?: string): string {
  const base = SOURCE_LABEL[sourceType] ?? sourceType;
  return event === "reverse" ? `عكس — ${base}` : base;
}

/** The screen a document's entry links to (the app has no per-document addresses yet). */
export const SOURCE_SCREEN: Record<string, string> = {
  sale: "/sales", sale_return: "/sales", customer_payment: "/customers", customer_adjustment: "/customers",
  drawer_tx: "/shifts", shift: "/shifts", expense: "/finance", safe_movement: "/finance", wallet_movement: "/finance",
  purchase: "/purchases", purchase_return: "/purchases", supplier_tx: "/suppliers", stock_movement: "/inventory",
  payroll: "/hr/payroll", hr_advance: "/hr", clinic_invoice: "/clinic", clinic_payment: "/clinic",
  opening: "/accounting/periods", year_end: "/accounting/periods", manual: "/accounting/journal",
};

// ── export ───────────────────────────────────────────────────────────────────────────────────

export type Cell = string | number | null | undefined;

function csvCell(v: Cell): string {
  if (v === null || v === undefined) return "";
  const s = typeof v === "number" ? (Number.isFinite(v) ? v.toFixed(2) : "") : String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** CSV text (numbers with 2 decimals, quoted where needed), lines ending CRLF as Excel expects. */
export function toCsv(columns: string[], rows: Cell[][]): string {
  return [columns, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n");
}

export function downloadCsv(filename: string, columns: string[], rows: Cell[][]): void {
  // The byte-order mark makes Excel read the Arabic as UTF-8.
  const blob = new Blob(["\ufeff" + toCsv(columns, rows)], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

const fmt = new Intl.NumberFormat("ar-EG-u-nu-latn", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** A printable RTL page of one table (opened in a new window and printed). */
export function printHtml(title: string, subtitle: string, columns: string[], rows: Cell[][]): string {
  const cell = (v: Cell) => (typeof v === "number" ? `<td class="n">${fmt.format(v)}</td>` : `<td>${esc(v == null ? "" : String(v))}</td>`);
  return `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>${esc(title)}</title><style>
body{font-family:system-ui,"Segoe UI",Tahoma,sans-serif;margin:24px;color:#111}h1{font-size:18px;margin:0 0 4px}
p{margin:0 0 16px;color:#555;font-size:12px}table{width:100%;border-collapse:collapse;font-size:12px}
th,td{border:1px solid #ccc;padding:4px 6px;text-align:start}th{background:#f3f3f3}td.n{text-align:end;font-variant-numeric:tabular-nums;direction:ltr}
@page{size:A4;margin:12mm}</style></head><body><h1>${esc(title)}</h1><p>${esc(subtitle)}</p><table><thead><tr>${columns
    .map((c) => `<th>${esc(c)}</th>`)
    .join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map(cell).join("")}</tr>`).join("")}</tbody></table></body></html>`;
}

export function openPrint(title: string, subtitle: string, columns: string[], rows: Cell[][]): void {
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(printHtml(title, subtitle, columns, rows));
  w.document.close();
  w.focus();
  w.print();
}
