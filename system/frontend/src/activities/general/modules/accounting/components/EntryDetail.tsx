// One journal entry: its lines, its source document, the entries it reverses or is reversed by,
// and the reverse action (manual entries: accounting:journal; the opening entry: accounting:settings).
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Printer, Undo2 } from "lucide-react";
import { api } from "@/lib/api";
import { printDocument } from "@app/lib/documents";
import { date as fmtDate, dateTime } from "@/lib/format";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import { useTenantNav } from "@app/lib/tenant";
import type { EntryDetail, ReverseResult } from "../api";
import { PARTY_LABEL, SOURCE_SCREEN, sourceLabel, todayCairo } from "../lib";
import { Money, PERM, SkeletonRows, useBranches } from "./shared";

export function canReverse(entry: Pick<EntryDetail, "source_type" | "event" | "reverses_id" | "reversed_by">, can: (p: string) => boolean): boolean {
  if (entry.event === "reverse" || entry.reverses_id || entry.reversed_by) return false;
  if (entry.source_type === "manual") return can(PERM.journal);
  if (entry.source_type === "opening") return can(PERM.settings);
  return false;
}

export function EntryDetailModal({ entryId, onClose, onOpen }: { entryId: string | null; onClose: () => void; onOpen: (id: string) => void }) {
  const qc = useQueryClient();
  const can = useAuth((s) => s.can);
  const { toast } = useToast();
  const { tenantTo } = useTenantNav();
  const branches = useBranches();
  const [reversing, setReversing] = useState(false);
  const [revDate, setRevDate] = useState("");
  const [revMemo, setRevMemo] = useState("");
  const q = useQuery({
    queryKey: ["accounting", "entry", entryId],
    queryFn: () => api.get<EntryDetail>(`/accounting/entries/${entryId}`),
    enabled: !!entryId,
  });
  const e = q.data;
  const reverse = useMutation({
    mutationFn: () => api.post<ReverseResult>(`/accounting/entries/${entryId}/reverse`, { date: revDate || null, memo: revMemo.trim() || null }),
    onSuccess: (res) => {
      toast("success", `سُجِّل القيد العكسي ${res.entry.number}`);
      setReversing(false);
      qc.invalidateQueries({ queryKey: ["accounting"] });
      for (const key of ["customers", "suppliers", "safes", "wallets"]) qc.invalidateQueries({ queryKey: [key] });
    },
  });
  const branchName = (id: string | null) => (id ? branches.data?.find((b) => b.id === id)?.name ?? "—" : "—");
  const totalDebit = e?.lines.reduce((s, l) => s + l.debit, 0) ?? 0;
  const totalCredit = e?.lines.reduce((s, l) => s + l.credit, 0) ?? 0;
  const screen = e ? SOURCE_SCREEN[e.source_type] : undefined;

  return (
    <Modal open={!!entryId} onClose={onClose} title={e ? `القيد ${e.number}` : "القيد"} wide>
      {q.isLoading ? (
        <SkeletonRows n={4} />
      ) : q.isError ? (
        <ErrorBox message={(q.error as Error).message} onRetry={() => q.refetch()} />
      ) : e ? (
        <div className="flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div><dt className="text-xs text-muted">التاريخ</dt><dd className="font-semibold">{fmtDate(e.date)}</dd></div>
            <div><dt className="text-xs text-muted">المصدر</dt><dd className="font-semibold">{sourceLabel(e.source_type, e.event)}</dd></div>
            <div><dt className="text-xs text-muted">الفرع</dt><dd className="font-semibold">{branchName(e.warehouse_id)}</dd></div>
            <div><dt className="text-xs text-muted">بواسطة</dt><dd className="font-semibold">{e.created_by_name ?? "تلقائي"}</dd></div>
          </dl>
          {e.memo && <p className="rounded-lg bg-elevated/60 p-3 text-sm">{e.memo}</p>}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {e.source_ref && e.source_ref !== e.memo && <Badge>{e.source_ref}</Badge>}
            {e.reverses_entry && (
              <button type="button" className="text-primary underline" onClick={() => onOpen(e.reverses_entry!.id)}>
                يعكس القيد {e.reverses_entry.number}
              </button>
            )}
            {e.reversed_by_entry && (
              <Badge tone="warning">
                <button type="button" className="underline" onClick={() => onOpen(e.reversed_by_entry!.id)}>
                  عُكس بالقيد {e.reversed_by_entry.number}
                </button>
              </Badge>
            )}
            {e.source_type === "sale" && (
              <Button variant="outline" size="sm" onClick={() => printDocument(`/print/sale/${e.source_id}`)}>
                <Printer className="size-3.5" /> الفاتورة
              </Button>
            )}
            {screen && (
              <Button variant="outline" size="sm" asChild>
                <Link to={tenantTo(screen)} onClick={onClose} className="inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-xs">
                  <ExternalLink className="size-3.5" /> شاشة المستند
                </Link>
              </Button>
            )}
          </div>
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted">
                  <th className="p-2 text-start">الحساب</th>
                  <th className="p-2 text-start">الطرف</th>
                  <th className="p-2 text-start">الفرع</th>
                  <th className="p-2 text-end">مدين</th>
                  <th className="p-2 text-end">دائن</th>
                </tr>
              </thead>
              <tbody>
                {e.lines.map((l) => (
                  <tr key={l.id} className="border-b border-line/60 last:border-0">
                    <td className="p-2"><span className="num text-xs text-muted" dir="ltr">{l.account_code}</span> {l.account_name}</td>
                    <td className="p-2 text-xs">{l.party_type ? `${PARTY_LABEL[l.party_type]}: ${l.party_name ?? "—"}` : "—"}</td>
                    <td className="p-2 text-xs">{branchName(l.warehouse_id)}</td>
                    <td className="p-2 text-end">{l.debit ? <Money value={l.debit} /> : ""}</td>
                    <td className="p-2 text-end">{l.credit ? <Money value={l.credit} /> : ""}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-line font-bold">
                  <td className="p-2" colSpan={3}>الإجمالي</td>
                  <td className="p-2 text-end"><Money value={totalDebit} /></td>
                  <td className="p-2 text-end"><Money value={totalCredit} /></td>
                </tr>
              </tfoot>
            </table>
          </div>
          <p className="text-xs text-muted">سُجِّل {dateTime(e.created_at)}. القيود المرحّلة لا تُعدَّل ولا تُحذف؛ يُصحَّح الخطأ بقيد عكسي.</p>
          {canReverse(e, can) && !reversing && (
            <Button variant="outline" className="self-start" onClick={() => { setReversing(true); setRevDate(""); setRevMemo(""); reverse.reset(); }}>
              <Undo2 className="size-4" /> عكس القيد
            </Button>
          )}
          {reversing && (
            <form
              className="flex flex-col gap-3 rounded-xl border border-line p-3"
              onSubmit={(ev) => { ev.preventDefault(); if (!reverse.isPending) reverse.mutate(); }}
            >
              <p className="text-xs text-muted">
                {e.source_type === "opening"
                  ? "يُعكس القيد الافتتاحي بتاريخه نفسه افتراضياً، ثم يمكن تسجيل قيد افتتاحي جديد من الأرصدة الحالية."
                  : "يُسجَّل قيد معاكس بتاريخ اليوم افتراضياً، وتعود أرصدة العملاء والموردين والخزائن التي حرّكها القيد."}
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label htmlFor="rev-date" className="mb-1 block text-xs font-medium">تاريخ القيد العكسي (اختياري)</label>
                  <Input id="rev-date" type="date" min={e.date} max={todayCairo()} value={revDate} onChange={(ev) => setRevDate(ev.target.value)} />
                </div>
                <div>
                  <label htmlFor="rev-memo" className="mb-1 block text-xs font-medium">السبب</label>
                  <Input id="rev-memo" value={revMemo} maxLength={300} onChange={(ev) => setRevMemo(ev.target.value)} />
                </div>
              </div>
              {reverse.isError && <ErrorBox message={(reverse.error as Error).message} />}
              <div className="flex gap-2">
                <Button type="submit" variant="danger" disabled={reverse.isPending}>{reverse.isPending ? <Spinner /> : "تأكيد العكس"}</Button>
                <Button type="button" variant="ghost" onClick={() => setReversing(false)}>إلغاء</Button>
              </div>
            </form>
          )}
        </div>
      ) : null}
    </Modal>
  );
}
