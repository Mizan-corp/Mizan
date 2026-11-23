/**
 * The pricing page's questions. Also the website's FAQPage structured data, so keep them true to
 * the terms (website/frontend/src/features/legal/documents.ts) and visible on the page.
 */
export interface Faq {
  qAr: string;
  qEn: string;
  aAr: string;
  aEn: string;
}

export const PRICING_FAQS: Faq[] = [
  {
    qAr: "هل أحتاج لبطاقة ائتمان لبدء التجربة المجانية؟",
    qEn: "Do I need a credit card for the 14-day trial?",
    aAr: "إطلاقاً. يمكنك تفعيل حسابك والبدء في إدارة مخزونك ونقاط البيع مجاناً بالكامل لمدة 14 يوماً بدون إدخال أي وسيلة دفع.",
    aEn: "Not at all. You can register and experience full POS, inventory, and accounting features for 14 days with zero payment info required.",
  },
  {
    qAr: "ما هي طرق الدفع المتاحة داخل مصر وخارجها؟",
    qEn: "What payment methods are supported?",
    aAr: "ندعم السداد بالجنيه المصري عبر كود فوري (Fawry)، تحويل فوري عبر إنستاباي (InstaPay)، محفظة فودافون كاش، والبطاقات الائتمانية البنكية (Visa / MasterCard).",
    aEn: "We support EGP billing via Fawry pay code, instant bank transfers via InstaPay, Vodafone Cash, and standard Visa / Mastercard.",
  },
  {
    qAr: "هل يمكنني الترقية أو تغيير الباقة لاحقاً مع توسع فروعنا؟",
    qEn: "Can I scale or upgrade our plan as we add branches?",
    aAr: "نعم وبكل سهولة. يتم احتساب فرق السعر بدقة متناهية (Prorated) وترقية مساحة العمل فورياً دون أي انقطاع في الخدمة أو توقف للكاشير.",
    aEn: "Yes, seamlessly. Pricing is prorated and your workspace limits and modules upgrade instantly with zero cashier downtime.",
  },
  {
    qAr: "هل تبقى بيانات مشروعي معزولة في حال انتهاء الاشتراك؟",
    qEn: "Is our financial data safe if subscription lapses?",
    aAr: "تبقى كافة فواتيرك وقيودك المحاسبية محفوظة ومعزولة ومشفرة بنمط القراءة فقط لمدة 90 يوماً إضافية مع إمكانية تصديرها بالكامل بصيغة Excel أو JSON في أي وقت.",
    aEn: "All financial journals and transaction records remain strictly isolated, encrypted, and accessible in read-only mode for 90 days with one-click Excel/JSON export.",
  },
];
