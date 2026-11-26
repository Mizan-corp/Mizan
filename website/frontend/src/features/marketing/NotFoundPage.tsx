import { ArrowLeft, ArrowRight } from "lucide-react";
import { useTranslation } from "@/i18n";
import { Link } from "@app/seo/LocaleLink";
import { MarketingLayout } from "./MarketingLayout";

/**
 * "Page not found". nginx sends it with status 404 for any address that isn't a page
 * (deploy/server/nginx.conf), and the router shows it for the same addresses in the browser.
 */
export default function NotFoundPage() {
  const { locale } = useTranslation();
  const isAr = locale === "ar";
  const Arrow = isAr ? ArrowLeft : ArrowRight;
  const links = [
    { to: "/product", label: isAr ? "المنتج" : "Product" },
    { to: "/features", label: isAr ? "المميزات" : "Features" },
    { to: "/pricing", label: isAr ? "الأسعار" : "Pricing" },
    { to: "/docs", label: isAr ? "دليل الاستخدام" : "Documentation" },
    { to: "/contact", label: isAr ? "تواصل معنا" : "Contact us" },
  ];
  return (
    <MarketingLayout notFound>
      <section className="bg-[#FAF6F0] py-20 sm:py-28">
        <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
          <p className="font-mono text-sm font-semibold tracking-widest text-[#B86B76]">404</p>
          <h1 className={`mt-3 text-4xl font-normal leading-tight text-[#262321] sm:text-5xl ${isAr ? "font-serif-ar" : "font-serif-en"}`}>
            {isAr ? "لم نجد هذه الصفحة" : "We couldn't find this page"}
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-sm leading-relaxed text-[#55504D] sm:text-base">
            {isAr
              ? "ربما تغيّر عنوانها أو كُتب الرابط بشكل خاطئ. ابدأ من الصفحة الرئيسية، أو اختر وجهتك:"
              : "Its address may have changed, or the link has a typo. Start from the home page, or pick where to go:"}
          </p>
          <div className="mt-8">
            <Link
              to="/"
              className="inline-flex min-h-[44px] items-center gap-2 rounded-full bg-[#651E2C] px-6 text-sm font-semibold text-[#FAF6F0] hover:bg-[#521723] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#651E2C]"
            >
              <span>{isAr ? "الصفحة الرئيسية" : "Home page"}</span>
              <Arrow className="h-4 w-4" aria-hidden="true" />
            </Link>
          </div>
          <nav aria-label={isAr ? "صفحات مقترحة" : "Suggested pages"} className="mt-8">
            <ul className="flex flex-wrap items-center justify-center gap-2">
              {links.map((l) => (
                <li key={l.to}>
                  <Link
                    to={l.to}
                    className="inline-flex min-h-[40px] items-center rounded-full border border-[#DECFC0] bg-white px-4 text-xs font-medium text-[#262321] hover:border-[#651E2C] hover:text-[#651E2C]"
                  >
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </section>
    </MarketingLayout>
  );
}
