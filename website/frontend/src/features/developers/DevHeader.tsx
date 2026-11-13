/** The developer platform's top bar (home and sign-in pages; the docs and portal have their own). */
import { Link } from "react-router-dom";
import { MizanLogo } from "@/components/MizanLogo";
import { appUrl } from "@/lib/urls";
import { useDevI18n } from "./i18n";
import { devPath } from "./paths";
import { useDeveloperToken } from "./session";

/** "العربية" / "English": the platform's language switch. */
export function LanguageToggle({ className = "" }: { className?: string }) {
  const { isAr, toggle } = useDevI18n();
  return (
    <button type="button" onClick={toggle} lang={isAr ? "en" : "ar"}
            className={`rounded-full px-3 py-1.5 text-sm text-[#77716E] hover:bg-white hover:text-[#262321] ${className}`}>
      {isAr ? "English" : "العربية"}
    </button>
  );
}

export function DevHeader() {
  const signedIn = !!useDeveloperToken();
  const { t } = useDevI18n();
  return (
    <header className="sticky top-0 z-40 border-b border-[#E7D6C1] bg-[#FAF6F0]/95 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link to={devPath("/")} className="flex items-center gap-2.5">
          <MizanLogo size="sm" showWordmark />
          <span className="hidden rounded-full bg-[#651E2C]/10 px-2.5 py-0.5 text-[11px] font-bold text-[#651E2C] sm:inline">
            {t("Developers", "للمطورين")}
          </span>
        </Link>
        <nav aria-label={t("Developer links", "روابط المطورين")} className="flex items-center gap-1 text-sm">
          <Link to={devPath("/docs")} className="rounded-full px-3 py-1.5 font-semibold text-[#262321] hover:bg-white">{t("Docs", "التوثيق")}</Link>
          <a href={appUrl("website", "/")} className="hidden rounded-full px-3 py-1.5 text-[#77716E] hover:bg-white md:inline">{t("Mizan", "موقع ميزان")}</a>
          <LanguageToggle />
          <Link to={devPath(signedIn ? "/portal" : "/login")}
                className="rounded-full bg-[#651E2C] px-4 py-1.5 font-bold text-white shadow-xs hover:bg-[#521723]">
            {signedIn ? t("Portal", "البوابة") : t("Sign in", "دخول المطورين")}
          </Link>
        </nav>
      </div>
    </header>
  );
}
