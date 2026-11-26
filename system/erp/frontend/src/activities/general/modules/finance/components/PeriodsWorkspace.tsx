// Month-end closing: every month from the first activity to now. Months close in order (only the
// earliest open past month offers "close"), never the current one; only the latest closed month
// reopens, with a reason kept in the audit log.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, Lock, LockOpen } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { sound } from "@/lib/sound";
import { useAuth } from "@/stores/auth";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import type { PeriodMonth } from "../api";

export function PeriodsWorkspace() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const canClose = useAuth((s) => s.can("accounting:close|finance"));
  const list = useQuery({ queryKey: ["periods"], queryFn: () => api.get<PeriodMonth[]>("/periods") });
  const [closing, setClosing] = useState<string | null>(null);
  const [reopening, setReopening] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  const act = useMutation({
    mutationFn: ({ month, verb }: { month: string; verb: "close" | "reopen" }) => {
      sound.click();
      return verb === "reopen"
        ? api.post(`/periods/${month}/reopen`, { reason: reason.trim() })
        : api.post(`/periods/${month}/close`);
    },
    onSuccess: (_r, v) => {
      sound.success();
      toast("success", v.verb === "close" ? `أُقفل شهر ${v.month}` : `أُعيد فتح شهر ${v.month}`);
      setClosing(null);
      setReopening(null);
      setReason("");
      qc.invalidateQueries({ queryKey: ["periods"] });
      qc.invalidateQueries({ queryKey: ["accounting"] });
    },
    onError: (e, v) => {
      sound.error();
      if (v.verb === "close") {
        setClosing(null);
        toast("error", (e as Error).message);
      }
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-line bg-card p-5 shadow-xs">
        <h2 className="text-base font-bold text-ink">إقفال الفترات المالية</h2>
        <p className="text-xs text-muted mt-1 leading-relaxed">
          تظهر كل الأشهر منذ أول حركة مالية. يُقفل الشهر بعد مراجعته وبالترتيب، ولا يُقفل الشهر الحالي. لا تُسجَّل حركات بتاريخ شهر
          مغلق، وإعادة الفتح تبدأ من آخر شهر مغلق وتتطلب سبباً يُحفظ في السجل.
        </p>
      </div>

      {list.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-14 w-full rounded-xl" />)}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <Empty text="لا توجد أشهر بعد" hint="تظهر الأشهر مع أول حركة مالية." icon={<CalendarCheck className="size-10" />} />
      ) : (
        <div className="rounded-2xl border border-line bg-card overflow-x-auto shadow-xs">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-elevated/50 text-xs font-bold text-muted">
                <th className="p-3.5 text-start">الشهر</th>
                <th className="p-3.5 text-start">الحالة</th>
                <th className="p-3.5 text-start">آخر إجراء</th>
                <th className="p-3.5 text-end">الإجراء</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {list.data.map((p) => (
                <tr key={p.month} className="hover:bg-elevated/40 transition-colors">
                  <td className="num p-3.5 font-bold text-ink" dir="ltr">
                    {p.month} {p.current && <Badge tone="brand">الحالي</Badge>}
                  </td>
                  <td className="p-3.5">
                    <Badge tone={p.status === "closed" ? "danger" : "success"}>
                      <span className="flex items-center gap-1.5">
                        {p.status === "closed" ? <><Lock className="size-3" /> مقفل</> : <><LockOpen className="size-3" /> مفتوح</>}
                      </span>
                    </Badge>
                  </td>
                  <td className="p-3.5 text-xs text-muted">
                    {p.status === "closed" && p.closed_at
                      ? `أُقفل ${dateTime(p.closed_at)}${p.closed_by_name ? ` — ${p.closed_by_name}` : ""}`
                      : p.reopened_at
                        ? `أُعيد فتحه ${dateTime(p.reopened_at)}${p.reopen_reason ? ` — ${p.reopen_reason}` : ""}`
                        : "—"}
                  </td>
                  <td className="p-3.5 text-end">
                    {canClose && p.can_close && (
                      <Button variant="danger" size="sm" className="font-bold text-xs gap-1.5 h-8" disabled={act.isPending}
                              onClick={() => setClosing(p.month)}>
                        <Lock className="size-3.5" /> إقفال الشهر
                      </Button>
                    )}
                    {canClose && p.can_reopen && (
                      <Button variant="outline" size="sm" className="font-bold text-xs gap-1.5 h-8" disabled={act.isPending}
                              onClick={() => { act.reset(); setReason(""); setReopening(p.month); }}>
                        <LockOpen className="size-3.5" /> إعادة الفتح
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={!!closing}
        onClose={() => setClosing(null)}
        onConfirm={() => closing && act.mutate({ month: closing, verb: "close" })}
        title={`إقفال شهر ${closing ?? ""}`}
        message="بعد الإقفال لا تُسجَّل أي حركة مالية بتاريخ هذا الشهر حتى يُعاد فتحه."
        confirmLabel="إقفال"
      />

      <Modal open={!!reopening} onClose={() => setReopening(null)} title={`إعادة فتح شهر ${reopening ?? ""}`}>
        <form className="flex flex-col gap-4"
              onSubmit={(ev) => {
                ev.preventDefault();
                if (reopening && !act.isPending && reason.trim().length >= 3) act.mutate({ month: reopening, verb: "reopen" });
              }}>
          <p className="text-xs text-muted leading-relaxed">
            بعد إعادة الفتح يمكن تسجيل حركات بتاريخ هذا الشهر من جديد. يُحفظ السبب ومن أعاد الفتح في سجل المراجعة.
          </p>
          <div>
            <label htmlFor="reopen-reason" className="mb-1 block text-xs font-semibold text-muted">سبب إعادة الفتح *</label>
            <Input id="reopen-reason" value={reason} maxLength={500} onChange={(ev) => setReason(ev.target.value)} />
          </div>
          {act.isError && <ErrorBox message={(act.error as Error).message} />}
          <Button type="submit" variant="danger" className="w-full h-11 font-bold text-xs rounded-xl"
                  disabled={act.isPending || reason.trim().length < 3}>
            {act.isPending ? <Spinner /> : "تأكيد إعادة الفتح"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}
