import { ApiError } from "@/lib/api";

const egp = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const count = new Intl.NumberFormat("en-US");
const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const rel = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export const money = (v: number | null | undefined) => `EGP ${egp.format(Math.round(v ?? 0))}`;
export const num = (v: number | null | undefined) => count.format(v ?? 0);
export const date = (iso: string | null | undefined) => (iso ? dateFmt.format(new Date(iso)) : "—");
export const dateTime = (iso: string | null | undefined) => (iso ? dateTimeFmt.format(new Date(iso)) : "—");

export function ago(iso: string | null | undefined): string {
  if (!iso) return "never";
  const s = (new Date(iso).getTime() - Date.now()) / 1000;
  const a = Math.abs(s);
  if (a < 60) return "just now";
  if (a < 3600) return rel.format(Math.round(s / 60), "minute");
  if (a < 86400) return rel.format(Math.round(s / 3600), "hour");
  if (a < 86400 * 30) return rel.format(Math.round(s / 86400), "day");
  if (a < 86400 * 365) return rel.format(Math.round(s / (86400 * 30)), "month");
  return rel.format(Math.round(s / (86400 * 365)), "year");
}

export const plural = (n: number, one: string, many = `${one}s`) => `${num(n)} ${n === 1 ? one : many}`;

export function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 0) return "Can't reach the admin API. Check your connection and try again.";
    // Server messages are English; anything else falls back to the status.
    return /[\u0600-\u06FF]/.test(e.message) ? `Request failed (${e.status})` : e.message;
  }
  return e instanceof Error ? e.message : "Something went wrong";
}

// ─── Labels ────────────────────────────────────────────────────────────────

export const PLANS: Record<string, { label: string; price: number }> = {
  trial: { label: "Trial", price: 0 },
  starter: { label: "Starter", price: 450 },
  pro: { label: "Pro", price: 850 },
  enterprise: { label: "Enterprise", price: 1950 },
};
export const planLabel = (p: string) => PLANS[p]?.label ?? p;

const SECTORS: Record<string, string> = {
  retail: "Retail",
  restaurant: "Restaurant & café",
  pharmacy: "Pharmacy",
  consulting: "Consulting & accounting",
  school: "School",
  wholesale: "Wholesale",
  logistics: "Logistics",
  warehousing: "3PL warehousing",
  ecommerce: "E-commerce",
  healthcare: "Clinic & hospital",
  legal: "Law firm",
  travel: "Travel agency",
  hotel: "Hotel",
  gym: "Gym",
  salon: "Salon & spa",
  agency: "Creative agency",
  maintenance: "Field service",
  manufacturing: "Manufacturing",
  food: "Food production",
  pharmaceuticals: "Pharma manufacturing",
  printing: "Printing & packaging",
  construction: "Construction",
  property: "Real estate",
  agriculture: "Agriculture",
  energy: "Energy",
  banking: "Banking",
  insurance: "Insurance",
  government: "Government & NGO",
  entertainment: "Entertainment",
  petroleum: "Oil & gas",
  services: "Services",
  plumbing: "Plumbing supplies",
  electrical: "Electrical supplies",
  tiles: "Tiles",
  paint: "Paint",
};
/** An activity's name: Mizan's from the list, a developer's from `name` (ADR-012). */
export const sectorLabel = (s: string, name?: string | null) => SECTORS[s] ?? name ?? s.replace(/_/g, " ");
export const SECTOR_OPTIONS = Object.entries(SECTORS).slice(0, 30);

// Module families (system/core/backend/app/catalog/families.json).
const CATEGORIES: Record<string, string> = {
  general: "General",
  commerce: "Commerce",
  food_hospitality: "Food & hospitality",
  health: "Health",
  education: "Education",
  services: "Services",
  logistics: "Logistics",
  industry: "Industry",
  projects: "Projects, real estate & energy",
  institutions: "Financial & public institutions",
};
export const categoryLabel = (c: string) => CATEGORIES[c] ?? c.replace(/_/g, " ");

const ARABIC = /[\u0600-\u06FF]/;
export function moduleLabel(m: { id: string; name: string; name_en: string }): string {
  if (m.name_en && !ARABIC.test(m.name_en)) return m.name_en;
  const inParens = m.name.match(/\(([^)]*[A-Za-z][^)]*)\)/);
  return inParens ? inParens[1] : m.id;
}

export const MODES: Record<string, { label: string; short: string }> = {
  cloud_saas: { label: "Cloud", short: "Cloud" },
  desktop: { label: "Single device", short: "Desktop" },
  lan: { label: "Local network (LAN)", short: "LAN" },
};
export const modeLabel = (m: string) => MODES[m]?.label ?? m;

export type Tone = "ok" | "warn" | "bad" | "info" | "mute" | "ox";

export function trialText(daysLeft: number | null | undefined): { text: string; tone: Tone } {
  if (daysLeft == null) return { text: "Trial", tone: "info" };
  if (daysLeft < 0) return { text: `Trial ended ${plural(-daysLeft, "day")} ago`, tone: "bad" };
  if (daysLeft === 0) return { text: "Trial ends today", tone: "warn" };
  return { text: `Trial · ${plural(daysLeft, "day")} left`, tone: daysLeft <= 3 ? "warn" : "info" };
}

/** Activity signal from the last sale. */
export function pulse(lastSaleIso: string | null | undefined): { tone: Tone; label: string } {
  if (!lastSaleIso) return { tone: "mute", label: "No sales yet" };
  const hours = (Date.now() - new Date(lastSaleIso).getTime()) / 3_600_000;
  if (hours <= 24) return { tone: "ok", label: `Sold ${ago(lastSaleIso)}` };
  if (hours <= 24 * 7) return { tone: "warn", label: `Last sale ${ago(lastSaleIso)}` };
  return { tone: "mute", label: `Quiet since ${date(lastSaleIso)}` };
}
