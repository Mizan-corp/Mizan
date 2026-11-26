import { useState, useEffect, type ComponentProps, type ComponentType, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Check,
  Sparkles,
  ChevronDown,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { PLANS, Plan } from "@/lib/plans";
import { APP_KIND, appUrl } from "@/lib/urls";
import { Button } from "@/components/kit/button";
import { Badge } from "@/components/kit/badge";
import { toast as sonnerToast } from "sonner";
import { useTranslation } from "@/i18n";
import { motion } from "motion/react";
import { MizanMagnetic } from "@/components/motion/MizanMagnetic";
import { PRICING_FAQS } from "./pricingFaqs";

interface SubscriptionInfo {
  plan: string;
  limits: {
    max_users: number;
    max_branches: number;
    max_monthly_sales: number;
  };
  usage: {
    current_users: number;
    current_branches: number;
    current_monthly_sales: number;
  };
  is_trial: boolean;
  trial_remaining_days: number | null;
  is_writable: boolean;
}

function PlainLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

/** Links that live on the website: in-app on the website, absolute elsewhere. */
function SiteLink({ to, ...rest }: { to: string } & Omit<ComponentProps<"a">, "href">) {
  return APP_KIND === "website" ? <Link to={to} {...rest} /> : <a href={appUrl("website", to)} {...rest} />;
}

const samePath = (path: string) => path;

/**
 * Plans & checkout. The website renders it inside its marketing layout for
 * visitors; the system app renders it inside the app shell for upgrades.
 */
export default function PricingPage({
  layout: Layout = PlainLayout,
  ownerPanel = null,
  sitePath = samePath,
}: {
  layout?: ComponentType<{ children: ReactNode }>;
  /** On the website, for a signed-in owner (#79): opens a path of the owner panel with their session. */
  ownerPanel?: ((path: string) => void) | null;
  /** On the website: a page's address in the visitor's language ("/signup" → "/en/signup"). */
  sitePath?: (path: string) => string;
}) {
  const { user, tenant } = useAuth();
  const navigate = useNavigate();
  const { locale } = useTranslation();
  const isAr = locale === "ar";

  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly");
  // The price animates when the visitor changes the billing cycle, not on the first paint.
  const [priceChanged, setPriceChanged] = useState(false);

  // Live Subscription Status (if logged in)
  const [subInfo, setSubInfo] = useState<SubscriptionInfo | null>(null);

  const [openFaq, setOpenFaq] = useState<number | null>(null);

  // Load tenant subscription info if logged in
  useEffect(() => {
    if (user && tenant) {
      api
        .get<SubscriptionInfo>("/billing/subscription")
        .then((res) => setSubInfo(res))
        .catch(() => {
          /* ignore error if not tenant admin */
        });
    }
  }, [user, tenant]);

  function handlePlanClick(p: Plan) {
    if (!user && ownerPanel) {
      // A signed-in owner chooses the workspace, then pays in the owner panel.
      ownerPanel(p.id === "trial" ? "/" : `/?plan=${p.id}&cycle=${billingCycle}`);
      return;
    }
    if (!user) {
      if (APP_KIND === "website") navigate(sitePath("/signup"));
      else window.location.assign(appUrl("website", "/signup"));
      return;
    }
    if (p.id === "trial") {
      sonnerToast.info(
        isAr
          ? "أنت مفعّل بالفعل على المنصة أو يمكنك اختيار إحدى الباقات الإنتاجية"
          : "You are already active or can choose an active production plan"
      );
      return;
    }
    // Subscribing and paying happen in the owner panel (Paymob), never inside a workspace.
    const target = tenant?.id ? `/workspaces/${tenant.id}?plan=${p.id}&cycle=${billingCycle}` : "/";
    window.location.assign(appUrl("owner", target));
  }

  const isCurrentPlan = (planId: string) => tenant?.plan === planId;

  // Filter the 3 paid commercial plans for the main luxury cards
  const commercialPlans = PLANS.filter((p) => p.id !== "trial");

  const comparisonFeatures = [
    { nameAr: "المستخدمين النشطين", nameEn: "Active Users", starter: "5", pro: "15", enterprise: "غير محدود / Unlimited" },
    { nameAr: "الفروع والمخازن المتصلة", nameEn: "Branches & Warehouses", starter: "1", pro: "3", enterprise: "غير محدود / Unlimited" },
    { nameAr: "حفظ الفواتير عند انقطاع الإنترنت", nameEn: "Sales kept when the internet drops", starter: true, pro: true, enterprise: true },
    { nameAr: "عزل بيانات كل منشأة (RLS)", nameEn: "Each business's data isolated (RLS)", starter: true, pro: true, enterprise: true },
    { nameAr: "الأنشطة المتاحة", nameEn: "Business activities", starter: "الأساسية / Core", pro: "التجارية والخدمية / Trade & services", enterprise: "كلها / All" },
    { nameAr: "شاشة المطبخ KDS", nameEn: "Kitchen display (KDS)", starter: true, pro: true, enterprise: true },
    { nameAr: "خادم مخصص ونطاق خاص (Custom Domain)", nameEn: "Dedicated Server & Custom Domain", starter: false, pro: false, enterprise: true },
    { nameAr: "ترخيص مكتبي .exe محلي للأجهزة", nameEn: "Local .exe Desktop License", starter: false, pro: false, enterprise: true },
    { nameAr: "الدعم الفني", nameEn: "Support", starter: "واتساب وهاتف / WhatsApp & phone", pro: "واتساب وهاتف / WhatsApp & phone", enterprise: "مدير حساب / Account manager" },
  ];


  return (
    <Layout>
      <div className="py-16 sm:py-24 space-y-20 bg-[#FAF6F0] text-[#262321] transition-colors">
        {/* 1. Hero Section */}
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#E7D6C1] bg-white/80 px-4 py-1.5 text-xs font-semibold text-[#651E2C] shadow-xs">
            <Sparkles className="size-3.5 text-[#B86B76]" />
            <span>
              {isAr
                ? "باقات اشتراك مرنة بالجنيه المصري — تفعيل فوري وبوابات سداد متعددة"
                : "Flexible Egyptian Pound pricing — Instant activation & local gateways"}
            </span>
          </div>

          <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-normal tracking-tight text-[#262321] leading-[1.15]">
            {isAr ? (
              <>
                استثمار مدروس وشفاف <br />
                <span className="italic text-[#B86B76]">لتحقيق التوازن التشغيلي</span>
              </>
            ) : (
              <>
                Predictable, transparent investment <br />
                <span className="italic text-[#B86B76]">in your operational balance</span>
              </>
            )}
          </h1>

          <p className="mx-auto max-w-2xl text-base sm:text-lg text-[#77716E] font-body leading-relaxed">
            {isAr
              ? "اختر الباقة المناسبة لحجم منشأتك. بدون رسوم خفية، مع إمكانية الترقية أو الإلغاء في أي وقت."
              : "Choose the package tailored to your business scale. No hidden fees, upgrade or adjust branches anytime."}
          </p>

          {/* Billing cycle toggle */}
          <div className="pt-4 flex flex-wrap items-center justify-center gap-4">
            {/* Monthly / Annual Toggle with sliding layoutId indicator */}
            <div className="relative inline-flex items-center rounded-full border border-[#E7D6C1] bg-white p-1 shadow-xs">
              <button
                type="button"
                onClick={() => { setBillingCycle("monthly"); setPriceChanged(true); }}
                className={`relative z-10 rounded-full px-5 py-2 text-xs font-semibold transition-colors ${
                  billingCycle === "monthly"
                    ? "text-white"
                    : "text-[#77716E] hover:text-[#262321]"
                }`}
              >
                {billingCycle === "monthly" && (
                  <motion.div
                    layoutId="billingToggleActive"
                    transition={{ type: "spring", stiffness: 450, damping: 30 }}
                    className="absolute inset-0 rounded-full bg-[#651E2C] shadow-xs z-[-1]"
                  />
                )}
                <span>{isAr ? "الدفع الشهري" : "Monthly Billing"}</span>
              </button>
              <button
                type="button"
                onClick={() => { setBillingCycle("annual"); setPriceChanged(true); }}
                className={`relative z-10 rounded-full px-5 py-2 text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                  billingCycle === "annual"
                    ? "text-white"
                    : "text-[#77716E] hover:text-[#262321]"
                }`}
              >
                {billingCycle === "annual" && (
                  <motion.div
                    layoutId="billingToggleActive"
                    transition={{ type: "spring", stiffness: 450, damping: 30 }}
                    className="absolute inset-0 rounded-full bg-[#651E2C] shadow-xs z-[-1]"
                  />
                )}
                <span>{isAr ? "الدفع السنوي" : "Annual Billing"}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    billingCycle === "annual"
                      ? "bg-white/20 text-white"
                      : "bg-[#B86B76]/20 text-[#651E2C]"
                  }`}
                >
                  {isAr ? "شهران مجانًا" : "2 months free"}
                </span>
              </button>
            </div>

            {/* Plans are sold in Egyptian pounds only (Paymob): the price shown is the price charged. */}
          </div>

          {/* Active Tenant Workspace Quota Status */}
          {tenant && subInfo && (
            <div className="mx-auto mt-6 max-w-2xl rounded-2xl border border-[#B86B76]/30 bg-white p-4 text-start shadow-xs">
              <div className="flex items-center justify-between border-b border-[#E7D6C1] pb-3">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-emerald-600 animate-pulse" />
                  <span className="text-xs font-semibold text-[#262321]">
                    {isAr ? "المساحة النشطة:" : "Active Workspace:"}{" "}
                    <span className="font-bold text-[#651E2C]">{tenant.name}</span>
                  </span>
                  <Badge variant="outline" className="text-[10px] text-[#651E2C] border-[#B86B76]/40">
                    {tenant.plan.toUpperCase()}
                  </Badge>
                </div>
                {subInfo.is_trial && (
                  <span className="text-xs font-medium text-amber-700 font-mono">
                    {isAr ? `${subInfo.trial_remaining_days} يوم متبقي بالتجربة` : `${subInfo.trial_remaining_days} days trial left`}
                  </span>
                )}
              </div>
              <div className="mt-3 grid grid-cols-3 gap-3 text-xs">
                <div className="rounded-xl border border-[#E7D6C1] bg-[#FAF6F0] p-2.5">
                  <span className="text-[11px] text-[#77716E] block">{isAr ? "المستخدمون:" : "Users:"}</span>
                  <span className="font-bold font-mono text-[#262321]">
                    {subInfo.usage.current_users} / {subInfo.limits.max_users >= 999 ? "∞" : subInfo.limits.max_users}
                  </span>
                </div>
                <div className="rounded-xl border border-[#E7D6C1] bg-[#FAF6F0] p-2.5">
                  <span className="text-[11px] text-[#77716E] block">{isAr ? "الفروع:" : "Branches:"}</span>
                  <span className="font-bold font-mono text-[#262321]">
                    {subInfo.usage.current_branches} / {subInfo.limits.max_branches >= 999 ? "∞" : subInfo.limits.max_branches}
                  </span>
                </div>
                <div className="rounded-xl border border-[#E7D6C1] bg-[#FAF6F0] p-2.5">
                  <span className="text-[11px] text-[#77716E] block">{isAr ? "مبيعات الشهر:" : "Monthly Sales:"}</span>
                  <span className="font-bold font-mono text-[#262321]">
                    {subInfo.usage.current_monthly_sales}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 2. Three Editorial Luxury Pricing Cards matching Screen 6 (06_pricing.png) */}
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-3 items-stretch">
            {commercialPlans.map((plan) => {
              const isPopular = plan.popular;
              const isCurrent = isCurrentPlan(plan.id);

              const price = billingCycle === "annual" ? Math.round(plan.price_annual_egp / 12) : plan.price_egp;
              const symbol = "";
              const period = isAr ? "ج.م / شهر" : "EGP / mo";

              return (
                <div
                  key={plan.id}
                  className={`relative flex flex-col justify-between rounded-3xl transition-all duration-300 p-8 sm:p-10 ${
                    isPopular
                      ? "border-2 border-[#651E2C] bg-gradient-to-b from-[#F7E7E9] via-white to-white shadow-xl shadow-[#651E2C]/10 ring-1 ring-[#651E2C]"
                      : "border border-[#E7D6C1] bg-white/90 hover:bg-white shadow-xs"
                  }`}
                >
                  {isPopular && (
                    <div className="absolute -top-3.5 start-1/2 -translate-x-1/2 rounded-full bg-[#651E2C] px-4 py-1 text-[11px] font-bold text-white shadow-xs">
                      {isAr ? "الباقة الأكثر اختياراً" : "Most Popular Choice"}
                    </div>
                  )}

                  <div className="space-y-6">
                    <div>
                      <h2 className="font-display text-2xl font-bold text-[#262321]">
                        {isAr ? plan.name.split("(")[0].trim() : plan.en.name}
                      </h2>
                      <p className="mt-2 text-xs text-[#77716E] leading-relaxed">
                        {isAr ? plan.tagline : plan.en.tagline}
                      </p>
                    </div>

                    <div className="border-y border-[#E7D6C1] py-5">
                      <div className="flex items-baseline gap-1.5 overflow-hidden">
                        <span className="font-display text-4xl sm:text-5xl font-normal text-[#262321] font-mono">
                          {symbol}
                          <motion.span
                            key={price}
                            initial={priceChanged ? { opacity: 0, y: -8 } : false}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.25 }}
                            className="inline-block"
                          >
                            {price.toLocaleString("en-US")}
                          </motion.span>
                        </span>
                        <span className="text-xs font-semibold text-[#77716E]">
                          {period}
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-[#B86B76] font-medium font-mono">
                        {billingCycle === "annual"
                          ? (isAr ? "(تُدفع سنويًا: شهران مجانًا)" : "(Billed yearly: 2 months free)")
                          : (isAr ? "(فاتورة شهرية مرنة)" : "(Flexible monthly billing)")}
                      </p>
                    </div>

                    <div className="space-y-3">
                      <p className="text-xs font-bold uppercase tracking-wider text-[#77716E]">
                        {isAr ? "المزايا المتضمنة:" : "Included Capabilities:"}
                      </p>
                      <ul className="space-y-2.5 text-xs text-[#262321]">
                        {(isAr ? plan.features : plan.en.features).map((feat, idx) => (
                          <li key={idx} className="flex items-start gap-2.5 leading-relaxed">
                            <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full bg-[#FAF6F0] text-[#651E2C] border border-[#E7D6C1]">
                              <Check className="size-2.5 stroke-[3]" />
                            </span>
                            <span>{feat}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <div className="mt-8 pt-6 border-t border-[#E7D6C1]">
                    <MizanMagnetic className="w-full">
                      <Button
                        onClick={() => handlePlanClick(plan)}
                        size="lg"
                        className={`w-full rounded-xl py-3 text-xs font-bold transition-all ${
                          isPopular
                            ? "bg-[#651E2C] text-white hover:bg-[#521723] shadow-md"
                            : "border border-[#E7D6C1] bg-[#FAF6F0] text-[#262321] hover:bg-[#E7D6C1]"
                        }`}
                      >
                        {isCurrent
                          ? isAr
                            ? "باقاتك الحالية المفعلة"
                            : "Current Active Plan"
                          : user
                          ? isAr
                            ? "ترقية واشتراك فوري"
                            : "Upgrade & Subscribe"
                          : ownerPanel
                          ? isAr
                            ? "اختر الباقة من لوحتك"
                            : "Choose it in your panel"
                          : isAr
                          ? "ابدأ الفترة التجريبية"
                          : "Start 14-Day Free Trial"}
                      </Button>
                    </MizanMagnetic>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 3. Detailed Feature Comparison Matrix */}
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="text-center space-y-2 mb-8">
            <h2 className="font-display text-2xl sm:text-3xl font-normal text-[#262321]">
              {isAr ? "جدول المقارنة التفصيلي للميزات" : "Comprehensive Feature Comparison"}
            </h2>
            <p className="text-xs text-[#77716E]">
              {isAr
                ? "مقارنة دقيقة لجميع الصلاحيات والحصص والخيارات المعمارية"
                : "Exact comparison of quotas, operational permissions, and infrastructure"}
            </p>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-[#E7D6C1] bg-white shadow-xs">
            <table className="w-full text-start text-xs text-[#262321]">
              <thead>
                <tr className="border-b border-[#E7D6C1] bg-[#FAF6F0] text-[#77716E]">
                  <th className="py-4 px-6 text-start font-bold uppercase tracking-wider">
                    {isAr ? "الميزة / القدرة" : "Feature / Capability"}
                  </th>
                  <th className="py-4 px-4 text-center font-bold">{isAr ? "البداية (Starter)" : "Starter"}</th>
                  <th className="py-4 px-4 text-center font-bold text-[#651E2C] bg-[#651E2C]/5">
                    {isAr ? "المحترفين (Pro)" : "Pro"}
                  </th>
                  <th className="py-4 px-4 text-center font-bold">{isAr ? "المؤسسات (Enterprise)" : "Enterprise"}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E7D6C1]">
                {comparisonFeatures.map((row, idx) => (
                  <tr key={idx} className="hover:bg-[#FAF6F0]/50 transition-colors">
                    <td className="py-3.5 px-6 font-medium text-[#262321]">
                      {isAr ? row.nameAr : row.nameEn}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      {typeof row.starter === "boolean" ? (
                        row.starter ? (
                          <Check className="mx-auto size-4 text-[#27835C] stroke-[2.5]" />
                        ) : (
                          <span className="text-[#77716E]">—</span>
                        )
                      ) : (
                        <span className="font-mono">{row.starter}</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-center bg-[#651E2C]/5">
                      {typeof row.pro === "boolean" ? (
                        row.pro ? (
                          <Check className="mx-auto size-4 text-[#651E2C] stroke-[2.5]" />
                        ) : (
                          <span className="text-[#77716E]">—</span>
                        )
                      ) : (
                        <span className="font-mono font-bold text-[#651E2C]">{row.pro}</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-center">
                      {typeof row.enterprise === "boolean" ? (
                        row.enterprise ? (
                          <Check className="mx-auto size-4 text-[#27835C] stroke-[2.5]" />
                        ) : (
                          <span className="text-[#77716E]">—</span>
                        )
                      ) : (
                        <span className="font-mono font-semibold">{row.enterprise}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 4. Frequently Asked Questions (FAQ Accordions) */}
        <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8 space-y-6">
          <div className="text-center space-y-2 mb-8">
            <h2 className="font-display text-2xl sm:text-3xl font-normal text-[#262321]">
              {isAr ? "الأسئلة الشائعة حول الباقات والسداد" : "Frequently Asked Questions"}
            </h2>
            <p className="text-xs text-[#77716E]">
              {isAr ? "إجابات شفافة عن الفوترة والتجديد وإلغاء الاشتراك" : "Transparent answers about billing, upgrades, and cancellations"}
            </p>
          </div>

          <div className="space-y-3">
            {PRICING_FAQS.map((faq, idx) => {
              const isOpen = openFaq === idx;
              return (
                <div
                  key={idx}
                  className="rounded-xl border border-[#E7D6C1] bg-white overflow-hidden transition-all shadow-xs"
                >
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    aria-controls={`pricing-faq-${idx}`}
                    onClick={() => setOpenFaq(isOpen ? null : idx)}
                    className="w-full flex items-center justify-between p-5 text-start font-semibold text-xs sm:text-sm text-[#262321] hover:text-[#651E2C] transition-colors"
                  >
                    <span>{isAr ? faq.qAr : faq.qEn}</span>
                    <ChevronDown
                      className={`size-4 text-[#77716E] transition-transform duration-200 shrink-0 ms-2 ${
                        isOpen ? "rotate-180 text-[#651E2C]" : ""
                      }`}
                    />
                  </button>
                  {/* In the page even when closed: the answers are the FAQ structured data's text. */}
                  <div
                    id={`pricing-faq-${idx}`}
                    hidden={!isOpen}
                    className="px-5 pb-5 text-xs text-[#77716E] leading-relaxed border-t border-[#E7D6C1]/50 pt-3"
                  >
                    {isAr ? faq.aAr : faq.aEn}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 5. Final CTA Banner */}
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="rounded-3xl bg-[#35151D] p-8 sm:p-12 text-center text-[#F5EBDD] space-y-6 shadow-xl relative overflow-hidden">
            <div className="relative z-10 space-y-3">
              <h2 className="font-display text-2xl sm:text-4xl font-normal tracking-tight text-white">
                {isAr ? "هل تحتاج إلى استشارة متخصصة لمؤسستك؟" : "Need custom enterprise requirements?"}
              </h2>
              <p className="mx-auto max-w-xl text-xs sm:text-sm text-[#E7D6C1] font-body leading-relaxed">
                {isAr
                  ? "تواصل معنا لنخطط معك الاستضافة المخصصة أو التشغيل داخل منشأتك ونقل بياناتك الحالية."
                  : "Talk to us about a dedicated server, running Mizan on your own premises, and bringing your existing data over."}
              </p>
              <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
                <Button
                  render={<SiteLink to={sitePath("/contact")} />}
                  nativeButton={false}
                  size="lg"
                  className="bg-[#651E2C] text-white hover:bg-[#8A293B] rounded-full px-6 py-2.5 text-xs font-bold"
                >
                  {isAr ? "تواصل معنا" : "Contact us"}
                </Button>
                {ownerPanel ? (
                  <Button
                    onClick={() => ownerPanel("/")}
                    size="lg"
                    variant="outline"
                    className="border-[#E7D6C1]/30 bg-transparent text-[#F5EBDD] hover:bg-white/10 rounded-full px-6 py-2.5 text-xs font-bold"
                  >
                    {isAr ? "العودة إلى لوحتك" : "Back to your panel"}
                  </Button>
                ) : (
                  <Button
                    render={<SiteLink to={sitePath("/signup")} />}
                    nativeButton={false}
                    size="lg"
                    variant="outline"
                    className="border-[#E7D6C1]/30 bg-transparent text-[#F5EBDD] hover:bg-white/10 rounded-full px-6 py-2.5 text-xs font-bold"
                  >
                    {isAr ? "تجربة مجانية فورية" : "Start 14-Day Free Trial"}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Checkout and Payment Simulation Modal */}
    </Layout>
  );
}
