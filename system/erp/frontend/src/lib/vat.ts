// VAT on documents (ADR-014 D6). The server computes and stores every document's VAT
// (app/platform/settings/vat.py); this mirrors the same rule so the point of sale can show the tax
// and, when prices exclude VAT, the total to collect before the sale is sent. The rates come from
// the server (GET /settings/vat), never from here.
//
// Rule: discounts first (the invoice discount shared pro rata, remainder on the largest line); each
// line rounded to the piastre, half up; prices including VAT: net = round(amount / (1 + rate)),
// tax = amount - net; excluding: tax = round(amount × rate) on top; totals are sums of lines.
import Decimal from "decimal.js";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type TaxCode = "standard" | "zero" | "exempt";

export interface VatSettings {
  vat_registered: boolean;
  prices_include_vat: boolean;
  tax_number: string;
  tax_number_display: string;
  codes: { code: TaxCode; label: string; rate: number }[];
  default_code: TaxCode;
}

export function useVat() {
  return useQuery({ queryKey: ["settings", "vat"], queryFn: () => api.get<VatSettings>("/settings/vat"), staleTime: 60_000 });
}

export interface LineTax { code: TaxCode | null; rate: number; net: Decimal; tax: Decimal; gross: Decimal }

const cents = (v: Decimal.Value) => new Decimal(v).toDecimalPlaces(2, Decimal.ROUND_HALF_UP);

export function rateOf(settings: Pick<VatSettings, "codes" | "default_code"> | undefined, code: string | null | undefined): number {
  const codes = settings?.codes ?? [];
  const found = codes.find((c) => c.code === code) ?? codes.find((c) => c.code === settings?.default_code);
  return found?.rate ?? 0;
}

export function lineTax(amount: Decimal.Value, code: TaxCode | null, rate: number, registered: boolean, inclusive: boolean): LineTax {
  const a = cents(amount);
  if (!registered) return { code: null, rate: 0, net: a, tax: new Decimal(0), gross: a };
  if (!rate) return { code, rate, net: a, tax: new Decimal(0), gross: a };
  const r = new Decimal(rate).div(100);
  if (inclusive) {
    const net = cents(a.div(r.plus(1)));
    return { code, rate, net, tax: a.minus(net), gross: a };
  }
  const tax = cents(a.times(r));
  return { code, rate, net: a, tax, gross: a.plus(tax) };
}

export function allocate(amounts: Decimal[], total: Decimal.Value): Decimal[] {
  const t = cents(total);
  if (!amounts.length) return [];
  if (t.isZero()) return amounts.map(() => new Decimal(0));
  const base = amounts.reduce((s, a) => s.plus(a), new Decimal(0));
  if (base.lte(0)) return amounts.map((_, i) => (i === 0 ? t : new Decimal(0)));
  const shares = amounts.map((a) => cents(t.times(a).div(base)));
  let largest = 0;
  amounts.forEach((a, i) => { if (a.gt(amounts[largest])) largest = i; });
  shares[largest] = shares[largest].plus(t.minus(shares.reduce((s, x) => s.plus(x), new Decimal(0))));
  return shares;
}

/** Each line's VAT for a document: `lines` are (amount after the line's own discount, tax code). */
export function documentTaxes(lines: { amount: Decimal.Value; code: TaxCode | null }[], invoiceDiscount: Decimal.Value,
                              settings: VatSettings | undefined): LineTax[] {
  const registered = !!settings?.vat_registered;
  const inclusive = settings?.prices_include_vat ?? true;
  const raw = lines.map((l) => new Decimal(l.amount));
  const amounts = raw.map((a) => cents(a));
  const shares = allocate(amounts, invoiceDiscount);
  const bases = amounts.map((a, i) => a.minus(shares[i]));
  if (bases.length) {
    const target = cents(raw.reduce((s, a) => s.plus(a), new Decimal(0)).minus(cents(invoiceDiscount)));
    const diff = target.minus(bases.reduce((s, b) => s.plus(b), new Decimal(0)));
    if (!diff.isZero()) {
      let largest = 0;
      amounts.forEach((a, i) => { if (a.gt(amounts[largest])) largest = i; });
      bases[largest] = bases[largest].plus(diff);
    }
  }
  return bases.map((b, i) => {
    const code = registered ? ((lines[i].code ?? settings?.default_code ?? "standard") as TaxCode) : null;
    return lineTax(b, code, registered ? rateOf(settings, code) : 0, registered, inclusive);
  });
}

export function sumTaxes(taxes: LineTax[]): { net: Decimal; tax: Decimal; gross: Decimal } {
  const z = new Decimal(0);
  return taxes.reduce((s, t) => ({ net: s.net.plus(t.net), tax: s.tax.plus(t.tax), gross: s.gross.plus(t.gross) }),
                      { net: z, tax: z, gross: z });
}
