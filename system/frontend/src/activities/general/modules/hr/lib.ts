// HR: labels and the screens' logic that isn't drawing (tested in __tests__/lib.test.ts).

export const ATTENDANCE_STATUS: Record<string, { label: string; tone: "success" | "warning" | "danger" | "muted" | "brand" }> = {
  present: { label: "حاضر", tone: "success" },
  absent: { label: "غائب", tone: "danger" },
  leave: { label: "إجازة", tone: "brand" },
  mission: { label: "مأمورية", tone: "brand" },
  excuse: { label: "عذر", tone: "warning" },
  weekend: { label: "عطلة أسبوعية", tone: "muted" },
  "pre-hire": { label: "قبل التعيين", tone: "muted" },
};

export const PERIOD_STATUS: Record<string, { label: string; tone: "success" | "warning" | "danger" | "muted" | "brand" }> = {
  draft: { label: "مسودة", tone: "muted" },
  review: { label: "قيد المراجعة", tone: "warning" },
  approved: { label: "معتمد", tone: "brand" },
  paid: { label: "مصروف", tone: "success" },
};

export const RECORD_TYPE: Record<string, { label: string; tone: "success" | "warning" | "danger" }> = {
  "سلفة": { label: "سلفة", tone: "warning" },
  "خصم": { label: "خصم", tone: "danger" },
  "مكافأة": { label: "مكافأة", tone: "success" },
};

export const AUDIT_ACTION: Record<string, string> = {
  create: "إضافة", update: "تعديل", cancel: "إلغاء", carry: "ترحيل", delete: "حذف",
};
export const AUDIT_ENTITY: Record<string, string> = {
  employee: "موظف", payroll_entry: "راتب", advance: "سلفة / خصم / مكافأة", attendance: "حضور",
};

/** Python's weekday numbers (the server's): Monday 0 … Sunday 6. */
export const WEEKDAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"];

export interface HrSettings {
  days_in_month: number;
  grace_period_minutes: number;
  late_penalty_multiplier: number | string;
  missing_checkout_penalty_hours: number | string;
  apply_missing_checkout_penalty: boolean;
  overtime_enabled: boolean;
  weekend_paid: boolean;
  weekend_day: number;
  day_start_hour: number;
  paid_leave_days: number;
  default_shift_start_hour: number;
  default_shift_end_hour: number;
}

export const NUMBER_SETTINGS: { key: keyof HrSettings; label: string; hint: string; min: number; max: number; step?: number }[] = [
  { key: "days_in_month", label: "أيام العمل في الشهر", hint: "يُقسم عليها الراتب لحساب أجر اليوم والساعة", min: 1, max: 31 },
  { key: "paid_leave_days", label: "أيام الإجازة المدفوعة في الشهر", hint: "ما زاد عليها إجازة بلا أجر", min: 0, max: 31 },
  { key: "grace_period_minutes", label: "سماح التأخير (دقائق)", hint: "لا يُحتسب تأخير أقل منها", min: 0, max: 240 },
  { key: "late_penalty_multiplier", label: "مضاعف خصم التأخير", hint: "ساعة التأخير تُخصم بهذا المضاعف", min: 0, max: 10, step: 0.25 },
  { key: "missing_checkout_penalty_hours", label: "خصم نسيان البصمة (ساعات)", hint: "عند غياب بصمة الدخول أو الخروج", min: 0, max: 24, step: 0.5 },
  { key: "day_start_hour", label: "بداية يوم الحضور (ساعة)", hint: "البصمة قبلها تُحسب لليوم السابق (ورديات الليل)", min: 0, max: 12 },
  { key: "default_shift_start_hour", label: "بداية الوردية الافتراضية (ساعة)", hint: "لموظف بلا وردية", min: 0, max: 23 },
  { key: "default_shift_end_hour", label: "نهاية الوردية الافتراضية (ساعة)", hint: "لموظف بلا وردية", min: 0, max: 23 },
];

/** The settings form as the API takes it: whole numbers where the server wants integers; null for
 *  what isn't a number in range (the form shows it and doesn't send). */
export function settingsPayload(form: Record<string, string | boolean>): Partial<HrSettings> | null {
  const out: Record<string, number | boolean | string> = {};
  for (const s of NUMBER_SETTINGS) {
    const raw = String(form[s.key] ?? "").trim();
    const v = Number(raw);
    if (!raw || !Number.isFinite(v) || v < s.min || v > s.max) return null;
    if (!s.step && !Number.isInteger(v)) return null;
    out[s.key] = s.step ? raw : v;
  }
  const weekend = Number(form.weekend_day);
  if (!Number.isInteger(weekend) || weekend < 0 || weekend > 6) return null;
  out.weekend_day = weekend;
  for (const k of ["apply_missing_checkout_penalty", "overtime_enabled", "weekend_paid"]) out[k] = Boolean(form[k]);
  return out as Partial<HrSettings>;
}

/** The hours the payroll counts for a shift "HH:MM" → "HH:MM", as the engine does: whole hours
 *  (the minutes are ignored), an overnight shift wrapping past midnight. */
export function shiftHours(start: string, end: string): number {
  const s = Number(start.split(":")[0]) || 0;
  const e = Number(end.split(":")[0]) || 0;
  return e > s ? e - s : 24 - s + e;
}

/** "YYYY-MM" of today in Egypt (the server's months). */
export function currentMonth(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Cairo", year: "numeric", month: "2-digit" }).format(now).slice(0, 7);
}

/** "08:30" of a stored check-in/out (wall-clock time marked UTC: the zone is ignored). */
export function clockOf(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = /T(\d{2}:\d{2})/.exec(iso);
  return m ? m[1] : "—";
}

export interface Paged<T> { items: T[]; total: number; page: number; page_size: number }
