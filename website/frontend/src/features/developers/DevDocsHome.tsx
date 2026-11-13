/** The developer docs' index (dev.allmizan.live/docs). */
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { devDocSections } from "./devDocs";
import { useDevI18n } from "./i18n";
import { devPath } from "./paths";

export default function DevDocsHome() {
  const { t, locale } = useDevI18n();
  return (
    <div className="space-y-10 text-[#262321]">
      <div className="space-y-3 border-b border-[#E7D6C1] pb-6">
        <h1 className="font-display text-3xl tracking-tight sm:text-4xl">{t("Developer docs", "توثيق المطورين")}</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-[#77716E]">
          {t("How to build a module for Mizan, sign it, and connect it to your server. Start with the ", "كيف تبني وحدة لميزان، توقّعها، وتربطها بخادمك. ابدأ بـ")}
          <Link to={devPath("/docs/quickstart")} className="font-semibold text-[#651E2C] hover:underline">{t("quickstart", "البدء السريع")}</Link>.
        </p>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        {devDocSections(locale).map((sec) => (
          <section key={sec.id} className="space-y-3 rounded-2xl border border-[#E7D6C1] bg-white p-6 shadow-xs">
            <h2 className="border-b border-[#E7D6C1] pb-2 font-display text-lg font-bold">{sec.title}</h2>
            <ul className="space-y-2.5">
              {sec.items.map((a) => (
                <li key={a.slug}>
                  <Link to={devPath(`/docs/${a.slug}`)} className="group flex items-start justify-between gap-3">
                    <span>
                      <span className="block text-sm font-semibold group-hover:text-[#651E2C]">{a.title}</span>
                      <span className="block text-xs text-[#77716E]">{a.description}</span>
                    </span>
                    <ArrowRight className="mt-1 size-3.5 shrink-0 text-[#B86B76] rtl:-scale-x-100" />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
