import type { Faq } from "@/features/billing/pricingFaqs";

/**
 * The home page's questions, shown on the page and published as its FAQPage structured data
 * (src/seo/pages.ts): keep every answer true to the product.
 */
export const HOME_FAQS: Faq[] = [
  {
    qEn: "Can the cashier keep selling when the internet goes down?",
    qAr: "كيف يضمن ميزان استمرار البيع عند انقطاع كابل الإنترنت؟",
    aEn: "Yes. The point of sale works offline: it keeps an encrypted copy of your products and prices on the device, so you can scan barcodes, issue invoices and print receipts as usual. Everything syncs to the cloud as soon as the connection is back.",
    aAr: "يعمل تطبيق الكاشير بنمط Offline-First؛ حيث يحتفظ بنسخة مشفرة من الأصناف والأسعار محلياً داخل جهازك. يمكنك مسح الباركود، إصدار الفواتير، وطباعة الإيصالات بشكل طبيعي، وتتم المزامنة التلقائية مع السحابة فور عودة الاتصال.",
  },
  {
    qEn: "Does Mizan work with ordinary receipt printers and barcode scanners?",
    qAr: "هل يدعم النظام طابعات الإيصالات الحرارية وقوارئ الباركود المتوفرة بالمحل؟",
    aEn: "Yes. Mizan works with standard ESC/POS thermal receipt printers (80mm and 58mm, USB or network), wired and wireless barcode scanners, and barcode weighing scales. No proprietary hardware needed.",
    aAr: "نعم. يتكامل ميزان مباشرة مع كافة طابعات الإيصالات الحرارية القياسية عبر USB أو الشبكة (80 مم و58 مم) ببروتوكول ESC/POS، بالإضافة إلى قارئات الباركود السلكية واللاسلكية وموازين الباركود الإلكترونية.",
  },
  {
    qEn: "Can I turn on only the modules my business needs?",
    qAr: "هل يمكن تفعيل الوحدات والموديولات التي يحتاجها نشاطي فقط؟",
    aEn: "Absolutely. Mizan is completely modular. You can start with POS and Inventory, and later activate Accounting, HR, or Manufacturing with a single click as your business expands, keeping your subscription and interface clean.",
    aAr: "بالتأكيد. ميزان مصمم ببنية معيارية مرنة؛ يمكنك البدء بالكاشير والمخازن فقط، وتفعيل المحاسبة المتقدمة أو الموارد البشرية أو التصنيع بنقرة زر واحدة كلما نما عملك، دون أي تكاليف أو تعقيدات إضافية.",
  },
  {
    qEn: "Are Mizan invoices compliant with the Egyptian Tax Authority (ETA) requirements?",
    qAr: "هل تتوافق الفواتير مع اشتراطات الفاتورة الإلكترونية المصرية (ETA)؟",
    aEn: "Yes. Invoices include cryptographic QR codes according to Egyptian tax standards, along with tax registration numbers, commercial register details, and buyer data according to ETA regulations.",
    aAr: "نعم. يولد النظام رمز الاستجابة السريعة المشفر وفق المعايير الضريبية المصرية، ويتيح إدراج الرقم الضريبي والسجل التجاري وبيانات المشتري وفق ضوابط مصلحة الضرائب المصرية.",
  },
];
