/**
 * Who sells Mizan, and how to reach them. Used by the legal pages, the contact
 * page and the footer: change it here only. The seller is an individual (sole
 * trader); identity documents are with Paymob and are not published.
 */
export const BUSINESS = {
  product: { ar: "ميزان", en: "Mizan" },
  seller: { ar: "عمار محمد السيد محمد", en: "Ammar Mohamed Elsayed Mohamed" },
  sellerType: { ar: "تاجر فرد", en: "sole trader" },
  city: { ar: "السويس، مصر", en: "Suez, Egypt" },
  /** E.164 without "+", for wa.me and tel: links. */
  phoneDigits: "201067790350",
  phoneDisplay: "+20 106 779 0350",
  /** When the current versions of the legal pages took effect. */
  effective: { ar: "10 نوفمبر 2026", en: "10 November 2026" },
} as const;

export const PHONE_HREF = `tel:+${BUSINESS.phoneDigits}`;

export function whatsappHref(text?: string): string {
  return `https://wa.me/${BUSINESS.phoneDigits}${text ? `?text=${encodeURIComponent(text)}` : ""}`;
}
