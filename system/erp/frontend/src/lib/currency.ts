// The workspace's currency (الإعدادات → العملة, GET /settings): screens show money with it instead
// of a hard-coded "ج.م". The setting is free text; ISO codes get their Arabic short name.
import type Decimal from "decimal.js";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { money } from "@/lib/format";

const NAMES: Record<string, string> = {
  EGP: "ج.م", SAR: "ر.س", AED: "د.إ", KWD: "د.ك", QAR: "ر.ق", BHD: "د.ب", OMR: "ر.ع", JOD: "د.أ", USD: "$", EUR: "€",
};

/** The short name shown after an amount: the Egyptian pound when nothing is set. */
export function currencyLabel(raw: string | null | undefined): string {
  const v = (raw ?? "").trim();
  if (!v) return NAMES.EGP;
  return NAMES[v.toUpperCase()] ?? v;
}

/** An amount with the currency: "1,234.50 ج.م". */
export function moneyIn(value: string | number | Decimal | null | undefined, currency: string): string {
  return `${money(value)} ${currency}`;
}

export function useCurrency(): string {
  const q = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<{ currency?: string }>("/settings"),
    staleTime: 5 * 60_000,
  });
  return currencyLabel(q.data?.currency);
}
