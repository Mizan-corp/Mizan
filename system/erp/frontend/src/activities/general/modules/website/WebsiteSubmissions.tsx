/**
 * Website tab form-submissions inbox: messages visitors send through published
 * contact-form blocks. Read surface over /site/forms; the only action is
 * marking a message read. Unread messages show a badge until marked.
 */
import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { ListState } from "@/components/app/shared";
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
import { createSiteFormsClient, type SiteFormSubmission } from "./siteForms";

function submissionDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" });
}

function senderLabel(s: SiteFormSubmission): string {
  return s.payload.name || s.payload.email || "—";
}

export default function WebsiteSubmissions({ apiBase }: { apiBase: string }) {
  const [submissions, setSubmissions] = useState<SiteFormSubmission[] | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const api = createSiteFormsClient({ baseUrl: apiBase });

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const out = await api.listSubmissions(unreadOnly);
      setSubmissions(out.submissions);
      setStatus("ready");
    } catch {
      setSubmissions(null);
      setStatus("error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, unreadOnly]);

  useEffect(() => {
    void load();
  }, [load]);

  const markRead = async (s: SiteFormSubmission) => {
    if (s.read_at) return;
    setSavingId(s.id);
    try {
      const out = await api.markRead(s.id);
      setSubmissions((prev) => (prev ?? []).map((x) => (x.id === s.id ? { ...x, read_at: out.read_at } : x)));
    } catch {
      // Keep the visible state; the next refresh reconciles.
    } finally {
      setSavingId(null);
    }
  };

  return (
    <section aria-label="رسائل الموقع" className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">الرسائل</h2>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant={unreadOnly ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setUnreadOnly((v) => !v)}
          >
            غير المقروءة بس
          </Button>
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
      </div>
      <ListState
        status={status}
        isEmpty={status === "ready" && !submissions?.length}
        onRetry={() => void load()}
        emptyTitle="لسه مفيش رسائل"
        emptyDescription="أول ما زائر يبعت من فورم التواصل في صفحة منشورة، رسالته هتظهر هنا."
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>المرسل</TableHead>
              <TableHead>الرسالة</TableHead>
              <TableHead>الصفحة</TableHead>
              <TableHead>التاريخ</TableHead>
              <TableHead className="text-end">الحالة</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(submissions ?? []).map((s) => (
              <TableRow key={s.id}>
                <TableCell>
                  <div className="flex flex-col">
                    <span>{senderLabel(s)}</span>
                    {s.payload.name && s.payload.email && (
                      <span className="text-muted-foreground text-sm" dir="ltr">
                        {s.payload.email}
                      </span>
                    )}
                    {s.payload.phone && (
                      <span className="text-muted-foreground text-sm" dir="ltr">
                        {s.payload.phone}
                      </span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="max-w-md">
                  <span className="line-clamp-2 whitespace-pre-wrap">{s.payload.message ?? ""}</span>
                </TableCell>
                <TableCell dir="ltr">{s.page_slug ? `/${s.page_slug}` : "—"}</TableCell>
                <TableCell>{submissionDate(s.created_at)}</TableCell>
                <TableCell className="text-end">
                  {s.read_at ? (
                    <Badge variant="secondary">مقروءة</Badge>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={savingId === s.id}
                      onClick={() => void markRead(s)}
                      aria-label={`تحديد رسالة ${senderLabel(s)} كمقروءة`}
                    >
                      تحديد كمقروءة
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ListState>
    </section>
  );
}
