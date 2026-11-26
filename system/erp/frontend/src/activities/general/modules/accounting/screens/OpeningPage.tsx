// The opening entry wizard (ADR-014 D10): pick the start date, review the lines built from today's
// balances (and the products skipped for having no cost), then post it (accounting:settings).
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { date as fmtDate, qty } from "@/lib/format";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Spinner } from "@/components/ui";
import { useTenantNav } from "@app/lib/tenant";
import type { EntryRef, OpeningPreview } from "../api";
import { todayCairo } from "../lib";
import { AccountingHeader, ExportButtons, Money, SkeletonRows, useAccountingState } from "../components/shared";

const SECTION: Record<string, string> = {
  customers: "العملاء", suppliers: "الموردون", safes: "الخزائن والبنوك", wallets: "المحافظ", drawers: "أدراج الكاشير",
  inventory: "المخزون", equity: "رصيد أول المدة",
};

export default function OpeningPage() {
  const qc = useQueryClient();
  const { tenantTo } = useTenantNav();
  const state = useAccountingState();
  const [date, setDate] = useState(todayCairo());
  const [asked, setAsked] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [posted, setPosted] = useState<EntryRef | null>(null);
  const preview = useQuery({
    queryKey: ["accounting", "opening-preview", asked],
    queryFn: () => api.get<OpeningPreview>("/accounting/opening/preview", { date: asked! }),
    enabled: !!asked,
  });
  const post = useMutation({
    mutationFn: () => api.post<OpeningPreview & { entry: EntryRef | null }>("/accounting/opening", { date: asked }),
    onSuccess: (r) => { setConfirming(false); setPosted(r.entry); qc.invalidateQueries({ queryKey: ["accounting"] }); },
    onError: () => setConfirming(false),
  });
  const p = preview.data;
  const existing = state.data?.opening_entry;
  const step = posted ? 3 : asked ? 2 : 1;

  return (
    <div className="flex flex-col gap-6">
      <AccountingHeader title="القيد الافتتاحي" subtitle="بداية الدفاتر من الأرصدة الحالية: المستندات السابقة لا يُعاد ترحيلها، والفرق يذهب إلى رصيد أول المدة." />
      <ol className="flex flex-wrap gap-2 text-xs font-semibold" aria-label="الخطوات">
        {["تاريخ البداية", "مراجعة السطور", "الترحيل"].map((s, i) => (
          <li key={s} className={`rounded-full px-3 py-1 ${step === i + 1 ? "bg-primary text-primary-foreground" : step > i + 1 ? "bg-success/20" : "bg-elevated text-muted"}`}>
            {i + 1}. {s}
          </li>
        ))}
      </ol>

      {posted ? (
        <div className="flex flex-col items-start gap-3 rounded-xl border border-success/40 bg-success/10 p-5">
          <p className="flex items-center gap-2 font-bold"><CheckCircle2 className="size-5" /> سُجِّل القيد الافتتاحي {posted.number} بتاريخ {fmtDate(posted.date)}</p>
          <p className="text-sm">من الآن تُرحَّل كل المستندات تلقائياً. راجع ميزان المراجعة والمطابقة للتأكد.</p>
          <div className="flex gap-2">
            <Button asChild><Link to={tenantTo("/accounting/reports?tab=trial")} className="inline-flex h-9 items-center rounded-md px-4 text-sm">ميزان المراجعة</Link></Button>
            <Button variant="outline" asChild><Link to={tenantTo("/accounting/reports?tab=reconciliation")} className="inline-flex h-9 items-center rounded-md px-4 text-sm">المطابقة</Link></Button>
          </div>
        </div>
      ) : existing && !asked ? (
        <Empty text={`القيد الافتتاحي مسجل بالفعل (${existing.number}، ${fmtDate(existing.date)})`}
               hint="لإعادته: اعكسه من دفتر اليومية أولاً، ثم عد إلى هنا." />
      ) : (
        <form className="flex flex-wrap items-end gap-3 rounded-xl border border-line bg-card p-4"
              onSubmit={(e) => { e.preventDefault(); setAsked(date); }}>
          <div>
            <label htmlFor="op-date" className="mb-1 block text-sm font-medium">تاريخ بداية الدفاتر *</label>
            <Input id="op-date" type="date" required max={todayCairo()} value={date} onChange={(e) => setDate(e.target.value)} className="w-44" />
          </div>
          <Button type="submit" variant={asked ? "outline" : "default"}>{asked ? "تحديث المعاينة" : "معاينة القيد"}</Button>
          <p className="basis-full text-xs text-muted">
            يكون في أو قبل تاريخ أول قيد في الدفاتر، وفي شهر مفتوح. الأرصدة تؤخذ كما هي الآن.
          </p>
        </form>
      )}

      {asked && !posted && (
        preview.isLoading ? <SkeletonRows n={8} /> : preview.isError ? (
          <ErrorBox message={(preview.error as Error).message} onRetry={() => preview.refetch()} />
        ) : p ? (
          <div className="flex flex-col gap-4">
            {p.blockers.length > 0 && (
              <ul className="list-inside list-disc rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm">
                {p.blockers.map((b) => <li key={b}>{b}</li>)}
              </ul>
            )}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(p.sections).map(([k, s]) => (
                <div key={k} className="rounded-xl border border-line bg-card p-3">
                  <p className="text-xs text-muted">{SECTION[k] ?? k} ({s.count})</p>
                  <p className="font-bold"><Money value={s.debit || s.credit} /> <span className="text-xs font-normal text-muted">{s.debit ? "مدين" : "دائن"}</span></p>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              {p.balanced ? <Badge tone="success"><CheckCircle2 className="size-3.5" /> متوازن</Badge> : <Badge tone="warning">غير متوازن</Badge>}
              <ExportButtons filename="opening-entry" title="القيد الافتتاحي (معاينة)" subtitle={fmtDate(p.date)}
                             columns={["القسم", "البيان", "الحساب", "مدين", "دائن"]}
                             rows={p.lines.map((l) => [SECTION[l.section] ?? l.section, l.label, l.account ? `${l.account.code} ${l.account.name}` : "حساب جديد", l.debit, l.credit])} />
            </div>
            {!p.lines.length ? (
              <Empty text="لا توجد أرصدة لترحيلها" hint="لا عملاء ولا موردون ولا خزائن ولا مخزون بأرصدة" />
            ) : (
              <div className="overflow-x-auto rounded-xl border border-line bg-card">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-xs text-muted">
                      <th className="p-2 text-start">القسم</th>
                      <th className="p-2 text-start">البيان</th>
                      <th className="p-2 text-start">الحساب</th>
                      <th className="p-2 text-end">مدين</th>
                      <th className="p-2 text-end">دائن</th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.lines.map((l, i) => (
                      <tr key={i} className="border-b border-line/60 last:border-0">
                        <td className="p-2 text-xs text-muted">{SECTION[l.section] ?? l.section}</td>
                        <td className="p-2">{l.label}</td>
                        <td className="p-2 text-xs">{l.account ? <><span className="num text-muted" dir="ltr">{l.account.code}</span> {l.account.name}</> : "يُنشأ تلقائياً"}</td>
                        <td className="p-2 text-end">{l.debit ? <Money value={l.debit} /> : ""}</td>
                        <td className="p-2 text-end">{l.credit ? <Money value={l.credit} /> : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-line font-bold">
                      <td className="p-2" colSpan={3}>الإجمالي</td>
                      <td className="p-2 text-end"><Money value={p.total_debit} /></td>
                      <td className="p-2 text-end"><Money value={p.total_credit} /></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            )}
            {p.skipped_no_cost.length > 0 && (
              <div className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm">
                <p className="mb-2 flex items-center gap-2 font-semibold"><TriangleAlert className="size-4" /> أصناف لها رصيد بلا تكلفة، لا تدخل قيمة المخزون:</p>
                <ul className="grid gap-1 text-xs sm:grid-cols-2">
                  {p.skipped_no_cost.map((s) => <li key={s.product_id}>{s.name}{s.code ? ` (${s.code})` : ""} — الكمية {qty(s.qty)}</li>)}
                </ul>
                <p className="mt-2 text-xs text-muted">أدخل تكلفتها في شاشة الأصناف ثم حدّث المعاينة، أو رحّل بدونها.</p>
              </div>
            )}
            {p.notes.map((n) => <p key={n} className="text-xs text-muted">{n}</p>)}
            {post.isError && <ErrorBox message={(post.error as Error).message} />}
            <Button className="h-11 self-start px-8 font-bold" disabled={!p.can_post || post.isPending || !p.lines.length} onClick={() => setConfirming(true)}>
              {post.isPending ? <Spinner /> : "ترحيل القيد الافتتاحي"}
            </Button>
          </div>
        ) : null
      )}
      <ConfirmDialog open={confirming} onClose={() => setConfirming(false)} onConfirm={() => post.mutate()} danger={false}
                     title="ترحيل القيد الافتتاحي" confirmLabel="ترحيل"
                     message={`يُسجَّل القيد بتاريخ ${asked ? fmtDate(asked) : ""} من الأرصدة الحالية، ويصبح تاريخ بداية الدفاتر. لا يُنشأ غيره إلا بعد عكسه.`} />
    </div>
  );
}
