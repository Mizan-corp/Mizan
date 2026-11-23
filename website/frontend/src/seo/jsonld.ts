/**
 * Structured data (schema.org JSON-LD) for the public pages, typed with schema-dts. Only facts:
 * the seller's details come from business.ts, the offers from the plans snapshot. No ratings, no
 * social profiles until real ones exist (sameAs is left out), no SearchAction (the docs search
 * has no URL to point at).
 */
import type {
  BlogPosting,
  BreadcrumbList,
  FAQPage,
  Offer,
  Organization,
  SoftwareApplication,
  WebPage,
  WebSite,
} from "schema-dts";
import { BUSINESS } from "@app/features/legal/business";
import type { Faq } from "@/features/billing/pricingFaqs";
import { withLang, type Lang } from "./paths";
import type { PageSeo } from "./pages";

export const ORG_ID = "https://allmizan.live/#organization";
const websiteId = (site: string, lang: Lang) => `${site}${withLang("/", lang)}#website`;
const softwareId = (site: string) => `${site}/#software`;

export function organization(lang: Lang, site: string): Organization {
  return {
    "@type": "Organization",
    "@id": ORG_ID,
    name: lang === "ar" ? "ميزان" : "Mizan",
    alternateName: ["Mizan ERP", "ميزان ERP", lang === "ar" ? "Mizan" : "ميزان"],
    url: `${site}/`,
    logo: { "@type": "ImageObject", url: `${site}/icons/logo-512.png`, width: "512", height: "512" },
    address: {
      "@type": "PostalAddress",
      addressLocality: lang === "ar" ? "السويس" : "Suez",
      addressCountry: "EG",
    },
    contactPoint: [
      {
        "@type": "ContactPoint",
        telephone: `+${BUSINESS.phoneDigits}`,
        contactType: "customer support",
        areaServed: "EG",
        availableLanguage: ["ar", "en"],
      },
      {
        "@type": "ContactPoint",
        telephone: `+${BUSINESS.phoneDigits}`,
        contactType: "sales",
        areaServed: "EG",
        availableLanguage: ["ar", "en"],
      },
    ],
  };
}

export function website(lang: Lang, site: string): WebSite {
  return {
    "@type": "WebSite",
    "@id": websiteId(site, lang),
    name: lang === "ar" ? "ميزان ERP" : "Mizan ERP",
    url: site + withLang("/", lang),
    inLanguage: lang,
    publisher: { "@id": ORG_ID },
  };
}

interface PlanSnapshot {
  id: string;
  name: string;
  price_egp: number;
}

export function softwareApplication(lang: Lang, site: string, plans: PlanSnapshot[]): SoftwareApplication {
  const pricing = site + withLang("/pricing", lang);
  const offers: Offer[] = plans.map((p) => ({
    "@type": "Offer",
    name: lang === "ar" ? p.name.split("(")[0].trim() : (p.name.match(/\(([^)]+)\)/)?.[1] ?? p.id),
    price: p.price_egp,
    priceCurrency: "EGP",
    url: pricing,
    priceSpecification: {
      "@type": "UnitPriceSpecification",
      price: p.price_egp,
      priceCurrency: "EGP",
      referenceQuantity: { "@type": "QuantitativeValue", value: 1, unitCode: "MON" },
    },
  }));
  return {
    "@type": "SoftwareApplication",
    "@id": softwareId(site),
    name: lang === "ar" ? "ميزان ERP" : "Mizan ERP",
    applicationCategory: "BusinessApplication",
    // The cloud service in the browser, and the installers for one computer or a network.
    operatingSystem: "Web, Windows, Linux",
    url: site + withLang("/", lang),
    description:
      lang === "ar"
        ? "منصة لإدارة الأعمال: الحسابات والمخازن والمبيعات ونقاط البيع والموارد البشرية في نظام واحد."
        : "A business management platform: accounting, inventory, sales, point of sale and HR in one system.",
    inLanguage: ["ar", "en"],
    publisher: { "@id": ORG_ID },
    offers,
  };
}

export function webPage(page: PageSeo, site: string, image: string): WebPage {
  const url = site + page.path;
  return {
    "@type": "WebPage",
    "@id": `${url}#webpage`,
    url,
    name: page.title,
    description: page.description,
    inLanguage: page.lang,
    isPartOf: { "@id": websiteId(site, page.lang) },
    primaryImageOfPage: { "@type": "ImageObject", url: image, width: "1200", height: "630" },
    ...(page.breadcrumbs.length > 1 ? { breadcrumb: { "@id": `${url}#breadcrumb` } } : {}),
  };
}

export function breadcrumbs(page: PageSeo, site: string): BreadcrumbList {
  return {
    "@type": "BreadcrumbList",
    "@id": `${site}${page.path}#breadcrumb`,
    itemListElement: page.breadcrumbs.map((c, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: c.name,
      item: site + c.path,
    })),
  };
}

/** Only for questions shown on the page (the home page's and the pricing page's). */
export function faqPage(url: string, lang: Lang, faqs: Faq[]): FAQPage {
  return {
    "@type": "FAQPage",
    "@id": `${url}#faq`,
    inLanguage: lang,
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: lang === "ar" ? f.qAr : f.qEn,
      acceptedAnswer: { "@type": "Answer", text: lang === "ar" ? f.aAr : f.aEn },
    })),
  };
}

/** The posts are written by the Mizan team, so the author is the organization. */
export function blogPosting(page: PageSeo, site: string, headline: string, image: string): BlogPosting {
  const url = site + page.path;
  return {
    "@type": "BlogPosting",
    "@id": `${url}#article`,
    headline,
    description: page.description,
    inLanguage: page.lang,
    url,
    mainEntityOfPage: { "@id": `${url}#webpage` },
    image,
    datePublished: page.published,
    dateModified: page.modified ?? page.published,
    author: { "@id": ORG_ID },
    publisher: { "@id": ORG_ID },
  };
}
