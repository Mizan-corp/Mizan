// Closing the books (ADR-014 D7, D10): the months in order (close; reopen with a reason), the
// fiscal years (year-end closing and its reversal), the fiscal year's first month, and the
// opening entry. Months and years: accounting:close; the setting and the opening: accounting:settings.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, LockOpen, Undo2 } from "lucide-react";
import { api } from "@/lib/api";
import { date as fmtDate, dateTime } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { useTenantNav } from "@app/lib/tenant";
import type { FiscalYear, PeriodsOverview } from "../api";
import { fiscalYearLabel, MONTHS_AR, monthLabel } from "../lib";
import { EntryDetailModal } from "../components/EntryDetail";
import { AccountingHeader, PERM, SkeletonRows, useAccountingState } from "../components/shared";

export default function PeriodsPage() {
  const qc = useQueryClient();
  const can = useAuth((s) => s.can);
  const { toast } = useToast();
  const canClose = can(PERM.close);
  const [reopening, setReopening] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [yearAction, setYearAction] = useState<{ year: FiscalYear; verb: "close" | "reverse" } | null>(null);
  const [openEntry, setOpenEntry] = useState<string | null>(null);
  const overview = useQuery({ queryKey: ["accounting", "periods"], queryFn: () => api.get<PeriodsOverview>("/accounting/periods") });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["accounting"] }); qc.invalidateQueries({ queryKey: ["periods"] }); };

  const month = useMutation({
    mutationFn: ({ m, verb }: { m: string; verb: "close" | "reopen" }) =>
      verb === "close" ? api.post(`/periods/${m}/close`) : api.post(`/periods/${m}/reopen`, { reason: reason.trim() }),
    onSuccess: (_r, v) => {
      toast("success", v.verb === "close" ? `أُقفل ${monthLabel(v.m)}` : `أُعيد فتح ${monthLabel(v.m)}`);
      setReopening(null);
      setReason("");
      refresh();
    },
    onError: (e, v) => { if (v.verb === "close") toast("error", (e as Error).message); },
  });
  const year = useMutation({
    mutationFn: ({ y, verb }: { y: number; verb: "close" | "reverse" }) =>
      api.post(verb === "close" ? `/accounting/year-end?year=${y}` : `/accounting/year-end/reverse?year=${y}`),
    onSuccess: (_r, v) => { toast("success", v.verb === "close" ? "سُجِّل قيد إقفال السنة" : "عُكس قيد إقفال السنة"); setYearAction(null); refresh(); },
    onError: (e) => { setYearAction(null); toast("error", (e as Error).message); },
  });
  const fyStart = overview.data?.fiscal_year_start ?? 1;

  return (
    <div className="flex flex-col gap-6">
      <AccountingHeader title="إقفال الفترات والسنة المالية"
                        subtitle="يُقفل الشهر بعد مراجعته وبالترتيب. لا تُسجَّل قيود بتاريخ شهر مغلق من أي شاشة، وإعادة الفتح تتطلب سبباً يُحفظ في السجل." />
      <div className="grid gap-4 lg:grid-cols-2">
        <FiscalYearStart />
        <OpeningCard onOpen={setOpenEntry} />
      </div>

      {overview.isLoading ? (
        <SkeletonRows n={6} />
      ) : overview.isError ? (
        <ErrorBox message={(overview.error as Error).message} onRetry={() => overview.refetch()} />
      ) : overview.data ? (
        <div className="grid gap-6 xl:grid-cols-[3fr_2fr]">
          <section className="flex flex-col gap-3">
            <h2 className="text-base font-bold">الأشهر</h2>
            <div className="overflow-x-auto rounded-xl border border-line bg-card">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-xs text-muted">
                    <th className="p-3 text-start">الشهر</th>
                    <th className="p-3 text-start">الحالة</th>
                    <th className="p-3 text-start">آخر إجراء</th>
                    <th className="p-3 text-end" />
                  </tr>
                </thead>
                <tbody>
                  {overview.data.months.map((m) => (
                    <tr key={m.month} className="border-b border-line/60 last:border-0">
                      <td className="p-3 font-semibold">{monthLabel(m.month)} {m.current && <Badge>الحالي</Badge>}</td>
                      <td className="p-3">
                        {m.status === "closed"
                          ? <Badge tone="danger"><Lock className="size-3" /> مقفل</Badge>
                          : <Badge tone="success"><LockOpen className="size-3" /> مفتوح</Badge>}
                      </td>
                      <td className="p-3 text-xs text-muted">
                        {m.status === "closed" && m.closed_at ? `أُقفل ${dateTime(m.closed_at)}${m.closed_by_name ? ` — ${m.closed_by_name}` : ""}`
                          : m.reopened_at ? `أُعيد فتحه ${dateTime(m.reopened_at)}${m.reopen_reason ? `: ${m.reopen_reason}` : ""}` : "—"}
                      </td>
                      <td className="p-3 text-end">
                        {canClose && m.can_close && (
                          <Button variant="danger" size="sm" disabled={month.isPending} onClick={() => month.mutate({ m: m.month, verb: "close" })}>
                            <Lock className="size-3.5" /> إقفال
                          </Button>
                        )}
                        {canClose && m.can_reopen && (
                          <Button variant="outline" size="sm" onClick={() => { month.reset(); setReason(""); setReopening(m.month); }}>
                            <LockOpen className="size-3.5" /> إعادة فتح
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted">يُقفل أقدم شهر مفتوح أولاً، ويُعاد فتح آخر شهر مقفل أولاً. الشهر الحالي لا يُقفل قبل انتهائه.</p>
          </section>

          <section className="flex flex-col gap-3">
            <h2 className="text-base font-bold">السنوات المالية</h2>
            {overview.data.years.map((y) => (
              <div key={y.year} className="flex flex-col gap-2 rounded-xl border border-line bg-card p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-bold">السنة المالية {fiscalYearLabel(y.year, fyStart)}</span>
                  {y.closing_entry ? <Badge tone="danger"><Lock className="size-3" /> مقفلة</Badge>
                    : y.over ? <Badge tone="warning">انتهت ولم تُقفل</Badge> : <Badge>جارية</Badge>}
                </div>
                <p className="text-xs text-muted">من {fmtDate(y.from)} إلى {fmtDate(y.to)}</p>
                {y.closing_entry ? (
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <button type="button" className="num text-primary underline" onClick={() => setOpenEntry(y.closing_entry!.id)}>
                      قيد الإقفال {y.closing_entry.number}
                    </button>
                    {canClose && (
                      <Button variant="outline" size="sm" onClick={() => setYearAction({ year: y, verb: "reverse" })}>
                        <Undo2 className="size-3.5" /> عكس الإقفال
                      </Button>
                    )}
                  </div>
                ) : y.over ? (
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    {y.open_months.length > 0 && <span className="text-muted">أشهر مفتوحة: {y.open_months.length}</span>}
                    {canClose && (
                      <Button size="sm" disabled={y.open_months.length > 0} onClick={() => setYearAction({ year: y, verb: "close" })}>
                        <Lock className="size-3.5" /> إقفال السنة
                      </Button>
                    )}
                  </div>
                ) : null}
              </div>
            ))}
            <p className="text-xs text-muted">
              إقفال السنة يرحّل أرصدة الإيرادات والمصروفات إلى الأرباح المحتجزة بقيد في آخر يوم منها، بعد إقفال كل أشهرها.
              لا يُعاد فتح أي شهر منها حتى يُعكس قيد الإقفال.
            </p>
          </section>
        </div>
      ) : null}

      <Modal open={!!reopening} onClose={() => setReopening(null)} title={`إعادة فتح ${reopening ? monthLabel(reopening) : ""}`}>
        <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (reopening && reason.trim().length >= 3 && !month.isPending) month.mutate({ m: reopening, verb: "reopen" }); }}>
          <p className="text-xs leading-relaxed text-muted">بعد إعادة الفتح يمكن تسجيل قيود بتاريخ هذا الشهر من جديد. يُحفظ السبب ومن أعاد الفتح في سجل المراجعة.</p>
          <div>
            <label htmlFor="reopen-why" className="mb-1 block text-sm font-medium">السبب *</label>
            <Input id="reopen-why" required minLength={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          {month.isError && <ErrorBox message={(month.error as Error).message} />}
          <Button type="submit" variant="danger" className="h-11 font-bold" disabled={month.isPending || reason.trim().length < 3}>
            {month.isPending ? <Spinner /> : "تأكيد إعادة الفتح"}
          </Button>
        </form>
      </Modal>
      <ConfirmDialog
        open={!!yearAction}
        onClose={() => setYearAction(null)}
        onConfirm={() => yearAction && year.mutate({ y: yearAction.year.year, verb: yearAction.verb })}
        title={yearAction?.verb === "close" ? `إقفال السنة المالية ${yearAction ? fiscalYearLabel(yearAction.year.year, fyStart) : ""}` : "عكس إقفال السنة"}
        message={yearAction?.verb === "close"
          ? "يُسجَّل قيد بتاريخ آخر يوم في السنة ينقل صافي الربح أو الخسارة إلى الأرباح المحتجزة. لا يُنشأ إلا مرة واحدة للسنة."
          : "يُسجَّل قيد عكسي لقيد الإقفال بتاريخه، فتعود أرصدة الإيرادات والمصروفات ويمكن بعدها إعادة فتح أشهر السنة."}
        confirmLabel={yearAction?.verb === "close" ? "إقفال السنة" : "عكس الإقفال"}
      />
      <EntryDetailModal entryId={openEntry} onClose={() => setOpenEntry(null)} onOpen={setOpenEntry} />
    </div>
  );
}

function FiscalYearStart() {
  const qc = useQueryClient();
  const can = useAuth((s) => s.can);
  const { toast } = useToast();
  const state = useAccountingState();
  const [value, setValue] = useState<number | null>(null);
  const current = value ?? state.data?.fiscal_year_start ?? 1;
  const locked = (state.data?.year_end_closings.length ?? 0) > 0;
  const save = useMutation({
    mutationFn: () => api.put("/accounting/settings", { fiscal_year_start: current }),
    onSuccess: () => { toast("success", "حُفظت بداية السنة المالية"); setValue(null); qc.invalidateQueries({ queryKey: ["accounting"] }); },
    onError: (e) => toast("error", (e as Error).message),
  });
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line bg-card p-4">
      <h2 className="text-base font-bold">بداية السنة المالية</h2>
      <div className="flex flex-wrap items-end gap-2">
        <Select className="w-44" aria-label="أول شهر في السنة المالية" value={current} disabled={!can(PERM.settings) || locked || state.isLoading}
                onChange={(e) => setValue(Number(e.target.value))}>
          {MONTHS_AR.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </Select>
        {can(PERM.settings) && !locked && (
          <Button variant="outline" disabled={save.isPending || value === null || value === state.data?.fiscal_year_start} onClick={() => save.mutate()}>
            {save.isPending ? <Spinner /> : "حفظ"}
          </Button>
        )}
      </div>
      <p className="text-xs text-muted">
        {locked ? "لا تتغير بعد إقفال سنة مالية: اعكس قيد الإقفال أولاً." : "تحدد السنة التي يُحسب لها ربح السنة الحالية في الميزانية وقيد إقفال السنة."}
      </p>
    </div>
  );
}

function OpeningCard({ onOpen }: { onOpen: (id: string) => void }) {
  const can = useAuth((s) => s.can);
  const { tenantTo } = useTenantNav();
  const state = useAccountingState();
  const opening = state.data?.opening_entry;
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line bg-card p-4">
      <h2 className="text-base font-bold">القيد الافتتاحي</h2>
      {state.isLoading ? (
        <SkeletonRows n={1} />
      ) : opening ? (
        <>
          <p className="text-sm">
            بدأت الدفاتر في {fmtDate(opening.date)} بالقيد{" "}
            <button type="button" className="num font-bold text-primary underline" onClick={() => onOpen(opening.id)}>{opening.number}</button>.
          </p>
          <p className="text-xs text-muted">لإعادته من الأرصدة الحالية: افتح القيد واعكسه (صلاحية إعداد الحسابات)، ثم سجّل قيداً افتتاحياً جديداً.</p>
        </>
      ) : (
        <>
          <p className="text-sm">لم يُسجَّل بعد. يبني القيد الافتتاحي الدفاتر من أرصدة العملاء والموردين والخزائن والمحافظ والمخزون الحالية.</p>
          {can(PERM.settings) && (
            <Button asChild className="self-start">
              <Link to={tenantTo("/accounting/opening")} className="inline-flex h-9 items-center rounded-md px-4 text-sm font-medium">تسجيل القيد الافتتاحي</Link>
            </Button>
          )}
        </>
      )}
    </div>
  );
}
