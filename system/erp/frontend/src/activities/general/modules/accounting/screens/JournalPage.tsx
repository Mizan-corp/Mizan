// The journal (ADR-014 D1, D9): every posted entry with filters (date, source, account) and its
// detail; the manual entries' drafts, written, posted and deleted here (accounting:journal).
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePenLine, Plus, Send, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { date as fmtDate, dateTime } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Select, useToast } from "@/components/ui";
import type { Draft, DraftRow, EntryRow, Paged, PostResult } from "../api";
import { SOURCE_LABEL, sourceLabel } from "../lib";
import { DraftForm } from "../components/DraftForm";
import { EntryDetailModal } from "../components/EntryDetail";
import { AccountingHeader, AccountSelect, Money, PERM, SkeletonRows, useChart } from "../components/shared";

const PAGE = 50;

export default function JournalPage() {
  const can = useAuth((s) => s.can);
  const canView = can(PERM.view);
  const canWrite = can(PERM.journal);
  const [tab, setTab] = useState<"entries" | "drafts">(canView ? "entries" : "drafts");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Draft | null>(null);

  return (
    <div className="flex flex-col gap-6">
      <AccountingHeader
        title="دفتر اليومية"
        subtitle="كل القيود المرحّلة في الدفاتر، تلقائية من المستندات أو يدوية، ومسودات القيود اليدوية"
        actions={canWrite && (
          <Button onClick={() => { setEditing(null); setFormOpen(true); }}>
            <Plus size={16} /> قيد يومية جديد
          </Button>
        )}
      />
      {canView && canWrite && (
        <div className="flex gap-2" role="tablist">
          {([["entries", "القيود المرحّلة"], ["drafts", "المسودات"]] as const).map(([key, label]) => (
            <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                    className={`rounded-lg px-3 py-1.5 text-sm font-semibold ${tab === key ? "bg-elevated text-ink" : "text-muted hover:text-ink"}`}>
              {label}
            </button>
          ))}
        </div>
      )}
      {tab === "entries" && canView && <Entries />}
      {tab === "drafts" && canWrite && <Drafts onEdit={(d) => { setEditing(d); setFormOpen(true); }} />}
      <DraftForm open={formOpen} draft={editing} onClose={() => { setFormOpen(false); setEditing(null); }} />
    </div>
  );
}

function Entries() {
  const chart = useChart();
  const [filters, setFilters] = useState({ from: "", to: "", source_type: "", account_id: "" });
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);
  const list = useQuery({
    queryKey: ["accounting", "entries", filters, page],
    queryFn: () => api.get<Paged<EntryRow>>("/accounting/entries", { ...filters, page, page_size: PAGE }),
    placeholderData: keepPreviousData,
  });
  const set = (patch: Partial<typeof filters>) => { setFilters((f) => ({ ...f, ...patch })); setPage(1); };
  const pages = Math.max(1, Math.ceil((list.data?.total ?? 0) / PAGE));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-card p-3">
        <div>
          <label htmlFor="je-f-from" className="mb-1 block text-xs font-medium text-muted">من تاريخ</label>
          <Input id="je-f-from" type="date" className="w-40" value={filters.from} onChange={(e) => set({ from: e.target.value })} />
        </div>
        <div>
          <label htmlFor="je-f-to" className="mb-1 block text-xs font-medium text-muted">إلى تاريخ</label>
          <Input id="je-f-to" type="date" className="w-40" value={filters.to} onChange={(e) => set({ to: e.target.value })} />
        </div>
        <div>
          <label htmlFor="je-f-src" className="mb-1 block text-xs font-medium text-muted">المصدر</label>
          <Select id="je-f-src" className="w-44" value={filters.source_type} onChange={(e) => set({ source_type: e.target.value })}>
            <option value="">كل المصادر</option>
            {Object.entries(SOURCE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </div>
        <div className="min-w-60 flex-1">
          <label htmlFor="je-f-acc" className="mb-1 block text-xs font-medium text-muted">الحساب</label>
          <AccountSelect id="je-f-acc" value={filters.account_id} onChange={(id) => set({ account_id: id })} rows={chart.rows}
                         placeholder="كل الحسابات" />
        </div>
      </div>

      {list.isLoading ? (
        <SkeletonRows />
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.items.length ? (
        <Empty text="لا توجد قيود" hint={Object.values(filters).some(Boolean) ? "غيّر عوامل التصفية" : "تُسجَّل القيود تلقائياً مع كل بيع وشراء ومصروف وحركة خزنة"} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">رقم القيد</th>
                <th className="p-3 text-start">التاريخ</th>
                <th className="p-3 text-start">المصدر</th>
                <th className="p-3 text-start">البيان</th>
                <th className="p-3 text-end">المبلغ</th>
                <th className="p-3 text-start" />
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((e) => (
                <tr key={e.id} className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-elevated" onClick={() => setOpenId(e.id)}>
                  <td className="num p-3 font-bold" dir="ltr">{e.number}</td>
                  <td className="p-3 text-xs">{fmtDate(e.date)}</td>
                  <td className="p-3">{sourceLabel(e.source_type, e.event)}</td>
                  <td className="max-w-80 truncate p-3 text-xs text-muted">{e.memo ?? "—"}</td>
                  <td className="p-3 text-end font-bold"><Money value={e.amount} /></td>
                  <td className="p-3">
                    {e.reversed && <Badge tone="warning">معكوس</Badge>}
                    {e.reverses_id && <Badge>قيد عكسي</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>السابق</Button>
          <span className="num text-muted">صفحة {page} من {pages}</span>
          <Button variant="outline" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>التالي</Button>
        </div>
      )}
      <EntryDetailModal entryId={openId} onClose={() => setOpenId(null)} onOpen={setOpenId} />
    </div>
  );
}

function Drafts({ onEdit }: { onEdit: (d: Draft) => void }) {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [status, setStatus] = useState<"draft" | "posted">("draft");
  const [deleting, setDeleting] = useState<DraftRow | null>(null);
  const list = useQuery({
    queryKey: ["accounting", "drafts", status],
    queryFn: () => api.get<Paged<DraftRow>>("/accounting/drafts", { status, page_size: 200 }),
  });
  const edit = useMutation({
    mutationFn: (id: string) => api.get<Draft>(`/accounting/drafts/${id}`),
    onSuccess: onEdit,
    onError: (e) => toast("error", (e as Error).message),
  });
  const post = useMutation({
    mutationFn: (id: string) => api.post<PostResult>(`/accounting/drafts/${id}/post`),
    onSuccess: (r) => {
      toast("success", `رُحِّل القيد ${r.entry.number}`);
      qc.invalidateQueries({ queryKey: ["accounting"] });
      for (const key of ["customers", "suppliers", "safes", "wallets"]) qc.invalidateQueries({ queryKey: [key] });
    },
    onError: (e) => toast("error", (e as Error).message),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.del(`/accounting/drafts/${id}`),
    onSuccess: () => { setDeleting(null); toast("success", "حُذفت المسودة"); qc.invalidateQueries({ queryKey: ["accounting", "drafts"] }); },
    onError: (e) => toast("error", (e as Error).message),
  });

  return (
    <div className="flex flex-col gap-4">
      <Select className="w-48" value={status} onChange={(e) => setStatus(e.target.value as "draft" | "posted")} aria-label="الحالة">
        <option value="draft">مسودات لم تُرحَّل</option>
        <option value="posted">قيود يدوية مرحّلة</option>
      </Select>
      {list.isLoading ? (
        <SkeletonRows n={4} />
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.items.length ? (
        <Empty text={status === "draft" ? "لا توجد مسودات" : "لا توجد قيود يدوية مرحّلة"} hint="قيد اليومية اليدوي للتسويات والإهلاك ورأس المال وما لا يسجله مستند" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">التاريخ</th>
                <th className="p-3 text-start">البيان</th>
                <th className="p-3 text-start">السطور</th>
                <th className="p-3 text-end">مدين</th>
                <th className="p-3 text-end">دائن</th>
                <th className="p-3 text-start">الحالة</th>
                <th className="p-3 text-start">آخر تعديل</th>
                <th className="p-3 text-start" />
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((d) => (
                <tr key={d.id} className="border-b border-line/60 last:border-0">
                  <td className="p-3 text-xs">{fmtDate(d.date)}</td>
                  <td className="max-w-72 truncate p-3">{d.memo ?? "—"}</td>
                  <td className="num p-3">{d.line_count}</td>
                  <td className="p-3 text-end"><Money value={d.debit} /></td>
                  <td className="p-3 text-end"><Money value={d.credit} /></td>
                  <td className="p-3">
                    {d.status === "posted" ? <Badge tone="success">{d.entry_number}</Badge>
                      : d.balanced ? <Badge tone="brand">متوازن</Badge> : <Badge tone="warning">غير متوازن</Badge>}
                  </td>
                  <td className="p-3 text-xs text-muted">{dateTime(d.updated_at)}{d.created_by_name ? ` — ${d.created_by_name}` : ""}</td>
                  <td className="p-3">
                    {d.status === "draft" && (
                      <div className="flex gap-1">
                        <Button variant="outline" size="sm" disabled={edit.isPending} onClick={() => edit.mutate(d.id)} aria-label="تعديل">
                          <FilePenLine className="size-4" />
                        </Button>
                        <Button size="sm" disabled={post.isPending || !d.balanced} onClick={() => post.mutate(d.id)}>
                          <Send className="size-4" /> ترحيل
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setDeleting(d)} aria-label="حذف">
                          <Trash2 className="size-4 text-destructive" />
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ConfirmDialog open={!!deleting} onClose={() => setDeleting(null)} onConfirm={() => deleting && remove.mutate(deleting.id)}
                     title="حذف المسودة" message="تُحذف المسودة نهائياً. لم تُرحَّل، فلا أثر لها على الدفاتر." confirmLabel="حذف" />
    </div>
  );
}
