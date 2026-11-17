import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, CheckCircle2, Coins, FileText, LockOpen, Send } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api, openPrintDoc } from "@/lib/api";
import { money, moneyEGP } from "@/lib/format";
import { Badge, Button, Card, ConfirmDialog, ErrorBox, Modal, Spinner, useToast } from "@/components/ui";
import { useAuth } from "@/stores/auth";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";

// A month nobody calculated yet is a draft without an id (reading it creates nothing).
interface Period { id: string | null; month: string; status: "draft" | "review" | "approved" | "paid" }
interface Entry {
  id: string; employee_id: string; emp_name: string; net_salary: string;
  base_salary: string; bonuses: string; deductions: string; advances: string;
}

export default function PayrollPage() {
  const qc = useQueryClient();
  const now = new Date();
  const [month, setMonth] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`);
  const [paying, setPaying] = useState(false);
  const [paySource, setPaySource] = useState("");
  const [reopening, setReopening] = useState(false);
  const can = useAuth((s) => s.can);
  const canApprove = can("payroll:approve");
  const canPay = can("payroll:pay");

  const period = useQuery({
    queryKey: ["payroll-period", month],
    queryFn: () => api.get<Period>("/hr/payroll/period", { month }),
    retry: false,
  });
  const entries = useQuery({
    queryKey: ["payroll", month],
    queryFn: () => api.get<Entry[]>("/hr/payroll", { month }),
  });

  const { toast } = useToast();
  const invalidate = (msg?: string) => {
    qc.invalidateQueries({ queryKey: ["payroll-period"] });
    qc.invalidateQueries({ queryKey: ["payroll"] });
    if (msg) toast("success", msg);
  };

  const calc = useMutation({
    mutationFn: () => api.post("/hr/payroll/calculate", { month }),
    onSuccess: () => invalidate("تم حساب رواتب الشهر"),
  });
  const submit = useMutation({
    mutationFn: () => api.post(`/hr/payroll/period/submit?month=${month}`),
    onSuccess: () => invalidate("تم تقديم الشهر للمراجعة"),
  });
  const approve = useMutation({
    mutationFn: () => api.post(`/hr/payroll/period/approve?month=${month}`),
    onSuccess: () => invalidate("تم اعتماد الرواتب"),
  });
  const pay = useMutation({
    mutationFn: () => api.post(`/hr/payroll/period/pay?month=${month}`, sourceFields(paySource)),
    onSuccess: () => {
      setPaying(false);
      setPaySource("");
      qc.invalidateQueries({ queryKey: ["safes"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
      invalidate("تم صرف الرواتب");
    },
  });
  const reopen = useMutation({
    mutationFn: () => api.post(`/hr/payroll/period/reopen?month=${month}`),
    onSuccess: () => { setReopening(false); invalidate("تمت إعادة فتح الشهر"); },
  });

  const status = period.data?.status ?? "draft";
  const stepIndex = { draft: 0, review: 1, approved: 2, paid: 3 }[status] ?? 0;
  const totalNet = (entries.data ?? []).reduce((s, e) => s + Number(e.net_salary), 0);
  const busy = calc.isPending || submit.isPending || approve.isPending || pay.isPending || reopen.isPending;
  const firstError = (period.error ?? calc.error ?? submit.error ?? approve.error ?? reopen.error) as Error | null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">الرواتب</h1>
        <div className="flex items-center gap-2">
          <input
            type="month"
            className="num rounded-lg border border-line bg-surface px-3 py-2 text-sm"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            aria-label="الشهر"
          />
          <Button variant="outline" onClick={() => openPrintDoc("/hr/payroll/report/monthly", { month })}>
            <FileText size={16} /> تقرير الشهر
          </Button>
        </div>
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-2">
          {[
            { label: "حساب", icon: <Calculator size={16} /> },
            { label: "تقديم", icon: <Send size={16} /> },
            { label: "اعتماد", icon: <CheckCircle2 size={16} /> },
            { label: "صرف", icon: <Coins size={16} /> },
          ].map((s, i) => (
            <div key={s.label} className="flex items-center gap-2">
              <div
                className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold ${
                  i <= stepIndex ? "bg-brand text-brand-ink" : "bg-elevated text-muted"
                }`}
              >
                {s.icon} {s.label}
              </div>
              {i < 3 && <span className="text-muted">←</span>}
            </div>
          ))}
          {status !== "draft" && status !== "paid" && canApprove && (
            <Button variant="ghost" className="text-xs" onClick={() => setReopening(true)} disabled={busy}>
              <LockOpen size={16} /> إعادة فتح
            </Button>
          )}
        </div>

        <div className="mt-4">
          {busy ? (
            <Button disabled><Spinner /> جارٍ التنفيذ…</Button>
          ) : status === "paid" ? (
            <Badge tone="success">تم صرف رواتب هذا الشهر</Badge>
          ) : !entries.data?.length ? (
            <Button onClick={() => calc.mutate()}><Calculator size={16} /> حساب رواتب الشهر</Button>
          ) : status === "draft" ? (
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => calc.mutate()}>إعادة الحساب</Button>
              <Button onClick={() => submit.mutate()}><Send size={16} /> تقديم للمراجعة</Button>
            </div>
          ) : status === "review" ? (
            canApprove ? (
              <Button onClick={() => approve.mutate()}><CheckCircle2 size={16} /> اعتماد</Button>
            ) : (
              <Badge tone="warning">بانتظار الاعتماد من صاحب صلاحية اعتماد الرواتب</Badge>
            )
          ) : canPay ? (
            <Button variant="danger" onClick={() => setPaying(true)}><Coins size={16} /> صرف الرواتب</Button>
          ) : (
            <Badge tone="warning">معتمد — بانتظار الصرف من صاحب صلاحية صرف الرواتب</Badge>
          )}
        </div>
        {firstError && <div className="mt-3"><ErrorBox message={firstError.message} /></div>}
        {status === "approved" && (
          <p className="mt-3 text-xs text-muted">الاعتماد يسجّل الرواتب مصروفًا بانتظار الصرف؛ المبلغ يخرج من الخزنة عند الصرف. لا تتغير رواتب الشهر ولا حضوره ولا سلفه بعد الاعتماد إلا بإعادة فتحه.</p>
        )}
      </Card>

      <ConfirmDialog
        open={reopening}
        onClose={() => setReopening(false)}
        onConfirm={() => reopen.mutate()}
        title={`إعادة فتح رواتب ${month}`}
        message="يُلغى مصروف الرواتب المعتمد ويُعكس قيده، ويعود الشهر مسودة يمكن تعديلها وإعادة حسابها ثم اعتمادها من جديد."
        confirmLabel="إعادة فتح الشهر"
      />

      <Modal open={paying} onClose={() => setPaying(false)} title={`صرف رواتب ${month}`}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!pay.isPending && paySource) pay.mutate();
          }}
          className="flex flex-col gap-4"
        >
          <div className="rounded-xl border border-line bg-elevated/40 p-3 text-sm">
            <span className="text-muted">إجمالي صافي الرواتب: </span>
            <strong className="num font-black text-brand">{moneyEGP(totalNet)}</strong>
          </div>
          <div>
            <label htmlFor="payroll-source" className="mb-1 block text-sm font-medium">تُصرف من *</label>
            <PaySourceSelect id="payroll-source" value={paySource} onChange={setPaySource} />
          </div>
          {pay.isError && <ErrorBox message={(pay.error as Error).message} />}
          <Button type="submit" variant="danger" className="w-full h-10 font-bold" disabled={pay.isPending || !paySource}>
            {pay.isPending ? <Spinner /> : "تأكيد الصرف"}
          </Button>
        </form>
      </Modal>

      {entries.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
            <Skeleton className="h-10 w-full" />
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
      ) : entries.isError ? (
        <ErrorBox message={(entries.error as Error).message} onRetry={() => entries.refetch()} />
      ) : !entries.data?.length ? (
        <Card className="p-10 text-center text-sm text-muted">لم تُحسب رواتب هذا الشهر بعد — ابدأ بالحساب</Card>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">الموظف</th>
                <th className="p-3 text-start">الأساسي</th>
                <th className="p-3 text-start">حوافز</th>
                <th className="p-3 text-start">استقطاعات</th>
                <th className="p-3 text-start">سلف</th>
                <th className="p-3 text-start">الصافي</th>
                <th className="p-3 text-start"></th>
              </tr>
            </thead>
            <tbody>
              {entries.data.map((e) => (
                <tr key={e.id} className="border-b border-line/60 last:border-0 hover:bg-elevated">
                  <td className="p-3 font-semibold">{e.emp_name}</td>
                  <td className="num p-3">{money(e.base_salary)}</td>
                  <td className="num p-3 text-success-ink">{money(e.bonuses)}</td>
                  <td className="num p-3 text-danger">{money(e.deductions)}</td>
                  <td className="num p-3 text-warning-ink">{money(e.advances)}</td>
                  <td className="num p-3 font-black text-brand">{money(e.net_salary)}</td>
                  <td className="p-3">
                    <button
                      onClick={() => openPrintDoc(`/hr/payroll/report/employee/${e.employee_id}`, { month, report_type: "ticket" })}
                      className="text-xs font-semibold text-brand hover:underline"
                    >
                      قسيمة
                    </button>
                  </td>
                </tr>
              ))}
              <tr className="bg-elevated font-black">
                <td className="p-3">الإجمالي</td>
                <td colSpan={4} />
                <td className="num p-3 text-brand">{moneyEGP(totalNet)}</td>
                <td />
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
