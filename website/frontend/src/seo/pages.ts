/**
 * Every public page's head (ADR-016): title, description, canonical address, language versions,
 * social image and structured data, in one place. The build pre-renders exactly these pages
 * (scripts/prerender.mjs) and lists the indexable ones in the sitemaps; the browser applies the
 * same data when the visitor moves between pages (SiteEffects.tsx).
 *
 * Keep every sentence true: the business facts come from features/legal/business.ts, the plans
 * from plans.snapshot.json (the live plans API, scripts/update-plans.mjs).
 */
import type { Thing } from "schema-dts";
import { BLOG_POSTS } from "@app/features/marketing/blogData";
import { DOC_SECTIONS } from "@app/features/docs/docsData";
import { LEGAL_DOCS, type LegalSlug } from "@app/features/legal/documents";
import { HOME_FAQS } from "@app/features/marketing/faqs";
import { PRICING_FAQS } from "@/features/billing/pricingFaqs";
import { BUSINESS } from "@app/features/legal/business";
import plans from "./plans.snapshot.json";
import { EN_PAGES, withLang, type Lang } from "./paths";
import * as ld from "./jsonld";

/** The address search engines should know, whatever host built the page. */
export const SITE_URL = "https://allmizan.live";

export type OgKey =
  | "home" | "product" | "features" | "industries" | "pricing" | "about"
  | "contact" | "demo" | "blog" | "docs" | "legal";

export interface PageSeo {
  path: string;
  lang: Lang;
  title: string;
  description: string;
  og: OgKey;
  ogType: "website" | "article";
  /** Indexable pages are in the sitemaps; the others say noindex. */
  index: boolean;
  sitemap?: "pages" | "blog" | "docs";
  /** The page in each language it exists in (itself included); hreflang when there are two. */
  alternates: Partial<Record<Lang, string>>;
  breadcrumbs: { name: string; path: string }[];
  jsonLd: Thing[];
  /** The source of the page component, so the build can preload its code. */
  module: string;
  /** Dates the content itself carries (posts, docs), ISO. */
  published?: string;
  modified?: string;
}

type Copy = { title: string; description: string; crumb: string };
interface StaticPage {
  path: string;
  og: OgKey;
  module: string;
  ar: Copy;
  en?: Copy;
  /** The page's own structured data, next to WebPage and BreadcrumbList. */
  extra?: (lang: Lang, url: string) => Thing[];
}

const M = "src/features/marketing";
const minPrice = Math.min(...plans.plans.map((p) => p.price_egp));
const priceList = (lang: Lang) =>
  plans.plans
    .map((p) => `${lang === "ar" ? p.name.split("(")[0].trim() : (p.name.match(/\(([^)]+)\)/)?.[1] ?? p.id)} ${p.price_egp.toLocaleString("en-US")}`)
    .join(lang === "ar" ? "، " : ", ");

const STATIC_PAGES: StaticPage[] = [
  {
    path: "/",
    og: "home",
    module: `${M}/LandingPage.tsx`,
    ar: {
      title: "ميزان ERP | برنامج حسابات ومخازن وكاشير لإدارة أعمالك في مصر",
      description:
        "ميزان منصة مصرية لإدارة الأعمال: الحسابات والمخازن والمبيعات وكاشير يعمل بدون إنترنت والموارد البشرية في نظام واحد، على السحابة أو على أجهزتك. جرّبه مجانًا 14 يومًا.",
      crumb: "الرئيسية",
    },
    en: {
      title: "Mizan ERP | Accounting, Inventory and POS Software for Egypt",
      description:
        "Egyptian business software: accounting, inventory, sales, an offline-ready POS and HR in one system, in the cloud or on your own computers. Free for 14 days.",
      crumb: "Home",
    },
    extra: (lang, url) => [ld.softwareApplication(lang, SITE_URL, plans.plans), ld.faqPage(url, lang, HOME_FAQS)],
  },
  {
    path: "/product",
    og: "product",
    module: `${M}/ProductPage.tsx`,
    ar: {
      title: "منصة ميزان: الحسابات والمخازن والمبيعات في نظام واحد | ميزان ERP",
      description:
        "كيف تتصل وحدات ميزان ببعضها: فاتورة الكاشير تخصم المخزون وتُرحّل القيد المحاسبي تلقائيًا، مع عزل كامل لبيانات كل منشأة وصلاحيات دقيقة لكل مستخدم.",
      crumb: "المنتج",
    },
    en: {
      title: "The Mizan Platform: Accounts, Stock and Sales in One System",
      description:
        "How Mizan's modules work together: a sale at the till updates stock and posts the journal entry, with each business's data isolated and permissions per user.",
      crumb: "Product",
    },
    extra: (lang) => [ld.softwareApplication(lang, SITE_URL, plans.plans)],
  },
  {
    path: "/features",
    og: "features",
    module: `${M}/FeaturesPage.tsx`,
    ar: {
      title: "مميزات ميزان: المحاسبة والمخازن والمبيعات والموارد البشرية | ميزان ERP",
      description:
        "وحدات ميزان: محاسبة بقيد مزدوج، نقاط بيع وفواتير، مخازن وتحويلات بين الفروع، مشتريات وموردون، وموارد بشرية ورواتب، تفعّل منها ما يحتاجه نشاطك.",
      crumb: "المميزات",
    },
    en: {
      title: "Mizan Features: Accounting, Inventory, Sales and HR",
      description:
        "Mizan's modules: double-entry accounting, point of sale and invoicing, multi-branch inventory, purchasing, HR and payroll. Switch on what your business needs.",
      crumb: "Features",
    },
  },
  {
    path: "/features/inventory",
    og: "features",
    module: `${M}/FeatureDetailPage.tsx`,
    ar: {
      title: "إدارة المخازن والمستودعات في ميزان | ميزان ERP",
      description:
        "تابع أرصدة الأصناف في كل مستودع لحظيًا، مع تنبيهات النواقص والوحدات المركبة (كرتونة، شيكارة، متر) والتحويل بين الفروع في برنامج ميزان.",
      crumb: "إدارة المخزون",
    },
    en: {
      title: "Inventory and Warehouse Management in Mizan",
      description:
        "Live stock levels in every warehouse, low-stock alerts, compound units (carton, bag, metre) and transfers between branches, in Mizan.",
      crumb: "Inventory",
    },
  },
  {
    path: "/industries",
    og: "industries",
    module: `${M}/IndustriesPage.tsx`,
    ar: {
      title: "ميزان لكل نشاط: التجزئة والمطاعم والصيدليات والعيادات وغيرها | ميزان ERP",
      description:
        "نظام ميزان يتشكل حسب نشاطك: شاشات ووحدات جاهزة للتجزئة والجملة والمطاعم والصيدليات والعيادات ومواد البناء والخدمات، على نفس المنصة.",
      crumb: "القطاعات",
    },
    en: {
      title: "Mizan by Industry: Retail, Restaurants, Pharmacies, Clinics and More",
      description:
        "Mizan adapts to your trade: ready screens and modules for retail, wholesale, restaurants, pharmacies, clinics, building materials and services, on one platform.",
      crumb: "Industries",
    },
  },
  {
    path: "/pricing",
    og: "pricing",
    module: `${M}/PricingRoute.tsx`,
    ar: {
      title: `أسعار ميزان ERP بالجنيه المصري | باقات تبدأ من ${minPrice} ج.م شهريًا`,
      description: `باقات ميزان الشهرية: ${priceList("ar")} ج.م. تجربة مجانية ${plans.trial_days} يومًا بدون وسيلة دفع، ولا تجديد تلقائي.`,
      crumb: "الأسعار",
    },
    en: {
      title: `Mizan ERP Pricing in Egyptian Pounds | Plans from EGP ${minPrice}/month`,
      description: `Mizan's monthly plans: ${priceList("en")} EGP. A free ${plans.trial_days}-day trial with no payment details, and nothing renews automatically.`,
      crumb: "Pricing",
    },
    extra: (lang, url) => [ld.softwareApplication(lang, SITE_URL, plans.plans), ld.faqPage(url, lang, PRICING_FAQS)],
  },
  {
    path: "/about",
    og: "about",
    module: `${M}/AboutPage.tsx`,
    ar: {
      title: "عن ميزان: منصة مصرية لإدارة الأعمال من السويس | ميزان ERP",
      description: "تعرّف على ميزان: منصة مصرية لإدارة أعمال المنشآت، من السويس، ومن يقف وراءها وكيف تتواصل معنا.",
      crumb: "من نحن",
    },
    en: {
      title: "About Mizan: an Egyptian Business Platform from Suez",
      description: "Meet Mizan: an Egyptian platform for running a business, built in Suez, who is behind it and how to reach us.",
      crumb: "About",
    },
  },
  {
    path: "/contact",
    og: "contact",
    module: `${M}/ContactPage.tsx`,
    ar: {
      title: "تواصل مع ميزان: واتساب وهاتف | ميزان ERP",
      description: `اسأل عن ميزان أو اطلب عرضًا توضيحيًا عبر واتساب أو الهاتف ${BUSINESS.phoneDisplay}، من السويس.`,
      crumb: "تواصل معنا",
    },
    en: {
      title: "Contact Mizan: WhatsApp and Phone",
      description: `Ask about Mizan or book a walkthrough over WhatsApp or phone, ${BUSINESS.phoneDisplay}, from Suez, Egypt.`,
      crumb: "Contact",
    },
  },
  {
    path: "/demo",
    og: "demo",
    module: `${M}/DashboardShowcasePage.tsx`,
    ar: {
      title: "عرض حي لنظام ميزان: لوحة التحكم والتقارير | ميزان ERP",
      description: "جرّب نموذجًا تفاعليًا لشاشات ميزان: لوحة التحكم والمبيعات والمخزون، بالوضع الفاتح والداكن، قبل أن تبدأ تجربتك المجانية.",
      crumb: "عرض حي",
    },
    en: {
      title: "Mizan Live Demo: Dashboard and Reports",
      description: "Try an interactive preview of Mizan's screens: the dashboard, sales and stock, in light and dark mode, before you start your free trial.",
      crumb: "Live demo",
    },
  },
  {
    path: "/blog",
    og: "blog",
    module: `${M}/BlogPage.tsx`,
    ar: {
      title: "مدونة ميزان | مقالات عن الأنظمة والكاشير والمحاسبة",
      description: "مقالات من فريق ميزان عن بناء أنظمة إدارة الأعمال: الكاشير بدون إنترنت، طباعة الإيصالات، عزل بيانات المنشآت، والأنظمة المعيارية.",
      crumb: "المدونة",
    },
  },
  {
    path: "/docs",
    og: "docs",
    module: "src/features/docs/DocsRoutes.tsx",
    ar: {
      title: "دليل استخدام ميزان | مركز التوثيق",
      description: "دليل استخدام ميزان خطوة بخطوة: إنشاء الحساب ومساحة العمل، الكاشير والمخازن والمحاسبة، الصلاحيات، التشغيل على جهاز أو شبكة، والنسخ الاحتياطي.",
      crumb: "التوثيق",
    },
  },
];

const LEGAL_PATH: Record<LegalSlug, string> = { terms: "/terms", privacy: "/privacy", "refund-policy": "/refund-policy" };

const HOME_CRUMB: Record<Lang, string> = { ar: "الرئيسية", en: "Home" };

function build(p: {
  path: string;
  lang: Lang;
  copy: { title: string; description: string };
  og: OgKey;
  module: string;
  crumbs: { name: string; path: string }[];
  alternates: Partial<Record<Lang, string>>;
  index?: boolean;
  sitemap?: PageSeo["sitemap"];
  ogType?: PageSeo["ogType"];
  extra?: Thing[];
  published?: string;
  modified?: string;
}): PageSeo {
  const page: PageSeo = {
    path: p.path,
    lang: p.lang,
    title: p.copy.title,
    description: p.copy.description,
    og: p.og,
    ogType: p.ogType ?? "website",
    index: p.index ?? true,
    sitemap: p.sitemap,
    alternates: p.alternates,
    breadcrumbs: p.crumbs,
    jsonLd: [],
    module: p.module,
    published: p.published,
    modified: p.modified,
  };
  // Every page carries the organization and the site, so each reference resolves on the page.
  page.jsonLd = [
    ld.webPage(page, SITE_URL, ogImageUrl(page)),
    ...(page.breadcrumbs.length > 1 ? [ld.breadcrumbs(page, SITE_URL)] : []),
    ld.organization(p.lang, SITE_URL),
    ld.website(p.lang, SITE_URL),
    ...(p.extra ?? []),
  ];
  return page;
}

export function ogImageUrl(page: Pick<PageSeo, "og" | "lang">): string {
  return `${SITE_URL}/og/${page.og}-${page.lang}.png`;
}

function staticPages(): PageSeo[] {
  const out: PageSeo[] = [];
  for (const sp of STATIC_PAGES) {
    const langs: Lang[] = sp.en && EN_PAGES.has(sp.path) ? ["ar", "en"] : ["ar"];
    const alternates = Object.fromEntries(langs.map((l) => [l, withLang(sp.path, l)]));
    for (const lang of langs) {
      const copy = (lang === "en" ? sp.en : sp.ar)!;
      const path = withLang(sp.path, lang);
      const crumbs = [{ name: HOME_CRUMB[lang], path: withLang("/", lang) }];
      if (sp.path === "/features/inventory") {
        const parent = STATIC_PAGES.find((x) => x.path === "/features")!;
        crumbs.push({ name: (lang === "en" ? parent.en! : parent.ar).crumb, path: withLang("/features", lang) });
      }
      if (sp.path !== "/") crumbs.push({ name: copy.crumb, path });
      out.push(
        build({
          path,
          lang,
          copy,
          og: sp.og,
          module: sp.module,
          crumbs,
          alternates,
          sitemap: "pages",
          extra: sp.extra?.(lang, SITE_URL + path),
        }),
      );
    }
  }
  return out;
}

function legalPages(): PageSeo[] {
  const out: PageSeo[] = [];
  for (const slug of Object.keys(LEGAL_PATH) as LegalSlug[]) {
    const base = LEGAL_PATH[slug];
    const alternates = { ar: base, en: withLang(base, "en") };
    for (const lang of ["ar", "en"] as Lang[]) {
      const doc = LEGAL_DOCS[slug][lang];
      const path = withLang(base, lang);
      out.push(
        build({
          path,
          lang,
          copy: { title: `${doc.title} | ${lang === "ar" ? "ميزان" : "Mizan"}`, description: doc.description },
          og: "legal",
          module: "src/features/legal/LegalPage.tsx",
          crumbs: [
            { name: HOME_CRUMB[lang], path: withLang("/", lang) },
            { name: doc.title, path },
          ],
          alternates,
          sitemap: "pages",
        }),
      );
    }
  }
  return out;
}

function blogPages(): PageSeo[] {
  const blog = STATIC_PAGES.find((p) => p.path === "/blog")!;
  return BLOG_POSTS.map((post) => {
    const path = `/blog/${post.slug}`;
    const page = build({
      path,
      lang: "ar",
      copy: { title: `${post.title} | مدونة ميزان`, description: clip(post.excerpt) },
      og: "blog",
      ogType: "article",
      module: `${M}/BlogPostPage.tsx`,
      crumbs: [
        { name: HOME_CRUMB.ar, path: "/" },
        { name: blog.ar.crumb, path: "/blog" },
        { name: post.title, path },
      ],
      alternates: { ar: path },
      sitemap: "blog",
      published: post.published,
      modified: post.published,
    });
    page.jsonLd.push(ld.blogPosting(page, SITE_URL, post.title, ogImageUrl(page)));
    return page;
  });
}

function docPages(): PageSeo[] {
  const docs = STATIC_PAGES.find((p) => p.path === "/docs")!;
  return DOC_SECTIONS.flatMap((section) =>
    section.items.map((article) => {
      const path = `/docs/${article.slug}`;
      return build({
        path,
        lang: "ar",
        copy: { title: `${article.title} | دليل ميزان`, description: clip(article.description) },
        og: "docs",
        module: "src/features/docs/DocsRoutes.tsx",
        crumbs: [
          { name: HOME_CRUMB.ar, path: "/" },
          { name: docs.ar.crumb, path: "/docs" },
          { name: article.title, path },
        ],
        alternates: { ar: path },
        sitemap: "docs",
        modified: article.lastUpdated,
      });
    }),
  );
}

/** Descriptions stay within what results pages show (~160 characters), cut at a word. */
function clip(text: string, max = 160): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max - 1);
  return `${cut.slice(0, cut.lastIndexOf(" "))}…`;
}

let cache: PageSeo[] | null = null;

/** Every page the build writes as HTML: all indexable. */
export function prerenderPages(): PageSeo[] {
  cache ??= [...staticPages(), ...legalPages(), ...blogPages(), ...docPages()];
  return cache;
}

/** The "page not found" pages nginx answers unknown addresses with (status 404). */
export function notFoundPages(): (PageSeo & { file: string; render: string })[] {
  return (["ar", "en"] as Lang[]).map((lang) => ({
    ...build({
      path: withLang("/404", lang),
      lang,
      copy:
        lang === "ar"
          ? { title: "الصفحة غير موجودة | ميزان", description: "لم نجد هذه الصفحة. ربما تغيّر عنوانها؛ ابدأ من الصفحة الرئيسية أو تصفح المميزات والأسعار." }
          : { title: "Page not found | Mizan", description: "We couldn't find this page. Its address may have changed; start from the home page or browse features and pricing." },
      og: "home",
      module: `${M}/NotFoundPage.tsx`,
      crumbs: [],
      alternates: {},
      index: false,
    }),
    file: lang === "ar" ? "404.html" : "en/404.html",
    render: withLang("/__not-found__", lang),
  }));
}

/** Application pages: served as the shell, never indexed; titles for the browser tab. */
const APP_TITLES: Record<string, Record<Lang, string>> = {
  "/signup": { ar: "إنشاء حساب | ميزان", en: "Create your account | Mizan" },
  "/onboarding": { ar: "تجهيز مساحة العمل | ميزان", en: "Set up your workspace | Mizan" },
};

/** The head for an address the visitor moved to in the browser. */
export function seoFor(pathname: string, lang: Lang): PageSeo {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const known = prerenderPages().find((p) => p.path === path);
  if (known) return known;
  const app = APP_TITLES[path.replace(/^\/en(?=\/)/, "")];
  const notFound = notFoundPages().find((p) => p.lang === lang)!;
  if (app) return { ...notFound, path, title: app[lang], jsonLd: [] };
  return notFound;
}
