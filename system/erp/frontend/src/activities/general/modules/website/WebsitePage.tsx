/**
 * PAGE CONTRACT
 * Page: الموقع (/website)
 * User: the owner or staff with the site.manage permission.
 * Outcome: manage the module data feeding the site (non-UI records/behavior
 *   configuration only): site-origin orders, published products and consent
 *   settings. The full page lifecycle (create/design/publish) lives in the
 *   standalone Studio, launched here in a NEW full browser tab (revised split,
 *   user-approved 2026-11-25 19:05, superseding the earlier pages-list slice).
 * Source: user decisions 2026-11-25 (17:33 frontstore is renamed Website; 17:36 pages
 *   are managed from Website; 17:37 page edit opens standalone Studio in a new full
 *   browser tab; 17:38 ALL website UI/design stays in Studio, non-UI lives here;
 *   17:41 Website owns the site data flow while Inventory stays the product/stock
 *   source of truth — no duplicated catalog).
 * Data: /site/pages through the same reviewed client the Studio uses; the module
 *   settings sections reuse the same consent components the Studio Data panel mounts,
 *   against the same workspace endpoints and edit tokens.
 * Required states: loading (skeleton), error (retry), empty (no pages yet), populated.
 */
import { Globe } from "lucide-react";
import { useEffect } from "react";
import { PageHeader } from "@/components/app/shared";
import { Button } from "@/components/kit/button";
import { useI18nStore } from "@/i18n";
import { syncUILang } from "@app/platform/site/studio/uiStrings";
import WebsiteModuleSettings from "@app/platform/site/studio/WebsiteModuleSettings";
import WebsiteOrders from "./WebsiteOrders";
import WebsitePublishedProducts from "./WebsitePublishedProducts";
import WebsiteSubmissions from "./WebsiteSubmissions";
import "./website.css";

const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";
// The standalone Studio bundle is served same-origin (deploy/studio-test/package.py:
// studio-preview.html is the deployment's root entry; /studio/* is the older
// experimental prototype, kept for prior-route compatibility but never launched).
// The workspace session cookie carries the sign-in across the new tab; the page id
// rides in the query string, never a token.
const STUDIO_URL: string =
  (import.meta.env.VITE_STUDIO_URL as string | undefined) ?? "/studio-preview.html";


export function studioLaunchUrl(pageId?: string): string {
  return pageId ? `${STUDIO_URL}?page=${encodeURIComponent(pageId)}` : STUDIO_URL;
}

export default function WebsitePage() {
  // Embedded Studio components follow the ERP locale here (not the Studio's own
  // saved preference): the settings copy is consent wording and must read in the
  // language the ERP runs in. syncUILang never writes the Studio's stored choice.
  const locale = useI18nStore((s) => s.locale);
  useEffect(() => {
    syncUILang(locale);
  }, [locale]);

  const openStudio = (pageId?: string) => {
    window.open(studioLaunchUrl(pageId), "_blank", "noopener,noreferrer");
  };

  return (
    <div className="website-module-page flex flex-col gap-8">
      <PageHeader
        title="الموقع"
        description="بيانات موقعك وطلباته. دورة الصفحات كلها (إنشاء، تصميم، نشر) في Studio - بيفتح في تبويب جديد منفصل."
        actions={
          <Button type="button" variant="outline" onClick={() => openStudio()}>
            <Globe data-icon="inline-start" />
            فتح Studio
          </Button>
        }
      />

      <WebsiteOrders apiBase={API_BASE} />

      <WebsiteSubmissions apiBase={API_BASE} />

      <WebsitePublishedProducts apiBase={API_BASE} />

      <section aria-label="بيانات الموقع" className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">بيانات الموقع</h2>
        <WebsiteModuleSettings apiBase={API_BASE} onSaved={() => {}} onDirty={() => {}} />
      </section>
    </div>
  );
}
