import { useTranslation } from "@/i18n";
import { Link } from "@app/seo/LocaleLink";
import { setConsent, useConsentBanner } from "./consent";

/**
 * Asks before Google Analytics loads (only when VITE_GA4_ID is set). Not a modal: the page stays
 * usable, nothing is measured by Google until "Accept".
 */
export function ConsentBanner() {
  const { open } = useConsentBanner();
  const { locale } = useTranslation();
  const isAr = locale === "ar";
  if (!open) return null;
  return (
    <section
      role="region"
      aria-labelledby="consent-title"
      dir={isAr ? "rtl" : "ltr"}
      className={`fixed inset-x-3 bottom-3 z-[60] mx-auto max-w-xl rounded-2xl border border-[#DECFC0] bg-[#FFFFFF] p-4 text-[#262321] shadow-xl sm:p-5 ${
        isAr ? "font-body" : "font-sans"
      }`}
    >
      <h2 id="consent-title" className="text-sm font-semibold">
        {isAr ? "هل تسمح بإحصاءات Google Analytics؟" : "Allow Google Analytics?"}
      </h2>
      <p className="mt-1.5 text-xs leading-relaxed text-[#55504D]">
        {isAr
          ? "نستخدمه لنعرف أي الصفحات تفيد زوارنا، ويضع ملفات تعريف ارتباط من Google. بدون موافقتك لا يُحمَّل أبدًا، ويكتفي الموقع بعدّاد زيارات خاص بنا بلا ملفات تعريف ارتباط ولا بيانات شخصية."
          : "It helps us see which pages are useful, and it sets Google cookies. Without your consent it never loads; the site only keeps its own visit counts, with no cookies and no personal data."}{" "}
        <Link to="/privacy" className="font-medium text-[#651E2C] underline underline-offset-2">
          {isAr ? "سياسة الخصوصية" : "Privacy policy"}
        </Link>
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setConsent("granted")}
          className="min-h-[40px] rounded-full bg-[#651E2C] px-5 text-xs font-semibold text-[#FAF6F0] hover:bg-[#521723] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#651E2C]"
        >
          {isAr ? "أوافق" : "Accept"}
        </button>
        <button
          type="button"
          onClick={() => setConsent("denied")}
          className="min-h-[40px] rounded-full border border-[#DECFC0] bg-[#FAF6F0] px-5 text-xs font-semibold text-[#262321] hover:bg-[#EFE4D6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#651E2C]"
        >
          {isAr ? "لا أوافق" : "Decline"}
        </button>
      </div>
    </section>
  );
}
