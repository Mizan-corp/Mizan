// Finance: the screens' rules that aren't drawing (tested in __tests__/lib.test.ts). They mirror the
// server's (routes/expenses.py, services/expenses.py): the server decides again.
import { D } from "@/lib/format";

export type ExpenseStatus = "draft" | "approved" | "rejected" | "cancelled";
export type RecurringInterval = "weekly" | "monthly" | "yearly";

export const EXPENSE_STATUS: Record<ExpenseStatus, { label: string; tone: "success" | "warning" | "danger" | "muted" }> = {
  draft: { label: "مسودة بانتظار الاعتماد", tone: "warning" },
  approved: { label: "معتمد ومصروف", tone: "success" },
  rejected: { label: "مرفوض", tone: "danger" },
  cancelled: { label: "ملغى (أُعيد المبلغ)", tone: "muted" },
};

export const INTERVAL_LABEL: Record<RecurringInterval, string> = { weekly: "أسبوعياً", monthly: "شهرياً", yearly: "سنوياً" };

export interface ExpenseActions {
  /** "full": every field (a draft); "notes": the notes and the recurrence only (decided). */
  edit: "full" | "notes";
  approve: boolean;
  reject: boolean;
  remove: boolean;
  cancel: boolean;
}

/** What can be done with an expense: only a draft is decided or edited in full; an approved one
 *  is cancelled (its money goes back), never deleted; payroll's is managed from the payroll screen. */
export function expenseActions(e: { status: ExpenseStatus; payment_method?: string | null }): ExpenseActions {
  const draft = e.status === "draft";
  return {
    edit: draft ? "full" : "notes",
    approve: draft,
    reject: draft,
    remove: draft || e.status === "rejected",
    cancel: e.status === "approved" && e.payment_method !== "payroll",
  };
}

export interface ExpenseForm {
  description: string;
  amount: string;
  tax_amount: string;
  date: string;
  category_id: string;
  vendor_id: string;
  warehouse_id: string;
  payment_method: string;
  source: string;
  notes: string;
  is_recurring: boolean;
  recurring_interval: RecurringInterval;
  recurring_end_date: string;
}

/** An amount typed by hand as the API takes it ("1234.50"); null when it isn't a positive number. */
export function amountOrNull(raw: string): string | null {
  const s = raw.trim().replace(/[٠-٩]/g, (c) => String("٠١٢٣٤٥٦٧٨٩".indexOf(c))).replace(/٫/g, ".").replace(/,/g, "");
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return null;
  const v = D(s);
  return v.gt(0) ? v.toFixed(2) : null;
}

/** The recurrence fields of a form as the API takes them: none when the expense doesn't recur. */
export function recurrenceBody(f: Pick<ExpenseForm, "is_recurring" | "recurring_interval" | "recurring_end_date">) {
  return f.is_recurring
    ? { is_recurring: true, recurring_interval: f.recurring_interval, recurring_end_date: f.recurring_end_date || null }
    : { is_recurring: false, recurring_interval: null, recurring_end_date: null };
}

/** Pages of a list of `total` rows, `size` a page (at least one). */
export function pageCount(total: number, size: number): number {
  return Math.max(1, Math.ceil((total || 0) / Math.max(1, size)));
}
