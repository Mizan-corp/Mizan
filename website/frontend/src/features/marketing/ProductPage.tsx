import { lazy, Suspense, useState } from "react";
import { Link } from "@app/seo/LocaleLink";
import {
  Boxes,
  Database,
  Cpu,
  Layers,
  ArrowRight,
  ArrowLeft,
} from "lucide-react";
import { Button } from "@/components/kit/button";
import { MarketingLayout } from "./MarketingLayout";

// A separate chunk and Suspense boundary: hydrated on its own, after the page (ADR-016).
const MizanModularArchitectureShowcase = lazy(() =>
  import("./components/MizanModularArchitectureShowcase").then((m) => ({ default: m.MizanModularArchitectureShowcase })),
);
import { MizanMagnetic } from "@/components/motion/MizanMagnetic";
import { useTranslation } from "@/i18n";

export default function ProductPage() {
  const { locale } = useTranslation();
  const isAr = locale === "ar";
  const [activeWorkflowStep, setActiveWorkflowStep] = useState<number>(0);

  const workflowSteps = [
    {
      titleAr: "1. حركة بيع في الكاشير (POS)",
      titleEn: "1. Cashier Point of Sale Transaction",
      descAr: "يمسح الكاشير باركود المنتج ويصدر الفاتورة ويطبع الإيصال الحراري.",
      descEn: "The cashier scans the barcode, issues the invoice and prints the thermal receipt.",
      badge: "POS Terminal",
    },
    {
      titleAr: "2. خصم المخزون اللحظي (WMS)",
      titleEn: "2. Instant Warehouse Inventory Deduction",
      descAr: "تُخصم الكميات من مخزن الفرع فورًا، وينبّهك ميزان إذا وصل الصنف إلى حد إعادة الطلب.",
      descEn: "The quantities leave the branch's warehouse at once, and Mizan alerts you when an item reaches its reorder level.",
      badge: "Inventory Sync",
    },
    {
      titleAr: "3. ترحيل القيود لدفتر الأستاذ (GL)",
      titleEn: "3. Automated General Ledger Journal Posting",
      descAr: "مع تفعيل المحاسبة يُنشأ قيد مزدوج تلقائي: مدين (الخزينة) ودائن (إيراد المبيعات + ضريبة القيمة المضافة) بدون تدخل يدوي.",
      descEn: "With accounting on, a double-entry posting is made automatically: debit the cash account, credit sales revenue and VAT.",
      badge: "General Ledger",
    },
    {
      titleAr: "4. تقفيل الوردية ومطابقة الدرج",
      titleEn: "4. Shift close and drawer count",
      descAr: "تُسجَّل الفاتورة على وردية الكاشير، وعند التقفيل يُطابَق نقد الدرج مع المبيعات ويُرحَّل أي عجز أو زيادة.",
      descEn: "The sale is recorded on the cashier's shift; at closing, the cash in the drawer is checked against it and any shortage or surplus is posted.",
      badge: "Shift close",
    },
  ];

  return (
    <MarketingLayout>
      <div className="py-12 sm:py-20 space-y-16 sm:space-y-24 bg-[#FAF6F0] text-[#262321]">
        {/* 1. Hero Header matching Image 4 */}
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#DECFC0] bg-[#FAF0E4] px-4 py-1.5 text-xs font-semibold text-[#651E2C]">
            <Layers className="h-3.5 w-3.5" />
            <span>{isAr ? "معمارية المنظومة الموحدة" : "Unified Enterprise Architecture"}</span>
          </div>

          <h1
            className={`text-4xl sm:text-5xl lg:text-6xl font-normal text-[#262321] tracking-tight max-w-4xl mx-auto leading-tight ${
              isAr ? "font-serif-ar" : "font-serif-en"
            }`}
          >
            {isAr
              ? "منصة أعمال متكاملة في نظام واحد"
              : "An Integrated Business Platform in One System"}
          </h1>

          <p className="max-w-2xl mx-auto text-sm sm:text-base text-[#77716E] leading-relaxed">
            {isAr
              ? "وداعاً لتشتت البيانات بين برامج منفصلة لكل قسم. في ميزان ERP، تتصل كافة الموديولات بشجرة حسابات موحدة، وقاعدة بيانات معزولة ومحرك أحداث لحظي."
              : "Eliminate fragmented data silos. In Mizan ERP, all operational modules connect to a unified ledger, isolated cloud database, and real-time event pipeline."}
          </p>

          {/* 3D Isometric Modular Blocks Illustration matching Image 4 */}
          <div className="pt-6 max-w-4xl mx-auto">
            <div className="relative rounded-3xl border border-[#DECFC0] bg-gradient-to-b from-[#FAF0E4]/60 to-[#FFFFFF] p-8 sm:p-12 shadow-xl overflow-hidden">
              {/* Isometric 3D Module Blocks Visual */}
              <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6">
                {[
                  { nameAr: "المحاسبة العامة", nameEn: "General Ledger", color: "#651E2C" },
                  { nameAr: "نقاط البيع POS", nameEn: "POS Terminal", color: "#8A293B" },
                  { nameAr: "المستودعات والمخازن", nameEn: "Warehouses", color: "#48151F" },
                  { nameAr: "المشتريات والموردين", nameEn: "Procurement", color: "#B86B76" },
                  { nameAr: "الموارد البشرية HR", nameEn: "Human Resources", color: "#D4626E" },
                  { nameAr: "العملاء والموردون", nameEn: "Customers & Suppliers", color: "#35151D" },
                ].map((block, i) => (
                  <div
                    key={i}
                    className="group relative flex flex-col items-center justify-center w-36 h-28 sm:w-44 sm:h-32 rounded-2xl border border-[#DECFC0] bg-[#FFFFFF] p-3 shadow-md hover:shadow-xl hover:-translate-y-1 transition-all"
                  >
                    <div
                      className="w-10 h-10 rounded-xl mb-2 flex items-center justify-center text-white font-bold text-xs shadow-sm"
                      style={{ backgroundColor: block.color }}
                    >
                      <Layers className="h-5 w-5" />
                    </div>
                    <span className="text-xs font-bold text-[#262321] text-center">
                      {isAr ? block.nameAr : block.nameEn}
                    </span>
                    <span className="text-[10px] text-[#27835C] font-mono mt-0.5">●</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Interactive Ecosystem Canvas */}
          <div className="pt-10 max-w-6xl mx-auto">
            <Suspense fallback={null}>
              <MizanModularArchitectureShowcase />
            </Suspense>
          </div>
        </div>

        {/* 2. Visual Architecture Layers */}
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="rounded-3xl border border-[#DECFC0] bg-[#FFFFFF] p-6 sm:p-10 shadow-xl space-y-8">
            <div className="text-center space-y-1">
              <h2
                className={`text-2xl sm:text-3xl font-semibold text-[#262321] ${
                  isAr ? "font-serif-ar" : "font-serif-en"
                }`}
              >
                {isAr
                  ? "بنية ذكية لعمل أكثر كفاءة"
                  : "Smart Architecture for Maximum Efficiency"}
              </h2>
              <p className="text-xs sm:text-sm text-[#77716E]">
                {isAr
                  ? "تصميم هندسي يجمع بين صلابة النواة ومرونة التخصيص المستقل"
                  : "A solid core with modules you switch on, and each business's data kept apart"}
              </p>
            </div>

            <div className="space-y-4">
              {/* Layer 1: Core System */}
              <div className="rounded-2xl border border-[#DECFC0] bg-[#FAF0E4]/60 p-5 sm:p-6 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-[#651E2C] text-[#FAF6F0]">
                      <Database className="h-5 w-5" />
                    </div>
                    <span className="font-bold text-sm sm:text-base text-[#262321]">
                      {isAr
                        ? "الطبقة الأولى: النواة والأمان وقواعد البيانات المعزولة (PostgreSQL RLS)"
                        : "Layer 1: Isolated Core Engine & Row-Level Security"}
                    </span>
                  </div>
                  <span className="text-[11px] font-semibold text-[#651E2C] bg-[#651E2C]/10 px-2.5 py-0.5 rounded-full">
                    {isAr ? "أساسية للجميع" : "Core Pillar"}
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-[#55504D] leading-relaxed">
                  {isAr
                    ? "تتولى المستخدمين والصلاحيات، تسجيل الدخول وكلمات المرور المشفرة، شجرة الحسابات، سجل العمليات المهمة، وعزل بيانات كل منشأة (RLS)."
                    : "Users and permissions, sign-in and hashed passwords, the chart of accounts, a log of important actions, and each business's data isolation (RLS)."}
                </p>
              </div>

              {/* Layer 2: Modular Applications */}
              <div className="rounded-2xl border border-[#DECFC0] bg-[#FAF6F0] p-5 sm:p-6 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-[#8A293B] text-[#FAF6F0]">
                      <Boxes className="h-5 w-5" />
                    </div>
                    <span className="font-bold text-sm sm:text-base text-[#262321]">
                      {isAr
                        ? "الطبقة الثانية: الموديولات القطاعية المعيارية (Modular Business Apps)"
                        : "Layer 2: Pluggable Modular Business Applications"}
                    </span>
                  </div>
                  <span className="text-[11px] font-semibold text-[#27835C] bg-[#27835C]/10 px-2.5 py-0.5 rounded-full">
                    {isAr ? "تفعيل اختياري" : "On-Demand"}
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-[#55504D] leading-relaxed">
                  {isAr
                    ? "تطبيقات منفصلة وظيفياً تتكامل عبر واجهات برمجية قياسية: نقاط البيع السريعة، المخازن المتعددة، المشتريات، الموارد البشرية، وشاشات المطبخ KDS."
                    : "Functionally independent modules integrating via standardized APIs: POS, multi-branch inventory, procurement, HR, and KDS displays."}
                </p>
              </div>

              {/* Layer 3: Integration & Extensibility */}
              <div className="rounded-2xl border border-[#DECFC0] bg-[#FAF0E4]/60 p-5 sm:p-6 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-[#35151D] text-[#FAF6F0]">
                      <Cpu className="h-5 w-5" />
                    </div>
                    <span className="font-bold text-sm sm:text-base text-[#262321]">
                      {isAr
                        ? "الطبقة الثالثة: الأجهزة الطرفية (Hardware)"
                        : "Layer 3: Hardware"}
                    </span>
                  </div>
                  <span className="text-[11px] font-semibold text-[#C58A35] bg-[#C58A35]/10 px-2.5 py-0.5 rounded-full">
                    {isAr ? "ربط فوري" : "Direct Link"}
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-[#55504D] leading-relaxed">
                  {isAr
                    ? "يعمل مع أجهزتك الحالية: أي طابعة إيصالات حرارية معرّفة على الجهاز (80mm أو 58mm)، قارئات الباركود، وملصقات باركود موازين الوزن في محلات التجزئة."
                    : "Works with the hardware you already have: any thermal receipt printer installed on the computer (80mm or 58mm), barcode scanners, and the barcode labels of retail weighing scales."}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* 3. Real-Time Workflow Trace */}
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8 space-y-6">
          <div className="text-start space-y-1">
            <h2
              className={`text-2xl sm:text-3xl font-semibold text-[#262321] ${
                isAr ? "font-serif-ar" : "font-serif-en"
              }`}
            >
              {isAr ? "دورة تدفق العملية الواحدة عبر المنظومة" : "Live Single-Transaction Workflow Trace"}
            </h2>
            <p className="text-xs sm:text-sm text-[#77716E]">
              {isAr
                ? "شاهد كيف تنتقل حركة البيع الواحدة بين نقاط البيع والمخزن والمالية والرواتب آلياً"
                : "Observe how a single cashier transaction propagates across inventory, GL, and HR"}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {workflowSteps.map((step, idx) => {
              const isSelected = activeWorkflowStep === idx;
              return (
                <button
                  key={idx}
                  onClick={() => setActiveWorkflowStep(idx)}
                  className={`text-start p-5 rounded-2xl border transition-all ${
                    isSelected
                      ? "border-[#651E2C] bg-[#FFFFFF] shadow-lg ring-1 ring-[#651E2C]"
                      : "border-[#DECFC0] bg-[#FFFFFF]/70 hover:bg-[#FFFFFF]"
                  }`}
                >
                  <div className="text-xs font-bold text-[#651E2C] font-mono mb-2">
                    {step.badge}
                  </div>
                  <h3 className="font-bold text-sm text-[#262321] mb-1">
                    {isAr ? step.titleAr : step.titleEn}
                  </h3>
                  <p className="text-xs text-[#77716E] leading-relaxed">
                    {isAr ? step.descAr : step.descEn}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        {/* 4. Bottom Conversion Banner */}
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="rounded-3xl bg-[#35151D] text-[#FAF6F0] p-8 sm:p-12 text-center space-y-5 shadow-2xl">
            <h2
              className={`text-2xl sm:text-3xl lg:text-4xl font-normal tracking-tight ${
                isAr ? "font-serif-ar" : "font-serif-en"
              }`}
            >
              {isAr
                ? "جاهز لربط عمليات منشأتك في دفتر واحد؟"
                : "Ready to Bring Your Enterprise Into Balance?"}
            </h2>
            <p className="text-xs sm:text-sm text-[#E7D6C1]/80 max-w-md mx-auto">
              {isAr
                ? "ابدأ تجربتك المجانية لمدة 14 يوماً بدون الحاجة لبطاقة دفع."
                : "Start your free 14-day trial: no card, instant cloud setup."}
            </p>
            <div className="pt-2">
              <MizanMagnetic>
                <Button
                  size="lg"
                  className="bg-[#651E2C] text-[#FAF6F0] hover:bg-[#521723] rounded-full px-8 py-3.5 text-sm font-semibold shadow-lg"
                  render={<Link to="/signup" />}
                  nativeButton={false}
                >
                  <span>{isAr ? "ابدأ الآن مجاناً" : "Get Started Free"}</span>
                  {isAr ? <ArrowLeft className="h-4 w-4 ms-2" /> : <ArrowRight className="h-4 w-4 ms-2" />}
                </Button>
              </MizanMagnetic>
            </div>
          </div>
        </div>
      </div>
    </MarketingLayout>
  );
}
