import type { PageSeo } from "./pages";
import { ogImageUrl, SITE_URL } from "./pages";

export interface HeadTag {
  tag: "meta" | "link" | "script";
  attrs: Record<string, string>;
  text?: string;
}

const OG_LOCALE = { ar: "ar_EG", en: "en_US" } as const;
const SITE_NAME = { ar: "ميزان ERP", en: "Mizan ERP" } as const;
const OG_ALT = { ar: "ميزان: منصة إدارة الأعمال", en: "Mizan: business management platform" } as const;

/** A page's tags, without <title> (set apart: document.title in the browser). */
export function headTags(page: PageSeo): HeadTag[] {
  const url = SITE_URL + page.path;
  const image = ogImageUrl(page);
  const tags: HeadTag[] = [
    { tag: "meta", attrs: { name: "description", content: page.description } },
    {
      tag: "meta",
      attrs: { name: "robots", content: page.index ? "index, follow, max-image-preview:large" : "noindex, follow" },
    },
  ];
  if (page.index) {
    tags.push({ tag: "link", attrs: { rel: "canonical", href: url } });
    const langs = Object.entries(page.alternates) as [keyof typeof OG_LOCALE, string][];
    if (langs.length > 1) {
      for (const [lang, path] of langs) tags.push({ tag: "link", attrs: { rel: "alternate", hreflang: lang, href: SITE_URL + path } });
      // Visitors in other languages get the Arabic page: the site's first language.
      tags.push({ tag: "link", attrs: { rel: "alternate", hreflang: "x-default", href: SITE_URL + page.alternates.ar } });
    }
  }
  tags.push(
    { tag: "meta", attrs: { property: "og:type", content: page.ogType } },
    { tag: "meta", attrs: { property: "og:site_name", content: SITE_NAME[page.lang] } },
    { tag: "meta", attrs: { property: "og:locale", content: OG_LOCALE[page.lang] } },
    ...Object.keys(page.alternates)
      .filter((l) => l !== page.lang)
      .map((l) => ({ tag: "meta" as const, attrs: { property: "og:locale:alternate", content: OG_LOCALE[l as keyof typeof OG_LOCALE] } })),
    { tag: "meta", attrs: { property: "og:title", content: page.title } },
    { tag: "meta", attrs: { property: "og:description", content: page.description } },
    { tag: "meta", attrs: { property: "og:url", content: url } },
    { tag: "meta", attrs: { property: "og:image", content: image } },
    { tag: "meta", attrs: { property: "og:image:type", content: "image/png" } },
    { tag: "meta", attrs: { property: "og:image:width", content: "1200" } },
    { tag: "meta", attrs: { property: "og:image:height", content: "630" } },
    { tag: "meta", attrs: { property: "og:image:alt", content: OG_ALT[page.lang] } },
    { tag: "meta", attrs: { name: "twitter:card", content: "summary_large_image" } },
    { tag: "meta", attrs: { name: "twitter:title", content: page.title } },
    { tag: "meta", attrs: { name: "twitter:description", content: page.description } },
    { tag: "meta", attrs: { name: "twitter:image", content: image } },
    { tag: "meta", attrs: { name: "twitter:image:alt", content: OG_ALT[page.lang] } },
  );
  if (page.ogType === "article" && page.published) {
    tags.push({ tag: "meta", attrs: { property: "article:published_time", content: page.published } });
    if (page.modified) tags.push({ tag: "meta", attrs: { property: "article:modified_time", content: page.modified } });
  }
  if (page.jsonLd.length) {
    tags.push({
      tag: "script",
      attrs: { type: "application/ld+json" },
      text: JSON.stringify({ "@context": "https://schema.org", "@graph": page.jsonLd }).replace(/</g, "\\u003c"),
    });
  }
  return tags;
}

const escapeAttr = (v: string) => v.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escapeText = (v: string) => v.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** The <title> and tags as HTML, for the pre-rendered files. Tags carry data-seo for the browser. */
export function renderHead(page: PageSeo): string {
  const tags = headTags(page).map((t) => {
    const attrs = Object.entries({ ...t.attrs, "data-seo": "" })
      .map(([k, v]) => (v === "" ? k : `${k}="${escapeAttr(v)}"`))
      .join(" ");
    return t.tag === "script" ? `<script ${attrs}>${t.text ?? ""}</script>` : `<${t.tag} ${attrs} />`;
  });
  return [`<title>${escapeText(page.title)}</title>`, ...tags].join("\n    ");
}
