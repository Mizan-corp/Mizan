/**
 * The public pages' head and structured data (ADR-016): checked offline here; the live check is
 * Google's Rich Results Test after a release.
 */
import { describe, expect, it } from "vitest";
import { notFoundPages, prerenderPages, seoFor, SITE_URL } from "../pages";
import { headTags } from "../head";
import { alternatePath, localizeHref } from "../paths";
import { HOME_FAQS } from "@app/features/marketing/faqs";
import { PRICING_FAQS } from "@/features/billing/pricingFaqs";
import plans from "../plans.snapshot.json";

type Node = Record<string, unknown>;
const pages = prerenderPages();

describe("paths", () => {
  it("keeps English pages in English and Arabic-only pages Arabic", () => {
    expect(localizeHref("/pricing", "en")).toBe("/en/pricing");
    expect(localizeHref("/", "en")).toBe("/en");
    expect(localizeHref("/pricing?plan=pro#faq", "en")).toBe("/en/pricing?plan=pro#faq");
    expect(localizeHref("/blog", "en")).toBe("/blog");
    expect(localizeHref("/docs/modules/pos", "en")).toBe("/docs/modules/pos");
    expect(localizeHref("/en/about", "en")).toBe("/en/about");
    expect(localizeHref("/pricing", "ar")).toBe("/pricing");
    expect(localizeHref("https://wa.me/1", "en")).toBe("https://wa.me/1");
  });

  it("switches language to the same page, or to that language's home", () => {
    expect(alternatePath("/pricing", "en")).toBe("/en/pricing");
    expect(alternatePath("/en/pricing", "ar")).toBe("/pricing");
    expect(alternatePath("/blog/x", "en")).toBe("/en");
    expect(alternatePath("/en", "ar")).toBe("/");
  });
});

describe("pages", () => {
  it("has one page per address, each with its own title, description and canonical", () => {
    const paths = pages.map((p) => p.path);
    expect(new Set(paths).size).toBe(paths.length);
    expect(new Set(pages.map((p) => p.title)).size).toBe(pages.length);
    expect(new Set(pages.map((p) => p.description)).size).toBe(pages.length);
    for (const p of pages) {
      expect(p.title.length, p.path).toBeLessThanOrEqual(110);
      expect(p.description.length, p.path).toBeGreaterThan(50);
      expect(p.description.length, p.path).toBeLessThanOrEqual(170);
      const canonical = headTags(p).find((t) => t.attrs.rel === "canonical");
      expect(canonical?.attrs.href).toBe(SITE_URL + p.path);
    }
  });

  it("has the English key pages, with hreflang both ways and x-default on the Arabic page", () => {
    for (const path of ["/en", "/en/product", "/en/features", "/en/pricing", "/en/industries", "/en/about", "/en/contact", "/en/demo"]) {
      const p = pages.find((x) => x.path === path);
      expect(p, path).toBeDefined();
      expect(p!.lang).toBe("en");
      const alts = headTags(p!).filter((t) => t.attrs.rel === "alternate");
      const ar = alts.find((t) => t.attrs.hreflang === "ar")!.attrs.href;
      expect(alts.find((t) => t.attrs.hreflang === "x-default")!.attrs.href).toBe(ar);
      const back = pages.find((x) => SITE_URL + x.path === ar)!;
      expect(headTags(back).some((t) => t.attrs.hreflang === "en" && t.attrs.href === SITE_URL + path)).toBe(true);
    }
  });

  it("keeps application pages and unknown addresses out of the index", () => {
    expect(seoFor("/signup", "ar").index).toBe(false);
    expect(seoFor("/en/signup", "en").title).toMatch(/account/i);
    expect(seoFor("/nope", "ar").index).toBe(false);
    for (const nf of notFoundPages()) {
      expect(headTags(nf).find((t) => t.attrs.name === "robots")!.attrs.content).toMatch(/noindex/);
      expect(headTags(nf).some((t) => t.attrs.rel === "canonical")).toBe(false);
    }
  });
});

const graphOf = (path: string): Node[] => {
  const p = pages.find((x) => x.path === path)!;
  const script = headTags(p).find((t) => t.tag === "script")!;
  const data = JSON.parse(script.text!) as { "@context": string; "@graph": Node[] };
  expect(data["@context"]).toBe("https://schema.org");
  return data["@graph"];
};
const ofType = (g: Node[], type: string) => g.filter((n) => n["@type"] === type);

describe("structured data", () => {
  it("resolves every @id reference within the page", () => {
    for (const p of pages) {
      const g = graphOf(p.path);
      const ids = new Set(g.map((n) => n["@id"]).filter(Boolean));
      const refs: string[] = [];
      const walk = (v: unknown) => {
        if (Array.isArray(v)) v.forEach(walk);
        else if (v && typeof v === "object") {
          const o = v as Node;
          if (Object.keys(o).length === 1 && typeof o["@id"] === "string") refs.push(o["@id"]);
          else Object.values(o).forEach(walk);
        }
      };
      g.forEach((n) => Object.values(n).forEach(walk));
      for (const r of refs) expect(ids.has(r), `${p.path}: ${r}`).toBe(true);
      for (const n of g) expect(typeof n["@type"], p.path).toBe("string");
    }
  });

  it("describes the organization with the seller's real details only", () => {
    const org = ofType(graphOf("/"), "Organization")[0];
    expect(org.url).toBe(`${SITE_URL}/`);
    expect((org.logo as Node).url).toMatch(/\.png$/);
    expect(JSON.stringify(org.contactPoint)).toContain("+201067790350");
    expect((org.address as Node).addressCountry).toBe("EG");
    expect(org).not.toHaveProperty("sameAs");
    expect(org).not.toHaveProperty("aggregateRating");
  });

  it("offers the plans of the plans API, in EGP, without ratings", () => {
    for (const path of ["/", "/pricing", "/en/pricing", "/product"]) {
      const app = ofType(graphOf(path), "SoftwareApplication")[0];
      expect(app.applicationCategory).toBe("BusinessApplication");
      expect(app).not.toHaveProperty("aggregateRating");
      const offers = app.offers as Node[];
      expect(offers.map((o) => o.price)).toEqual(plans.plans.map((p) => p.price_egp));
      for (const o of offers) expect(o.priceCurrency).toBe("EGP");
    }
  });

  it("publishes FAQPage only with the questions shown on the page", () => {
    const home = ofType(graphOf("/"), "FAQPage")[0];
    expect((home.mainEntity as Node[]).map((q) => q.name)).toEqual(HOME_FAQS.map((f) => f.qAr));
    const pricing = ofType(graphOf("/en/pricing"), "FAQPage")[0];
    expect((pricing.mainEntity as Node[]).map((q) => (q.acceptedAnswer as Node).text)).toEqual(PRICING_FAQS.map((f) => f.aEn));
    for (const p of pages.filter((x) => !["/", "/en", "/pricing", "/en/pricing"].includes(x.path))) {
      expect(ofType(graphOf(p.path), "FAQPage"), p.path).toHaveLength(0);
    }
  });

  it("dates blog posts and credits the organization", () => {
    const posts = pages.filter((p) => p.path.startsWith("/blog/"));
    expect(posts.length).toBeGreaterThan(0);
    for (const p of posts) {
      const post = ofType(graphOf(p.path), "BlogPosting")[0];
      expect(post.datePublished).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(post.author).toEqual({ "@id": "https://allmizan.live/#organization" });
      expect(post.headline).toBeTruthy();
    }
  });

  it("numbers breadcrumbs from 1 with absolute addresses", () => {
    const crumbs = ofType(graphOf("/docs/modules/pos"), "BreadcrumbList")[0].itemListElement as Node[];
    expect(crumbs.map((c) => c.position)).toEqual([1, 2, 3]);
    for (const c of crumbs) expect(String(c.item)).toMatch(/^https:\/\/allmizan\.live\//);
  });
});
