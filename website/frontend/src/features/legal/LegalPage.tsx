import { Link } from "@app/seo/LocaleLink";
import { Check, MessageCircle, Phone, Scale } from "lucide-react";
import { useTranslation } from "@/i18n";
import { MarketingLayout } from "@app/features/marketing/MarketingLayout";
import { BUSINESS, PHONE_HREF, whatsappHref } from "./business";
import { type Block, LEGAL_DOCS, LEGAL_ORDER, type LegalSlug } from "./documents";

export const LEGAL_PATHS: Record<LegalSlug, string> = {
  terms: "/terms",
  privacy: "/privacy",
  "refund-policy": "/refund-policy",
};

function Blocks({ blocks }: { blocks: Block[] }) {
  return (
    <>
      {blocks.map((b, i) =>
        typeof b === "string" ? (
          <p key={i}>{b}</p>
        ) : (
          <ul key={i} className="list-disc space-y-1.5 ps-5 marker:text-[#B86B76]">
            {b.list.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ),
      )}
    </>
  );
}

/** Terms, privacy and refund policy: one layout, Arabic or English with the site's language. */
export default function LegalPage({ slug }: { slug: LegalSlug }) {
  const { locale } = useTranslation();
  const isAr = locale === "ar";
  const lang = isAr ? "ar" : "en";
  const doc = LEGAL_DOCS[slug][lang];


  return (
    <MarketingLayout>
      <div className="bg-[#FAF6F0] py-12 text-[#262321] sm:py-16">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <header className="max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E7D6C1] bg-white/80 px-3.5 py-1 text-xs font-semibold text-[#651E2C]">
              <Scale className="size-3.5 text-[#B86B76]" />
              {isAr ? "الشروط والسياسات" : "Legal"}
            </div>
            <h1 className={`mt-4 text-4xl font-normal leading-tight tracking-tight sm:text-5xl ${isAr ? "font-serif-ar" : "font-serif-en"}`}>
              {doc.title}
            </h1>
            <p className="mt-3 text-base leading-relaxed text-[#4D4744]">{doc.description}</p>
            <p className="mt-2 text-xs text-[#77716E]">
              {isAr ? "سارية من" : "Effective"} {BUSINESS.effective[lang]} · {BUSINESS.seller[lang]}{isAr ? "، " : ", "}{BUSINESS.city[lang]}
            </p>
          </header>

          <div className="mt-10 grid grid-cols-1 gap-10 lg:grid-cols-12">
            <aside className="lg:col-span-3">
              <nav aria-label={isAr ? "الصفحات القانونية" : "Legal pages"} className="space-y-6 lg:sticky lg:top-24">
                <ul className="space-y-1">
                  {LEGAL_ORDER.map((s) => {
                    const current = s === slug;
                    return (
                      <li key={s}>
                        <Link
                          to={LEGAL_PATHS[s]}
                          aria-current={current ? "page" : undefined}
                          className={`block rounded-xl px-3 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-[#651E2C] ${
                            current ? "bg-[#651E2C] font-semibold text-[#FAF6F0]" : "text-[#4D4744] hover:bg-[#EFE4D6]"
                          }`}
                        >
                          {LEGAL_DOCS[s][lang].title}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
                <div className="hidden lg:block">
                  <p className="mb-2 px-3 text-[11px] font-bold uppercase tracking-wider text-[#77716E]">
                    {isAr ? "في هذه الصفحة" : "On this page"}
                  </p>
                  <ol className="space-y-1 border-s border-[#E6DCD2] text-[13px]">
                    {doc.sections.map((sec, i) => (
                      <li key={sec.id}>
                        <a href={`#${sec.id}`} className="block px-3 py-0.5 text-[#77716E] hover:text-[#651E2C]">
                          {i + 1}. {sec.title}
                        </a>
                      </li>
                    ))}
                  </ol>
                </div>
              </nav>
            </aside>

            <article className="space-y-8 lg:col-span-9">
              {doc.summary && (
                <div className="rounded-2xl border border-[#E7D6C1] bg-white p-5 sm:p-6">
                  <h2 className="text-sm font-bold text-[#651E2C]">{isAr ? "باختصار" : "In short"}</h2>
                  <ul className="mt-3 space-y-2">
                    {doc.summary.map((s) => (
                      <li key={s} className="flex items-start gap-2.5 text-[15px] leading-relaxed">
                        <Check className="mt-1 size-4 shrink-0 text-[#27835C]" />
                        {s}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {doc.sections.map((sec, i) => (
                <section key={sec.id} id={sec.id} className="scroll-mt-28 border-b border-[#E6DCD2] pb-8 last:border-0">
                  <h2 className="text-xl font-bold text-[#262321]">
                    <span className="me-2 font-mono text-base text-[#B86B76]">{i + 1}.</span>
                    {sec.title}
                  </h2>
                  <div className="mt-3 space-y-3 text-[15px] leading-8 text-[#4D4744]">
                    <Blocks blocks={sec.blocks} />
                  </div>
                </section>
              ))}

              <div className="flex flex-col gap-4 rounded-2xl bg-[#35151D] p-6 text-[#FAF6F0] sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="font-semibold">{isAr ? "عندك سؤال عن هذه الشروط؟" : "Questions about these terms?"}</p>
                  <p className="mt-1 text-sm text-[#E7D6C1]/80">{isAr ? "تواصل معنا مباشرة." : "Get in touch directly."}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <a
                    href={whatsappHref()}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 rounded-full bg-[#FAF6F0] px-4 py-2 text-sm font-semibold text-[#35151D] hover:bg-white"
                  >
                    <MessageCircle className="size-4" /> {isAr ? "واتساب" : "WhatsApp"}
                  </a>
                  <a
                    href={PHONE_HREF}
                    className="inline-flex items-center gap-2 rounded-full border border-white/25 px-4 py-2 text-sm font-semibold hover:bg-white/10"
                  >
                    <Phone className="size-4" /> <span dir="ltr">{BUSINESS.phoneDisplay}</span>
                  </a>
                </div>
              </div>
            </article>
          </div>
        </div>
      </div>
    </MarketingLayout>
  );
}
