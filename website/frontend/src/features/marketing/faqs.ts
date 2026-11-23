import type { Faq } from "@/features/billing/pricingFaqs";

/**
 * The home page's questions, shown on the page and published as its FAQPage structured data
 * (src/seo/pages.ts): keep every answer true to the product.
 */
export const HOME_FAQS: Faq[] = [
  {
    qEn: "Can the cashier keep selling when the internet goes down?",
    qAr: "كيف يضمن ميزان استمرار البيع عند انقطاع كابل الإنترنت؟",
    aEn: "Yes, for sales already on the till. If the connection drops at checkout, the sale is kept on the device and sent automatically when it's back, never twice. If your internet is often unreliable, Mizan can run entirely on one computer or on your shop's local network, with no internet at all.",
    aAr: "إذا انقطع الإنترنت عند الدفع، تُحفظ الفاتورة على الجهاز وتُرسل تلقائيًا فور عودة الاتصال، دون أن تتكرر. وإذا كان الإنترنت عندك غير مستقر دائمًا، يمكن تشغيل ميزان بالكامل على جهاز واحد أو على شبكة المحل بدون إنترنت.",
  },
  {
    qEn: "Does Mizan work with ordinary receipt printers and barcode scanners?",
    qAr: "هل يدعم النظام طابعات الإيصالات الحرارية وقوارئ الباركود المتوفرة بالمحل؟",
    aEn: "Yes. Mizan prints receipts on any thermal printer installed on the computer, 80mm or 58mm wide, works with wired and wireless barcode scanners, and in retail reads the barcode labels that weighing scales print. No special hardware needed.",
    aAr: "نعم. يطبع ميزان الإيصالات على أي طابعة حرارية معرّفة على الجهاز بعرض 80 مم أو 58 مم، ويعمل مع قارئات الباركود السلكية واللاسلكية، ويقرأ في محلات التجزئة ملصقات الباركود التي تطبعها موازين الوزن. لا يحتاج أجهزة خاصة.",
  },
  {
    qEn: "Can I turn on only the modules my business needs?",
    qAr: "هل يمكن تفعيل الوحدات والموديولات التي يحتاجها نشاطي فقط؟",
    aEn: "Yes. Mizan is modular: start with the point of sale and inventory, then switch on accounting, HR or other modules within your plan when you need them, and keep the screens free of what you don't use.",
    aAr: "بالتأكيد. ميزان مصمم ببنية معيارية مرنة؛ يمكنك البدء بالكاشير والمخازن فقط، ثم تفعيل المحاسبة أو الموارد البشرية أو غيرها في حدود باقتك حين تحتاجها، دون ازدحام الشاشات بما لا تستخدمه.",
  },
  {
    qEn: "Does Mizan issue Egyptian e-invoices and e-receipts (ETA)?",
    qAr: "هل يصدر ميزان الفاتورة والإيصال الإلكتروني المصري (ETA)؟",
    aEn: "No. Mizan doesn't submit invoices or receipts to the Egyptian Tax Authority's e-invoice and e-receipt systems. Its invoices show your tax registration number and the VAT when you turn VAT on for your products.",
    aAr: "لا. ميزان لا يرسل الفواتير أو الإيصالات إلى منظومة الفاتورة والإيصال الإلكتروني لمصلحة الضرائب المصرية. تظهر على فواتيره رقم التسجيل الضريبي لمنشأتك وضريبة القيمة المضافة عند تفعيلها على الأصناف.",
  },
];
