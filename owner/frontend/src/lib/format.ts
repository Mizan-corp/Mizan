import { ApiError } from "@/lib/api";

// Arabic text with Latin digits, as on Egyptian invoices and receipts.
const LOCALE = "ar-EG-u-nu-latn";
const count = new Intl.NumberFormat(LOCALE);
const dateFmt = new Intl.DateTimeFormat(LOCALE, { day: "numeric", month: "long", year: "numeric" });
const rel = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });

export const num = (v: number | null | undefined) => count.format(v ?? 0);
export const money = (v: number | null | undefined) => `${count.format(Math.round(v ?? 0))} ج.م`;
export const date = (iso: string | null | undefined) => (iso ? dateFmt.format(new Date(iso)) : "—");

export function ago(iso: string | null | undefined): string {
  if (!iso) return "—";
  const s = (new Date(iso).getTime() - Date.now()) / 1000;
  const a = Math.abs(s);
  if (a < 60) return "الآن";
  if (a < 3600) return rel.format(Math.round(s / 60), "minute");
  if (a < 86400) return rel.format(Math.round(s / 3600), "hour");
  if (a < 86400 * 30) return rel.format(Math.round(s / 86400), "day");
  return date(iso);
}

/** "يوم واحد", "يومان", "3 أيام", "11 يومًا". */
export function days(n: number): string {
  const v = Math.abs(n);
  if (v === 1) return "يوم واحد";
  if (v === 2) return "يومان";
  if (v >= 3 && v <= 10) return `${num(v)} أيام`;
  return `${num(v)} يومًا`;
}

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 0) return "تعذر الاتصال بالخادم. تحقق من الإنترنت وحاول مرة أخرى.";
    if (e.status === 429) return "محاولات كثيرة. انتظر دقيقة ثم حاول مرة أخرى.";
    return e.message || `حدث خطأ (${e.status})`;
  }
  return e instanceof Error ? e.message : "حدث خطأ غير متوقع";
}

export type Tone = "ok" | "warn" | "bad" | "info" | "mute" | "wine";

export const PLAN_LABEL: Record<string, string> = {
  trial: "تجريبية",
  starter: "البداية",
  pro: "المحترفين",
  enterprise: "المؤسسات",
};
export const planLabel = (p: string) => PLAN_LABEL[p] ?? p;

export const SECTORS: [string, string][] = [
  ["retail", "تجزئة وسوبرماركت"],
  ["restaurant", "مطعم وكافيه"],
  ["pharmacy", "صيدلية"],
  ["wholesale", "جملة وتوزيع"],
  ["healthcare", "عيادة ومركز طبي"],
  ["salon", "صالون وسبا"],
  ["gym", "نادي رياضي"],
  ["school", "مدرسة وتعليم"],
  ["consulting", "استشارات ومحاسبة"],
  ["ecommerce", "متجر إلكتروني"],
  ["hotel", "فندق"],
  ["travel", "سياحة وسفر"],
  ["maintenance", "خدمات ميدانية"],
  ["construction", "مقاولات"],
  ["property", "عقارات"],
  ["manufacturing", "تصنيع"],
  ["food", "تصنيع غذائي"],
  ["printing", "طباعة وتغليف"],
  ["logistics", "نقل وشحن"],
  ["agency", "وكالة إبداعية"],
  ["legal", "مكتب محاماة"],
  ["agriculture", "زراعة"],
  ["plumbing", "أدوات صحية"],
  ["electrical", "أدوات كهربائية"],
  ["tiles", "سيراميك وبلاط"],
  ["paint", "دهانات"],
  ["services", "خدمات أخرى"],
];
const SECTOR_MAP = Object.fromEntries(SECTORS);
export const sectorLabel = (s: string) => SECTOR_MAP[s] ?? s.replace(/_/g, " ");

export function trialState(daysLeft: number | null | undefined): { text: string; tone: Tone } {
  if (daysLeft == null) return { text: "فترة تجريبية", tone: "info" };
  if (daysLeft < 0) return { text: `انتهت التجربة منذ ${days(daysLeft)}`, tone: "bad" };
  if (daysLeft === 0) return { text: "التجربة تنتهي اليوم", tone: "warn" };
  return { text: `متبقٍ ${days(daysLeft)} من التجربة`, tone: daysLeft <= 3 ? "warn" : "info" };
}

/** A paid plan's period (#66): read-only the moment it ends; a week of warning before. */
export function paidState(paidUntil: string | null | undefined): { text: string; tone: Tone; ended: boolean } | null {
  if (!paidUntil) return null;
  const left = Math.floor((new Date(paidUntil).getTime() - Date.now()) / 86_400_000);
  if (new Date(paidUntil).getTime() <= Date.now()) return { text: "انتهى الاشتراك — للقراءة فقط", tone: "bad", ended: true };
  if (left <= 7) return { text: left <= 0 ? "ينتهي الاشتراك اليوم" : `ينتهي الاشتراك خلال ${days(left)}`, tone: "warn", ended: false };
  return null;
}

export const INVOICE_STATUS: Record<string, { label: string; tone: Tone }> = {
  paid: { label: "مدفوعة", tone: "ok" },
  pending: { label: "بانتظار الدفع", tone: "warn" },
  failed: { label: "فشل الدفع", tone: "bad" },
  refunded: { label: "مستردة", tone: "mute" },
};

export const METHOD_LABEL: Record<string, string> = {
  paymob: "بطاقة / محفظة (Paymob)",
  card: "بطاقة",
  instapay: "إنستاباي",
  vodafone_cash: "فودافون كاش",
  fawry: "فوري",
  bank: "تحويل بنكي",
  bank_transfer: "تحويل بنكي",
};

export const MODE: Record<string, { label: string; short: string; desc: string }> = {
  cloud_saas: { label: "على السحابة", short: "سحابي", desc: "تفتحها من المتصفح على أي جهاز. نحن نستضيفها ونحفظ نسخها الاحتياطية." },
  desktop: { label: "جهاز واحد", short: "جهاز واحد", desc: "برنامج يُثبَّت على كمبيوتر واحد ويعمل بدون إنترنت. لا يتصل به جهاز آخر." },
  lan: { label: "شبكة محلية", short: "شبكة محلية", desc: "خادم على جهاز في منشأتك، وتتصل به أجهزة الكاشير والمكاتب عبر شبكتك الداخلية." },
};

export const LICENCE_STATUS: Record<string, { label: string; tone: Tone }> = {
  active: { label: "الترخيص ساري", tone: "ok" },
  expired: { label: "انتهى الترخيص", tone: "bad" },
  revoked: { label: "الترخيص موقوف", tone: "bad" },
  none: { label: "بدون ترخيص", tone: "mute" },
};
