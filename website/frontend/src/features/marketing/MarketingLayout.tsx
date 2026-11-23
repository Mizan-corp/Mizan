import { useState, useEffect } from "react";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { Link } from "@app/seo/LocaleLink";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import {
  Menu,
  X,
  Globe,
  Search,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  Lock,
  ChevronDown,
} from "lucide-react";
import { BUSINESS } from "@app/features/legal/business";
import { useTranslation } from "@/i18n";
import { alternatePath, basePath, withLang } from "@app/seo/paths";
import { useEntrance } from "@app/lib/entrance";
import { ANALYTICS_CONFIGURABLE, reopenConsent } from "@app/analytics/consent";
import { MizanLogo } from "@/components/MizanLogo";
import { SmoothScroll } from "@/components/SmoothScroll";
import { MizanReadingProgress } from "@/components/motion/MizanReadingProgress";
import { MizanCursor } from "@/components/motion/MizanCursor";
import { MizanMagnetic } from "@/components/motion/MizanMagnetic";
import { pageTransitionVariant } from "@/lib/motion";
import { appUrl } from "@/lib/urls";
import { openWithSession } from "@/lib/handoff";
import { useOwner } from "@app/lib/ownerSession";
import { signOutEverywhere } from "@app/features/session/SessionRoutes";

interface MarketingLayoutProps {
  children?: React.ReactNode;
  /** The "page not found" page: its language switch leads to the other language's home. */
  notFound?: boolean;
}

export function MarketingLayout({ children, notFound = false }: MarketingLayoutProps) {
  const location = useLocation();
  const owner = useOwner();
  const { locale, dir } = useTranslation();
  const shouldReduceMotion = useReducedMotion();
  const pageFrom = useEntrance("initial" as const);
  const current = basePath(location.pathname);
  // The other language's page (or its home). The choice is also remembered for the owner panel.
  const otherLang = locale === "ar" ? "en" : "ar";
  const switchTo = notFound ? withLang("/", otherLang) : alternatePath(location.pathname, otherLang);
  const rememberLang = () => {
    try {
      localStorage.setItem("mizan.locale", otherLang);
    } catch {
      /* not remembered */
    }
  };

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState<string | null>(null);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
    setDropdownOpen(null);
  }, [location.pathname]);

  const isAr = locale === "ar";
  const toPanel = () => owner && openWithSession("owner", "/", owner.token);

  // Navigation Links matching Image 1 (EN) and Image 2 (AR)
  const navLinksEn = [
    {
      href: "/product",
      label: "Product",
      hasDropdown: true,
      items: [
        { href: "/product", label: "Overview & Architecture" },
        { href: "/features", label: "Core Modules & Features" },
        { href: "/demo", label: "Live System Demo (Light & Dark)" },
        { href: "/docs", label: "Developer Documentation" },
      ],
    },
    {
      href: "/industries",
      label: "Solutions",
      hasDropdown: true,
      items: [
        { href: "/industries", label: "Retail & E-commerce" },
        { href: "/industries", label: "Manufacturing & Supply" },
        { href: "/industries", label: "Services & Healthcare" },
      ],
    },
    { href: "/demo", label: "Live Demo", hasDropdown: false },
    { href: "/pricing", label: "Pricing", hasDropdown: false },
    {
      href: "/blog",
      label: "Resources",
      hasDropdown: true,
      items: [
        { href: "/blog", label: "Editorial Blog & Insights" },
        { href: "/docs", label: "Documentation Portal" },
        { href: "/contact", label: "Help & Technical Support" },
      ],
    },
    { href: "/about", label: "About", hasDropdown: false },
  ];

  const navLinksAr = [
    {
      href: "/product",
      label: "المنتج",
      hasDropdown: true,
      items: [
        { href: "/product", label: "نظرة عامة والبنية التحتية" },
        { href: "/features", label: "الوحدات والمميزات الأساسية" },
        { href: "/demo", label: "معاينة النظام الحي (فاتح وداكن)" },
        { href: "/docs", label: "دليل المطور والتوثيق" },
      ],
    },
    {
      href: "/demo",
      label: "عرض حي",
      hasDropdown: false,
    },
    {
      href: "/industries",
      label: "القطاعات",
      hasDropdown: true,
      items: [
        { href: "/industries", label: "التجزئة والتجارة الإلكترونية" },
        { href: "/industries", label: "التصنيع والتوريد" },
        { href: "/industries", label: "الخدمات والاستشارات والرعاية" },
      ],
    },
    { href: "/pricing", label: "الأسعار", hasDropdown: false },
    { href: "/about", label: "من نحن", hasDropdown: false },
    { href: "/blog", label: "المدونة", hasDropdown: false },
  ];

  const currentNav = isAr ? navLinksAr : navLinksEn;

  return (
    <SmoothScroll>
      <MizanReadingProgress color="#B86B76" height={2.5} />
      <MizanCursor />
      <div
        dir={dir}
        className={`min-h-screen flex flex-col bg-[#FAF6F0] text-[#262321] transition-colors duration-150 selection:bg-[#651E2C] selection:text-[#FAF6F0] ${
          isAr ? "font-body" : "font-sans"
        }`}
      >
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:start-3 focus:z-[70] focus:rounded-full focus:bg-[#651E2C] focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-[#FAF6F0]"
      >
        {isAr ? "تخطَّ إلى المحتوى" : "Skip to content"}
      </a>
      {/* 1. Top Navigation Bar — Warm Ivory Light background matching design */}
      <header className="sticky top-0 z-50 w-full border-b border-[#E6DCD2] bg-[#FAF6F0]/95 backdrop-blur-md">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Brand Logo */}
          <div className="flex items-center gap-3">
            <Link to="/" className="flex items-center py-2" aria-label={isAr ? "ميزان ERP: الصفحة الرئيسية" : "Mizan ERP: home"}>
              <MizanLogo size="lg" locale={locale} />
            </Link>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden lg:flex items-center gap-1.5" aria-label={isAr ? "القائمة الرئيسية" : "Main navigation"}>
            {currentNav.map((link) => {
              const isActive = current === link.href;

              if (link.hasDropdown && link.items) {
                const isOpen = dropdownOpen === link.label;
                return (
                  <div
                    key={link.label}
                    className="relative"
                    onMouseEnter={() => setDropdownOpen(link.label)}
                    onMouseLeave={() => setDropdownOpen(null)}
                  >
                    <Link
                      to={link.href}
                      className={`inline-flex items-center gap-1 px-3.5 py-2 text-sm font-medium rounded-full transition-colors ${
                        isActive
                          ? "text-[#651E2C] font-semibold"
                          : "text-[#55504D] hover:text-[#262321] hover:bg-[#EFE4D6]/60"
                      }`}
                    >
                      <span>{link.label}</span>
                      <ChevronDown
                        className={`h-3.5 w-3.5 transition-transform duration-200 ${
                          isOpen ? "rotate-180" : ""
                        }`}
                      />
                    </Link>

                    {/* Elegant Dropdown Card */}
                    <AnimatePresence>
                      {isOpen && (
                        <motion.div
                          initial={shouldReduceMotion ? false : { opacity: 0, y: 8 }}
                          animate={shouldReduceMotion ? { opacity: 1 } : { opacity: 1, y: 0 }}
                          exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 4 }}
                          transition={{ duration: 0.15 }}
                          className="absolute top-full start-0 mt-1 w-64 rounded-xl border border-[#E6DCD2] bg-[#FFFFFF] p-2 shadow-lg z-50"
                        >
                          {link.items.map((subItem) => (
                            <Link
                              key={subItem.href + subItem.label}
                              to={subItem.href}
                              className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-[#55504D] hover:text-[#651E2C] hover:bg-[#FAF6F0] transition-colors"
                            >
                              <span className="w-1.5 h-1.5 rounded-full bg-[#B86B76]/50" />
                              <span>{subItem.label}</span>
                            </Link>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              }

              return (
                <Link
                  key={link.href}
                  to={link.href}
                  className={`px-3.5 py-2 text-sm font-medium rounded-full transition-colors ${
                    isActive
                      ? "text-[#651E2C] font-semibold"
                      : "text-[#55504D] hover:text-[#262321] hover:bg-[#EFE4D6]/60"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>

          {/* Right Action Utilities (Language Switcher + Sign In + Get Started) */}
          <div className="flex items-center gap-3">
            {/* Search Icon button (Matching Arabic mockup) */}
            <Link
              to="/docs"
              className="hidden sm:flex h-9 w-9 items-center justify-center rounded-full text-[#77716E] hover:text-[#262321] hover:bg-[#EFE4D6]/70 transition-colors"
              title={isAr ? "بحث في التوثيق" : "Search docs"}
              aria-label={isAr ? "البحث في دليل الاستخدام" : "Search the documentation"}
            >
              <Search className="h-4 w-4" />
            </Link>

            {/* Language switcher: the same page in the other language (ADR-016) */}
            <RouterLink
              to={switchTo}
              onClick={rememberLang}
              hrefLang={otherLang}
              lang={otherLang}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#DECFC0] bg-[#FAF6F0] text-xs font-medium text-[#262321] hover:bg-[#EFE4D6] transition-colors"
              title={isAr ? "Switch to English" : "التبديل إلى العربية"}
            >
              <Globe className="h-3.5 w-3.5 text-[#651E2C]" aria-hidden="true" />
              <span>{isAr ? "English" : "العربية"}</span>
            </RouterLink>

            {/* Signed-in owner: back to the owner panel + sign out; otherwise sign in + get started */}
            {owner ? (
              <div className="flex items-center gap-2 sm:gap-3">
                <button
                  type="button"
                  onClick={signOutEverywhere}
                  className="hidden sm:inline-flex px-3 py-1.5 text-xs sm:text-sm font-medium text-[#55504D] hover:text-[#262321] transition-colors"
                >
                  {isAr ? "تسجيل الخروج" : "Sign Out"}
                </button>
                <MizanMagnetic>
                  <button
                    type="button"
                    onClick={toPanel}
                    className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-full bg-[#651E2C] text-[#FAF6F0] text-xs sm:text-sm font-semibold hover:bg-[#521723] shadow-sm transition-all hover:scale-[1.02]"
                  >
                    <span>{isAr ? "العودة إلى لوحتك" : "Back to your panel"}</span>
                    {isAr ? <ArrowLeft className="h-3.5 w-3.5" /> : <ArrowRight className="h-3.5 w-3.5" />}
                  </button>
                </MizanMagnetic>
              </div>
            ) : (
              <div className="flex items-center gap-2 sm:gap-3">
                <a
                  href={appUrl("owner", "/login")}
                  className="hidden sm:inline-flex px-3 py-1.5 text-xs sm:text-sm font-medium text-[#55504D] hover:text-[#262321] transition-colors"
                >
                  {isAr ? "تسجيل الدخول" : "Sign In"}
                </a>

                <MizanMagnetic>
                  <Link
                    to="/signup"
                    className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-full bg-[#651E2C] text-[#FAF6F0] text-xs sm:text-sm font-semibold hover:bg-[#521723] shadow-sm transition-all hover:scale-[1.02]"
                  >
                    <span>{isAr ? "ابدأ الآن" : "Get Started"}</span>
                    {isAr ? <ArrowLeft className="h-3.5 w-3.5" /> : <ArrowRight className="h-3.5 w-3.5" />}
                  </Link>
                </MizanMagnetic>
              </div>
            )}

            {/* Mobile Hamburger Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#DECFC0] text-[#55504D] hover:bg-[#EFE4D6] lg:hidden"
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer Sheet */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={shouldReduceMotion ? false : { height: 0, opacity: 0 }}
              animate={shouldReduceMotion ? { opacity: 1 } : { height: "auto", opacity: 1 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden border-b border-[#DECFC0] bg-[#FAF6F0] px-4 py-5 lg:hidden"
            >
              <div className="flex flex-col space-y-2">
                {currentNav.map((link) => {
                  const isActive = current === link.href;
                  return (
                    <Link
                      key={link.href}
                      to={link.href}
                      className={`rounded-lg px-3.5 py-2.5 text-sm font-medium transition-colors min-h-[44px] flex items-center ${
                        isActive
                          ? "bg-[#651E2C] text-[#FAF6F0]"
                          : "text-[#55504D] hover:bg-[#EFE4D6] hover:text-[#262321]"
                      }`}
                    >
                      {link.label}
                    </Link>
                  );
                })}

                <div className="pt-3 border-t border-[#DECFC0] flex flex-col gap-2.5">
                  <div className="flex items-center justify-between px-2 py-1">
                    <span className="text-xs text-[#77716E]">{isAr ? "اللغة" : "Language"}</span>
                    <RouterLink
                      to={switchTo}
                      onClick={rememberLang}
                      hrefLang={otherLang}
                      lang={otherLang}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#DECFC0] bg-white text-xs font-medium text-[#262321]"
                    >
                      <Globe className="h-3.5 w-3.5 text-[#651E2C]" aria-hidden="true" />
                      <span>{isAr ? "English" : "العربية"}</span>
                    </RouterLink>
                  </div>

                  {owner ? (
                    <>
                      <button
                        type="button"
                        onClick={signOutEverywhere}
                        className="flex min-h-[44px] items-center justify-center rounded-full border border-[#DECFC0] bg-white text-xs font-semibold text-[#262321] hover:bg-[#EFE4D6]"
                      >
                        {isAr ? "تسجيل الخروج" : "Sign Out"}
                      </button>
                      <button
                        type="button"
                        onClick={toPanel}
                        className="flex min-h-[44px] items-center justify-center rounded-full bg-[#651E2C] text-xs font-semibold text-[#FAF6F0] hover:bg-[#521723]"
                      >
                        {isAr ? "العودة إلى لوحتك" : "Back to your panel"}
                      </button>
                    </>
                  ) : (
                    <>
                      <a
                        href={appUrl("owner", "/login")}
                        className="flex min-h-[44px] items-center justify-center rounded-full border border-[#DECFC0] bg-white text-xs font-semibold text-[#262321] hover:bg-[#EFE4D6]"
                      >
                        {isAr ? "تسجيل الدخول للمنظومة" : "Sign In to Mizan"}
                      </a>
                      <Link
                        to="/signup"
                        className="flex min-h-[44px] items-center justify-center rounded-full bg-[#651E2C] text-xs font-semibold text-[#FAF6F0] hover:bg-[#521723]"
                      >
                        {isAr ? "ابدأ تجربة مجانية (14 يوماً)" : "Start Free Trial (14 Days)"}
                      </Link>
                    </>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* 2. Main Page Content with Editorial Page Transition */}
      <motion.main
        id="main-content"
        key={location.pathname}
        variants={pageTransitionVariant}
        initial={pageFrom}
        animate="animate"
        className="flex-1"
      >
        {children}
      </motion.main>

      {/* 3. Official Deep Merlot Luxury Footer (#35151D) matching Image 4 */}
      <footer className="border-t border-[#481822] bg-[#35151D] text-[#E7D6C1]">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8 sm:py-16">
          <div className="grid grid-cols-1 gap-10 md:grid-cols-2 lg:grid-cols-5">
            {/* Col 1 & 2: Brand Identity & Equilibrium Philosophy */}
            <div className="lg:col-span-2 space-y-4">
              <Link to="/" className="inline-flex items-center" aria-label={isAr ? "ميزان ERP: الصفحة الرئيسية" : "Mizan ERP: home"}>
                <MizanLogo size="lg" theme="dark" locale={locale} />
              </Link>
              <p className="text-xs sm:text-sm leading-relaxed text-[#E7D6C1]/80 max-w-sm">
                {isAr
                  ? "منصة ميزان السحابية المتكاملة لإدارة العمليات المالية والتشغيلية والمخازن. صُممت لتحقيق التوازن الدقيق والكفاءة المؤسسية العالية."
                  : "Mizan is an enterprise multi-tenant ERP platform uniting financial, administrative, and operational activities into one balanced ecosystem."}
              </p>

              {/* Security & Reliability Badges */}
              <div className="flex flex-wrap items-center gap-3 pt-2 text-xs text-[#E7D6C1]/90">
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#48151F] border border-white/10">
                  <ShieldCheck className="h-3.5 w-3.5 text-[#27835C]" />
                  {isAr ? "مدفوعات آمنة عبر Paymob" : "Payments secured by Paymob"}
                </span>
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[#48151F] border border-white/10">
                  <Lock className="h-3.5 w-3.5 text-[#B86B76]" />
                  {isAr ? "تشفير TLS 1.3" : "TLS 1.3 Encrypted"}
                </span>
              </div>
            </div>

            {/* Col 3: Core Platform Modules */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#FAF6F0] mb-4">
                {isAr ? "منظومة البرامج" : "Platform Modules"}
              </h3>
              <ul className="space-y-2.5 text-xs text-[#E7D6C1]/80">
                <li>
                  <Link to="/features" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "المحاسبة والمالية المتقدمة" : "Accounting & Finance"}
                  </Link>
                </li>
                <li>
                  <Link to="/features" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "إدارة المبيعات وفواتير POS" : "Sales & POS Terminal"}
                  </Link>
                </li>
                <li>
                  <Link to="/features" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "المخازن والوحدات المركبة" : "Inventory & Warehouses"}
                  </Link>
                </li>
                <li>
                  <Link to="/features" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "المشتريات وإدارة الموردين" : "Purchases & Procurement"}
                  </Link>
                </li>
                <li>
                  <Link to="/features" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "الموارد البشرية والرواتب HR" : "HR & Payroll Management"}
                  </Link>
                </li>
                <li>
                  <Link to="/features" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "المشاريع والأتمتة الذكية" : "Projects & Workflow Automation"}
                  </Link>
                </li>
              </ul>
            </div>

            {/* Col 4: Industry Solutions */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#FAF6F0] mb-4">
                {isAr ? "قطاعات الأعمال" : "Industry Solutions"}
              </h3>
              <ul className="space-y-2.5 text-xs text-[#E7D6C1]/80">
                <li>
                  <Link to="/industries" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "تجارة التجزئة والمعارض" : "Retail & Showrooms"}
                  </Link>
                </li>
                <li>
                  <Link to="/industries" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "التوزيع والتجارة بالجملة" : "Wholesale & Distribution"}
                  </Link>
                </li>
                <li>
                  <Link to="/industries" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "التصنيع وتتبع خطوط الإنتاج" : "Manufacturing & BOM"}
                  </Link>
                </li>
                <li>
                  <Link to="/industries" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "الخدمات المهنية والاستشارات" : "Professional Services"}
                  </Link>
                </li>
                <li>
                  <Link to="/industries" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "المقاولات ومواد البناء" : "Contracting & Construction"}
                  </Link>
                </li>
                <li>
                  <Link to="/industries" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "الضيافة والمطاعم" : "Hospitality & Restaurants"}
                  </Link>
                </li>
              </ul>
            </div>

            {/* Col 5: Documentation & Help */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#FAF6F0] mb-4">
                {isAr ? "التوثيق والمساعدة" : "Documentation & Help"}
              </h3>
              <ul className="space-y-2.5 text-xs text-[#E7D6C1]/80">
                <li>
                  <Link to="/docs" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "دليل البدء السريع" : "Quickstart Guide"}
                  </Link>
                </li>
                <li>
                  <Link to="/docs" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "مرجع REST API الموثق" : "REST API Reference"}
                  </Link>
                </li>
                <li>
                  <Link to="/pricing" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "باقات واشتراكات ميزان" : "Plans & Pricing"}
                  </Link>
                </li>
                <li>
                  <Link to="/contact" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "طلب عرض توضيحي (Demo)" : "Request a Live Demo"}
                  </Link>
                </li>
                <li>
                  <Link to="/about" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "عن الشركة وفلسفة العمل" : "About Mizan"}
                  </Link>
                </li>
                <li>
                  <Link to="/blog" className="hover:text-[#FAF6F0] transition-colors">
                    {isAr ? "مدونة رؤى الأعمال" : "Editorial Blog"}
                  </Link>
                </li>
              </ul>
            </div>
          </div>

          {/* Bottom Bar — Hairline top border in Merlot tone */}
          <div className="mt-12 flex flex-col items-center justify-between border-t border-white/10 pt-6 text-xs text-[#E7D6C1]/70 sm:flex-row gap-3">
            <div>
              © {__BUILD_YEAR__} {isAr ? `ميزان ERP · ${BUSINESS.seller.ar}، ${BUSINESS.city.ar}. جميع الحقوق محفوظة.` : `Mizan ERP · ${BUSINESS.seller.en}, ${BUSINESS.city.en}. All rights reserved.`}
            </div>
            <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
              <Link to="/about" className="hover:text-[#FAF6F0] transition-colors">
                {isAr ? "عن المنصة" : "About"}
              </Link>
              <Link to="/pricing" className="hover:text-[#FAF6F0] transition-colors">
                {isAr ? "الأسعار" : "Pricing"}
              </Link>
              <Link to="/contact" className="hover:text-[#FAF6F0] transition-colors">
                {isAr ? "اتصل بنا" : "Contact"}
              </Link>
              <Link to="/terms" className="hover:text-[#FAF6F0] transition-colors">
                {isAr ? "شروط الاستخدام" : "Terms"}
              </Link>
              <Link to="/privacy" className="hover:text-[#FAF6F0] transition-colors">
                {isAr ? "سياسة الخصوصية" : "Privacy Policy"}
              </Link>
              <Link to="/refund-policy" className="hover:text-[#FAF6F0] transition-colors">
                {isAr ? "الاسترداد والإلغاء" : "Refunds"}
              </Link>
              {ANALYTICS_CONFIGURABLE && (
                <button type="button" onClick={reopenConsent} className="hover:text-[#FAF6F0] transition-colors">
                  {isAr ? "إعدادات الإحصاءات" : "Analytics settings"}
                </button>
              )}
            </div>
          </div>
        </div>
      </footer>
    </div>
  </SmoothScroll>
  );
}

export default MarketingLayout;
