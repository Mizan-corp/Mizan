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
    qAr: "هل أحتاج لبطاقة دفع لبدء التجربة المجانية؟",
    qEn: "Do I need a card to start the free trial?",
    aAr: "لا. تبدأ كل مساحة عمل جديدة بتجربة مجانية لمدة 14 يومًا بدون أي وسيلة دفع، في حدود باقة التجربة.",
    aEn: "No. Every new workspace starts with a free 14-day trial without any payment details, within the trial's limits.",
  },
  {
    qAr: "كيف أدفع الاشتراك؟",
    qEn: "How do I pay for a subscription?",
    aAr: "من لوحة المالك عبر بوابة الدفع Paymob، بالبطاقات البنكية أو المحافظ الإلكترونية حسب المتاح. لا نستلم بيانات بطاقتك ولا نحتفظ بها.",
    aEn: "From the owner panel, through the Paymob payment gateway, by bank card or mobile wallet as available. We never receive or store your card details.",
  },
  {
    qAr: "هل يتجدد الاشتراك تلقائيًا؟",
    qEn: "Does the subscription renew automatically?",
    aAr: "لا. تدفع عن شهر أو سنة مقدمًا، ولا نحتفظ بوسيلة الدفع، فلا يتجدد شيء تلقائيًا ولا يلزم إلغاء: إن لم تدفع للمدة التالية تنتهي عند آخر المدة المدفوعة.",
    aEn: "No. You pay for a month or a year in advance and we don't keep your payment method, so nothing renews and there's nothing to cancel: if you don't pay for the next period, it ends with the period you paid for.",
  },
  {
    qAr: "ماذا يحدث لبياناتي إذا انتهى الاشتراك؟",
    qEn: "What happens to my data if the subscription ends?",
    aAr: "تصبح مساحة العمل للقراءة فقط حتى التجديد، ولا تُحذف بياناتك، ويمكنك تصديرها من داخل النظام.",
    aEn: "The workspace becomes read-only until you renew. Your data isn't deleted, and you can export it from the system.",
  },
  {
    qAr: "هل يمكن استرداد المبلغ؟",
    qEn: "Can I get a refund?",
    aAr: "نعم. إذا طلبت ذلك خلال 14 يومًا من أول دفعة اشتراك لمساحة العمل نرد المبلغ كاملًا إلى وسيلة الدفع نفسها. التفاصيل في سياسة الاسترداد والإلغاء.",
    aEn: "Yes. If you ask within 14 days of a workspace's first subscription payment, we refund it in full to the same payment method. The details are in the refund and cancellation policy.",
  },
];
