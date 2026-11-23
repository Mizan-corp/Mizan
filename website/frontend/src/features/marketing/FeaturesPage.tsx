import { Link } from "@app/seo/LocaleLink";
import {
  BarChart3,
  ShoppingCart,
  Users,
  Layers,
  Box,
  Briefcase,
  Check,
  ArrowRight,
  ArrowLeft,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/kit/button";
import { MarketingLayout } from "./MarketingLayout";
import { useTranslation } from "@/i18n";

/** Where each module is explained in depth: its page, or its chapter of the user guide. */
const FEATURE_DETAIL: Record<string, string> = {
  finance: "/docs/modules/accounting",
  sales: "/docs/modules/pos",
  hr: "/docs/modules/hr",
  inventory: "/features/inventory",
  purchasing: "/docs/modules/purchasing",
};

export default function FeaturesPage() {
  const { locale } = useTranslation();
  const isAr = locale === "ar";

  const coreFeatures = [
    {
      id: "finance",
      titleAr: "إدارة مالية متقدمة",
      titleEn: "Advanced Financial Management",
      descAr: "شجرة حسابات موحدة، قيود يومية تلقائية، تسوية بنكية آلية، وميزان مراجعة وتقارير أرباح وخسائر لحظية.",
      descEn: "Unified chart of accounts, automated journal entries, bank reconciliation, balance sheet, and live P&L reports.",
      icon: BarChart3,
      badge: "Accounting",
      itemsAr: [
        "إصدار قيود محاسبية تلقائية مع كل حركة",
        "كشوف حسابات تفصيلية للعملاء والموردين",
        "ميزان المراجعة وقائمة الدخل والميزانية العمومية",
        "احتساب ضريبة القيمة المضافة وتقريرها الشهري",
      ],
      itemsEn: [
        "Automated double-entry posting per transaction",
        "Detailed customer and vendor sub-ledgers",
        "Trial balance, income statement and balance sheet",
        "VAT on documents and a monthly VAT report",
      ],
    },
    {
      id: "sales",
      titleAr: "إدارة المبيعات ونقاط البيع",
      titleEn: "Sales & Fast POS Terminal",
      descAr: "فواتير بضريبة القيمة المضافة، قراءة باركود سريعة، طباعة إيصالات حرارية، الدفع بأكثر من طريقة، وحفظ الفاتورة على الجهاز إذا انقطع الإنترنت.",
      descEn: "Invoices with VAT, fast barcode scanning, thermal receipts, split payments, and sales kept on the device if the internet drops.",
      icon: ShoppingCart,
      badge: "Sales & POS",
      itemsAr: [
        "دعم قارئات الباركود وطابعات 80mm/58mm",
        "تعليق واستئناف الفواتير بسلاسة",
        "تقفيل الوردية ومطابقة نقد الدرج",
        "الخصومات، وعروض الأسعار التي تتحول إلى فواتير",
      ],
      itemsEn: [
        "80mm/58mm thermal receipts and barcode scanners",
        "Seamless bill holding and resume",
        "Shift close with a drawer count",
        "Discounts, and quotations that become invoices",
      ],
    },
    {
      id: "hr",
      titleAr: "إدارة الموارد البشرية",
      titleEn: "Human Resources & Payroll",
      descAr: "الحضور والانصراف يدويًا أو باستيراد ملف جهاز البصمة، مسير رواتب محسوب من الحضور، والسلف والخصومات والمكافآت.",
      descEn: "Attendance entered by hand or imported from your fingerprint device's file, payroll calculated from it, and advances, deductions and bonuses.",
      icon: Users,
      badge: "Human Resources",
      itemsAr: [
        "احتساب الرواتب والبدلات والخصومات آلياً",
        "متابعة ورديات الموظفين وجداول العمل",
        "سجل السلف والخصومات والمكافآت",
        "اعتماد المسير وصرفه من الخزنة",
      ],
      itemsEn: [
        "Automated salary and deductions calculation",
        "Shift scheduling and attendance audits",
        "Advances, deductions and bonuses",
        "Approve the payroll and pay it from a safe",
      ],
    },
    {
      id: "inventory",
      titleAr: "إدارة المخزون والمستودعات",
      titleEn: "Inventory & Warehouses",
      descAr: "أرصدة الأصناف في مستودعات متعددة، تنبيهات النواقص، التسويات والجرد، والتحويلات بين الفروع.",
      descEn: "Stock across several warehouses, low-stock alerts, adjustments and counts, and transfers between branches.",
      icon: Layers,
      badge: "Warehouses",
      itemsAr: [
        "رصيد كل صنف في كل مخزن لحظيًا",
        "التشغيلات وتواريخ الصلاحية للبضاعة الواردة",
        "أذون الصرف والإضافة والتحويلات المخزنية",
        "معالجة الهالك والتوالف بدقة تامة",
      ],
      itemsEn: [
        "Live stock of every item in every warehouse",
        "Batches and expiry dates on incoming goods",
        "Goods receipt, issue, and branch transfers",
        "Scrap and damaged inventory write-offs",
      ],
    },
    {
      id: "purchasing",
      titleAr: "المشتريات وإدارة الموردين",
      titleEn: "Purchasing & Vendors",
      descAr: "أوامر الشراء واستلام البضائع، فواتير ومرتجعات الشراء، والشراء الآجل وحسابات الموردين.",
      descEn: "Purchase orders and receiving, purchase bills and returns, buying on credit and supplier accounts.",
      icon: Box,
      badge: "Procurement",
      itemsAr: [
        "أسعار كل مورد لكل صنف وسجل الأسعار",
        "تسجيل فواتير الشراء وحساب متوسط التكلفة",
        "اقتراحات شراء للأصناف التي بلغت حد الطلب",
        "كشف حساب لكل مورد",
      ],
      itemsEn: [
        "Each supplier's prices per item, with history",
        "Purchase bills and weighted average costing",
        "Purchase suggestions for items at their reorder level",
        "A statement for every supplier",
      ],
    },
    {
      id: "reports",
      titleAr: "التقارير والمهام التلقائية",
      titleEn: "Reports & Scheduled Jobs",
      descAr: "تقارير المبيعات والأرباح والتدفق النقدي وأعمار الديون مع تصدير Excel، ومهام ليلية تعمل وحدها.",
      descEn: "Sales, profit, cash-flow and debt-aging reports with Excel export, and nightly jobs that run on their own.",
      icon: Briefcase,
      badge: "Reports",
      itemsAr: [
        "مبيعات يومية وشهرية وأفضل الأصناف وحسب الكاشير",
        "الأرباح والتدفق النقدي وأعمار ديون العملاء",
        "إغلاق الورديات المنسية تلقائيًا كل ليلة",
        "ملخص يومي للمبيعات في إشعارات الإدارة",
      ],
      itemsEn: [
        "Daily and monthly sales, top items, by cashier",
        "Profit, cash flow and customer debt aging",
        "Forgotten shifts closed automatically every night",
        "A daily sales summary in the managers' notifications",
      ],
    },
  ];

  return (
    <MarketingLayout>
      <div className="py-12 sm:py-20 space-y-16 sm:space-y-24 bg-[#FAF6F0] text-[#262321]">
        {/* 1. Hero Header matching Image 4 */}
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center space-y-5">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#DECFC0] bg-[#FAF0E4] px-4 py-1.5 text-xs font-semibold text-[#651E2C]">
            <Sparkles className="h-3.5 w-3.5" />
            <span>{isAr ? "قدرات المنظومة الشاملة" : "Complete Platform Capabilities"}</span>
          </div>

          <h1
            className={`text-4xl sm:text-5xl lg:text-6xl font-normal text-[#262321] tracking-tight max-w-4xl mx-auto leading-tight ${
              isAr ? "font-serif-ar" : "font-serif-en"
            }`}
          >
            {isAr
              ? "مميزات ميزان — كل ما تحتاجه لإدارة أعمالك بكفاءة"
              : "Mizan Features — Engineered for Total Operational Control"}
          </h1>

          <p className="max-w-2xl mx-auto text-sm sm:text-base text-[#77716E] leading-relaxed">
            {isAr
              ? "مجموعة متكاملة من التطبيقات والوظائف المصممة لتمنحك تحكماً مطلقاً في كل صنف، كل وردية، وكل قرش في منشأتك."
              : "A comprehensive suite of enterprise-grade tools designed to give you precision control over inventory, finances, and workforce."}
          </p>
        </div>

        {/* 2. Six Core Feature Cards Grid matching Image 4 */}
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
            {coreFeatures.map((feat) => {
              const Icon = feat.icon;
              return (
                <div
                  key={feat.id}
                  className="rounded-3xl border border-[#DECFC0] bg-[#FFFFFF] p-6 sm:p-8 shadow-md hover:shadow-xl hover:-translate-y-1 transition-all flex flex-col justify-between space-y-6"
                >
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FAF0E4] text-[#651E2C] shadow-xs">
                        <Icon className="h-6 w-6" />
                      </div>
                      <span className="text-xs font-bold text-[#651E2C] bg-[#651E2C]/10 px-3 py-1 rounded-full font-mono">
                        {feat.badge}
                      </span>
                    </div>

                    <h3
                      className={`text-xl font-bold text-[#262321] ${
                        isAr ? "font-serif-ar" : "font-serif-en text-2xl font-normal"
                      }`}
                    >
                      {isAr ? feat.titleAr : feat.titleEn}
                    </h3>

                    <p className="text-xs sm:text-sm text-[#77716E] leading-relaxed">
                      {isAr ? feat.descAr : feat.descEn}
                    </p>

                    <div className="pt-2 border-t border-[#E6DCD2] space-y-2">
                      {(isAr ? feat.itemsAr : feat.itemsEn).map((item, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-xs text-[#55504D]">
                          <Check className="h-3.5 w-3.5 text-[#27835C] shrink-0 mt-0.5" />
                          <span>{item}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {FEATURE_DETAIL[feat.id] && (
                    <Link
                      to={FEATURE_DETAIL[feat.id]}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#651E2C] hover:text-[#521723] pt-2"
                    >
                      <span>
                        {isAr ? `تفاصيل ${feat.titleAr}` : `More on ${feat.titleEn}`}
                      </span>
                      {isAr ? <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> : <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />}
                    </Link>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* 3. Deep Showcase Section: Smart Reports & Analytics matching Image 4 */}
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="rounded-3xl border border-[#DECFC0] bg-[#FAF0E4]/60 p-8 sm:p-14 shadow-xl space-y-8">
            <div className="max-w-2xl space-y-3">
              <span className="text-xs font-bold uppercase tracking-widest text-[#B86B76]">
                {isAr ? "ذكاء الأعمال الفوري" : "BUSINESS INTELLIGENCE"}
              </span>
              <h2
                className={`text-3xl sm:text-4xl font-normal text-[#262321] tracking-tight ${
                  isAr ? "font-serif-ar" : "font-serif-en"
                }`}
              >
                {isAr ? "تقارير وتحليلات ذكية لحظية" : "Live Intelligent Financial Analytics"}
              </h2>
              <p className="text-xs sm:text-sm text-[#77716E] leading-relaxed">
                {isAr
                  ? "لوحات بيانية تفاعلية تكشف لك في ثوانٍ معدل الربحية الحقيقي، الأصناف الأكثر مبيعاً، ومعدلات دوران المخزون دون انتظار محاسب أو نهاية الشهر."
                  : "Interactive analytical views showing true profit margins, fastest selling SKUs, and inventory turnover in real-time."}
              </p>
            </div>

            {/* Simulated Live Analytics Dashboard Board */}
            <div className="rounded-2xl border border-[#DECFC0] bg-[#FFFFFF] p-6 shadow-lg space-y-6">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 divide-y sm:divide-y-0 sm:divide-s divide-[#E6DCD2] text-center">
                <div className="p-2">
                  <div className="text-xs text-[#77716E]">{isAr ? "صافي أرباح الشهر" : "Net Profit"}</div>
                  <div className="text-lg sm:text-xl font-bold font-mono text-[#27835C] mt-1">EGP 342,850</div>
                  <div className="text-[10px] text-[#27835C]">↑ 18.4% vs last mo</div>
                </div>

                <div className="p-2">
                  <div className="text-xs text-[#77716E]">{isAr ? "معدل دوران المخزون" : "Turnover Rate"}</div>
                  <div className="text-lg sm:text-xl font-bold font-mono text-[#262321] mt-1">4.2x / yr</div>
                  <div className="text-[10px] text-[#77716E]">Healthy velocity</div>
                </div>

                <div className="p-2">
                  <div className="text-xs text-[#77716E]">{isAr ? "نسبة التحصيل النقدي" : "Cash Collection"}</div>
                  <div className="text-lg sm:text-xl font-bold font-mono text-[#651E2C] mt-1">94.8%</div>
                  <div className="text-[10px] text-[#77716E]">Low aging debt</div>
                </div>

                <div className="p-2">
                  <div className="text-xs text-[#77716E]">{isAr ? "متوسط زمن الفاتورة" : "Avg Checkout"}</div>
                  <div className="text-lg sm:text-xl font-bold font-mono text-[#262321] mt-1">1.8 sec</div>
                  <div className="text-[10px] text-[#27835C]">Zero queues</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 4. CTA */}
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center space-y-5">
          <h2
            className={`text-2xl sm:text-3xl lg:text-4xl font-normal text-[#262321] tracking-tight ${
              isAr ? "font-serif-ar" : "font-serif-en"
            }`}
          >
            {isAr ? "ابدأ تجربة كافة المميزات مجاناً لمدة 14 يوماً" : "Experience All Features with 14 Days Free"}
          </h2>
          <div className="flex justify-center pt-2">
            <Button
              size="lg"
              className="bg-[#651E2C] text-[#FAF6F0] hover:bg-[#521723] rounded-full px-8 py-3.5 text-sm font-semibold shadow-lg"
              render={<Link to="/signup" />}
              nativeButton={false}
            >
              <span>{isAr ? "ابدأ الآن" : "Start Free Trial"}</span>
              {isAr ? <ArrowLeft className="h-4 w-4 ms-2" /> : <ArrowRight className="h-4 w-4 ms-2" />}
            </Button>
          </div>
        </div>
      </div>
    </MarketingLayout>
  );
}
