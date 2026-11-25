/**
 * PAGE CONTRACT
 * Page: الموقع (/website)
 * User: the owner or staff with the site.manage permission.
 * Outcome: manage the website's pages and the module data feeding the site (non-UI
 *   records/behavior configuration only); every design edit opens the standalone
 *   Studio in a NEW full browser tab with the page loaded.
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
import { useCallback, useEffect, useState } from "react";
import { ExternalLink, Globe, RefreshCw } from "lucide-react";
import { ListState, PageHeader } from "@/components/app/shared";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/kit/table";
import WebsiteModuleSettings from "@app/features/studio/WebsiteModuleSettings";
import WebsiteOrders from "./WebsiteOrders";
import {
  createSitePagesClient,
  type PageSummary,
} from "@app/features/studio/sitePages";
import "./website.css";

const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "/api";
// The standalone Studio bundle is served same-origin (deploy: /studio/* -> studio.html).
// The workspace session cookie carries the sign-in across the new tab; the page id
// rides in the query string, never a token.
const STUDIO_URL: string =
  (import.meta.env.VITE_STUDIO_URL as string | undefined) ?? "/studio/";

const api = createSitePagesClient({ baseUrl: API_BASE });

export function studioLaunchUrl(pageId?: string): string {
  return pageId ? `${STUDIO_URL}?page=${encodeURIComponent(pageId)}` : STUDIO_URL;
}

function pageTitle(p: PageSummary): string {
  return p.titles?.ar || p.titles?.en || p.slug;
}

function pageStatus(p: PageSummary): { label: string; published: boolean } {
  const published = p.published || p.status === "published";
  if (published && p.has_draft) return { label: "منشورة وفيها تعديلات", published: true };
  if (published) return { label: "منشورة", published: true };
  return { label: "مسودة", published: false };
}

export default function WebsitePage() {
  const [pages, setPages] = useState<PageSummary[] | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const out = await api.listPages();
      setPages(out.items.filter((p) => p.status !== "archived"));
      setStatus("ready");
    } catch {
      setPages(null);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openStudio = (pageId?: string) => {
    window.open(studioLaunchUrl(pageId), "_blank", "noopener,noreferrer");
  };

  return (
    <div className="website-module-page flex flex-col gap-8">
      <PageHeader
        title="الموقع"
        description="صفحات موقعك والبيانات اللي بتغذيه. أي تعديل في التصميم بيفتح في Studio في تبويب جديد منفصل."
        actions={
          <Button type="button" variant="outline" onClick={() => openStudio()}>
            <Globe data-icon="inline-start" />
            فتح Studio
          </Button>
        }
      />

      <section aria-label="صفحات الموقع" className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">الصفحات</h2>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => void load()}
            disabled={status === "loading"}
          >
            <RefreshCw data-icon="inline-start" />
            تحديث
          </Button>
        </div>
        <ListState
          status={status}
          isEmpty={status === "ready" && !pages?.length}
          onRetry={() => void load()}
          emptyTitle="لسه مفيش صفحات"
          emptyDescription="ابدأ أول صفحة من Studio؛ هتظهر هنا أول ما تتسجل."
          emptyAction={
            <Button type="button" onClick={() => openStudio()}>
              فتح Studio
            </Button>
          }
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>الصفحة</TableHead>
                <TableHead>المسار</TableHead>
                <TableHead>الحالة</TableHead>
                <TableHead className="text-end">تعديل التصميم</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(pages ?? []).map((p) => {
                const state = pageStatus(p);
                return (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{pageTitle(p)}</TableCell>
                    <TableCell dir="ltr" className="text-muted-foreground">
                      /{p.slug}
                    </TableCell>
                    <TableCell>
                      <Badge variant={state.published ? "default" : "secondary"}>
                        {state.label}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-end">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => openStudio(p.id)}
                      >
                        <ExternalLink data-icon="inline-start" />
                        تعديل في Studio
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </ListState>
      </section>

      <WebsiteOrders apiBase={API_BASE} />

      <section aria-label="بيانات الموقع" className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">بيانات الموقع</h2>
        <WebsiteModuleSettings apiBase={API_BASE} onSaved={() => void load()} onDirty={() => {}} />
      </section>
    </div>
  );
}
