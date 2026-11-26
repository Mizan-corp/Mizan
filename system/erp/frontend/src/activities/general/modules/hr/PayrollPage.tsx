/**
 * PAGE CONTRACT
 * Page: الرواتب (/hr/payroll)
 * User: مسؤول الرواتب (payroll)، المعتمد (payroll:approve)، الصارف (payroll:pay)
 * Purpose: حساب رواتب الشهر من الحضور، تعديلات كل راتب (مكافأة، خصم، فرق درج) وتفصيل أيامه، ثم
 * التقديم والاعتماد والصرف؛ إعادة فتح شهر معتمد بتأكيد. ما لا يغطيه الصافي من السلف يُرحَّل للشهر التالي.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, CheckCircle2, Coins, FileText, ListChecks, LockOpen, Pencil, Send } from "lucide-react";
import { api } from "@/lib/api";
import { printDocument } from "@app/lib/documents";
import { D, date as fmtDate } from "@/lib/format";
import { Badge, Button, Card, ConfirmDialog, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import { useAuth } from "@/stores/auth";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";
import { moneyIn, useCurrency } from "@app/lib/currency";
import { ATTENDANCE_STATUS, clockOf, currentMonth, PERIOD_STATUS } from "./lib";
import { Rows } from "./components/common";

// A month nobody calculated yet is a draft without an id (reading it creates nothing).
interface Period { id: string | null; month: string; status: "draft" | "review" | "approved" | "paid"; approved_amount?: string | null }
interface Entry {
  id: string; employee_id: string; emp_name: string; position: string | null; net_salary: string; base_salary: string;
  base_pay: string | null; bonus: string | null; deductions: string | null; advances: string | null; advances_carried: string | null;
  lateness_deduction: string | null; overtime_pay: string | null; bonus_payment: string | null; drawer_variance: string | null;
  working_days: number | null; notes: string | null;
}
interface Day { date: string; status: string; check_in?: string | null; check_out?: string | null; work_hours: number; late_minutes: number;
  early_minutes?: number; overtime_hours: number; note: string }
interface Breakdown { employee: string; month: string; period_status: string; breakdown: Day[] | null; entry: Record<string, string | number | null> }

const ADJUSTABLE = ["draft", "review"];

export default function PayrollPage() {
  const qc = useQueryClient();
  const cur = useCurrency();
  const [month, setMonth] = useState(currentMonth());
  const [paying, setPaying] = useState(false);
  const [paySource, setPaySource] = useState("");
  const [reopening, setReopening] = useState(false);
  const [adjusting, setAdjusting] = useState<{ entry: Entry; bonus: string; deductions: string; drawer_variance: string; notes: string } | null>(null);
  const [detail, setDetail] = useState<Entry | null>(null);
  const can = useAuth((s) => s.can);
  const canApprove = can("payroll:approve");
  const canPay = can("payroll:pay");

  const period = useQuery({
    queryKey: ["payroll-period", month],
    queryFn: () => api.get<Period>("/hr/payroll/period", { month }),
    retry: false,
    enabled: !!month,
  });
  const entries = useQuery({
    queryKey: ["payroll", month],
    queryFn: () => api.get<Entry[]>("/hr/payroll", { month }),
    enabled: !!month,
  });

  const { toast } = useToast();
  const invalidate = (msg?: string) => {
    qc.invalidateQueries({ queryKey: ["payroll-period"] });
    qc.invalidateQueries({ queryKey: ["payroll"] });
    qc.invalidateQueries({ queryKey: ["hr-advances"] });
    if (msg) toast("success", msg);
  };

  const calc = useMutation({ mutationFn: () => api.post("/hr/payroll/calculate", { month }), onSuccess: () => invalidate("تم حساب رواتب الشهر") });
  const submit = useMutation({ mutationFn: () => api.post(`/hr/payroll/period/submit?month=${month}`), onSuccess: () => invalidate("تم تقديم الشهر للمراجعة") });
  const approve = useMutation({ mutationFn: () => api.post(`/hr/payroll/period/approve?month=${month}`), onSuccess: () => invalidate("تم اعتماد الرواتب") });
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
    onError: () => setReopening(false),
  });
  const adjust = useMutation({
    mutationFn: (a: NonNullable<typeof adjusting>) =>
      api.put(`/hr/payroll/${a.entry.id}`, {
        bonus: D(a.bonus || 0).toFixed(2), deductions: D(a.deductions || 0).toFixed(2),
        drawer_variance: D(a.drawer_variance || 0).toFixed(2), notes: a.notes || null,
      }),
    onSuccess: () => { setAdjusting(null); invalidate("حُفظ تعديل الراتب"); },
  });

  const status = period.data?.status;
  const stepIndex = status ? { draft: 0, review: 1, approved: 2, paid: 3 }[status] : -1;
  const rows = entries.data ?? [];
  const totalNet = rows.reduce((s, e) => s.plus(D(e.net_salary ?? 0)), D(0));
  const totalCarried = rows.reduce((s, e) => s.plus(D(e.advances_carried ?? 0)), D(0));
  const busy = calc.isPending || submit.isPending || approve.isPending || pay.isPending || reopen.isPending;
  const actionError = (calc.error ?? submit.error ?? approve.error ?? reopen.error) as Error | null;
  const validAmount = (v: string, signed = false) => !v.trim() || (signed ? /^-?\d+(\.\d{1,2})?$/ : /^\d+(\.\d{1,2})?$/).test(v.trim());

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">الرواتب</h1>
          <p className="mt-0.5 text-xs text-muted">حساب ← تقديم ← اعتماد ← صرف. لا يتغير شهر معتمد إلا بإعادة فتحه.</p>
        </div>
        <div className="flex items-center gap-2">
          <Input type="month" className="num w-44" value={month} onChange={(e) => setMonth(e.target.value)} aria-label="الشهر" />
          <Button variant="outline" disabled={!month} onClick={() => printDocument("/hr/payroll/report/monthly", { month })}>
            <FileText size={16} /> تقرير الشهر
          </Button>
        </div>
      </div>

      {period.isError ? (
        // The period couldn't be read: no step is offered (treating it as a draft would invite a recalculation).
        <ErrorBox message={(period.error as Error).message} onRetry={() => period.refetch()} />
      ) : period.isLoading || !status ? (
        <Rows n={1} />
      ) : (
        <Card>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={PERIOD_STATUS[status].tone}>{PERIOD_STATUS[status].label}</Badge>
            {[
              { label: "حساب", icon: <Calculator size={16} /> },
              { label: "تقديم", icon: <Send size={16} /> },
              { label: "اعتماد", icon: <CheckCircle2 size={16} /> },
              { label: "صرف", icon: <Coins size={16} /> },
            ].map((s, i) => (
              <div key={s.label} className="flex items-center gap-2">
                <div className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold ${i <= stepIndex ? "bg-primary text-primary-foreground" : "bg-elevated text-muted"}`}>
                  {s.icon} {s.label}
                </div>
                {i < 3 && <span className="text-muted rtl:-scale-x-100">→</span>}
              </div>
            ))}
            {(status === "review" || status === "approved") && canApprove && (
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
            ) : entries.isSuccess && !rows.length ? (
              <Button onClick={() => calc.mutate()}><Calculator size={16} /> حساب رواتب الشهر</Button>
            ) : status === "draft" ? (
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => calc.mutate()}>إعادة الحساب</Button>
                <Button onClick={() => submit.mutate()}><Send size={16} /> تقديم للمراجعة</Button>
              </div>
            ) : status === "review" ? (
              canApprove ? <Button onClick={() => approve.mutate()}><CheckCircle2 size={16} /> اعتماد</Button>
                : <Badge tone="warning">بانتظار الاعتماد من صاحب صلاحية اعتماد الرواتب</Badge>
            ) : canPay ? (
              <Button variant="danger" onClick={() => setPaying(true)}><Coins size={16} /> صرف الرواتب</Button>
            ) : (
              <Badge tone="warning">معتمد — بانتظار الصرف من صاحب صلاحية صرف الرواتب</Badge>
            )}
          </div>
          {actionError && <div className="mt-3"><ErrorBox message={actionError.message} /></div>}
          {status === "approved" && (
            <p className="mt-3 text-xs text-muted">الاعتماد يسجّل الرواتب مصروفًا بانتظار الصرف؛ المبلغ يخرج من الخزنة عند الصرف. لا تتغير رواتب الشهر ولا حضوره ولا سلفه بعد الاعتماد إلا بإعادة فتحه.</p>
          )}
          {totalCarried.gt(0) && (
            <p className="mt-3 text-xs text-muted">
              سلف لم يغطها صافي الرواتب: <span className="num font-semibold text-ink">{moneyIn(totalCarried, cur)}</span>
              {status === "approved" || status === "paid" ? " — رُحّلت سلفاً مفتوحة للشهر التالي." : " — تُرحَّل للشهر التالي عند الاعتماد."}
            </p>
          )}
        </Card>
      )}

      <ConfirmDialog
        open={reopening}
        onClose={() => setReopening(false)}
        onConfirm={() => !reopen.isPending && reopen.mutate()}
        title={`إعادة فتح رواتب ${month}`}
        message="يُلغى مصروف الرواتب المعتمد ويُعكس قيده، وتُلغى السلف التي رُحّلت منه للشهر التالي، ويعود الشهر مسودة يمكن تعديلها وإعادة حسابها ثم اعتمادها من جديد. لا يُعاد فتح شهر صُرف."
        confirmLabel="إعادة فتح الشهر"
      />

      <Modal open={paying} onClose={() => setPaying(false)} title={`صرف رواتب ${month}`}>
        <form onSubmit={(e) => { e.preventDefault(); if (!pay.isPending && paySource) pay.mutate(); }} className="flex flex-col gap-4">
          <div className="rounded-xl border border-line bg-elevated/40 p-3 text-sm">
            <span className="text-muted">إجمالي صافي الرواتب: </span>
            <strong className="num font-black">{moneyIn(period.data?.approved_amount ?? totalNet, cur)}</strong>
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

      <Modal open={!!adjusting} onClose={() => setAdjusting(null)} title={`تعديلات راتب ${adjusting?.entry.emp_name ?? ""}`}>
        {adjusting && (
          <form className="flex flex-col gap-3" onSubmit={(e) => {
            e.preventDefault();
            if (!adjust.isPending && validAmount(adjusting.bonus) && validAmount(adjusting.deductions) && validAmount(adjusting.drawer_variance, true)) adjust.mutate(adjusting);
          }}>
            <p className="text-xs text-muted">تحل محل المكافآت والخصومات المحسوبة من السجلات لهذا الشهر، ويُعاد تكوين الصافي من الأجر المستحق. يُسجَّل التعديل في سجل التدقيق.</p>
            <div className="grid grid-cols-3 gap-3">
              {([["bonus", "مكافأة"], ["deductions", "خصومات"], ["drawer_variance", "فرق الدرج (±)"]] as const).map(([k, label]) => (
                <div key={k}>
                  <label htmlFor={`adj-${k}`} className="mb-1 block text-xs font-semibold text-muted">{label}</label>
                  <Input id={`adj-${k}`} className="num" inputMode="decimal" value={adjusting[k]} onChange={(e) => setAdjusting({ ...adjusting, [k]: e.target.value })} />
                </div>
              ))}
            </div>
            <div>
              <label htmlFor="adj-notes" className="mb-1 block text-xs font-semibold text-muted">ملاحظات</label>
              <Input id="adj-notes" maxLength={1000} value={adjusting.notes} onChange={(e) => setAdjusting({ ...adjusting, notes: e.target.value })} />
            </div>
            {adjust.isError && <ErrorBox message={(adjust.error as Error).message} />}
            <Button type="submit" className="h-10 font-bold" disabled={adjust.isPending}>{adjust.isPending ? <Spinner /> : "حفظ"}</Button>
          </form>
        )}
      </Modal>

      <BreakdownModal entry={detail} onClose={() => setDetail(null)} currency={cur} />

      {entries.isLoading ? <Rows /> : entries.isError ? (
        <ErrorBox message={(entries.error as Error).message} onRetry={() => entries.refetch()} />
      ) : !rows.length ? (
        <Card className="p-10 text-center text-sm text-muted">لم تُحسب رواتب هذا الشهر بعد — ابدأ بالحساب</Card>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">الموظف</th>
                <th className="p-3 text-end">الأساسي</th>
                <th className="p-3 text-end">المستحق</th>
                <th className="p-3 text-end">مكافآت وإضافي</th>
                <th className="p-3 text-end">خصومات وتأخير</th>
                <th className="p-3 text-end">سلف</th>
                <th className="p-3 text-end">الصافي</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => {
                const plus = D(e.bonus ?? 0).plus(D(e.overtime_pay ?? 0)).plus(D(e.bonus_payment ?? 0));
                const minus = D(e.deductions ?? 0).plus(D(e.lateness_deduction ?? 0));
                return (
                  <tr key={e.id} className="border-b border-line/60 last:border-0 hover:bg-elevated">
                    <td className="p-3 font-semibold">{e.emp_name}{e.notes ? <div className="text-[11px] font-normal text-muted">{e.notes}</div> : null}</td>
                    <td className="num p-3 text-end">{moneyIn(e.base_salary, cur)}</td>
                    <td className="num p-3 text-end">{e.base_pay != null ? moneyIn(e.base_pay, cur) : "—"}</td>
                    <td className="num p-3 text-end text-success-ink">{moneyIn(plus, cur)}</td>
                    <td className="num p-3 text-end text-danger">{moneyIn(minus, cur)}</td>
                    <td className="num p-3 text-end">
                      {moneyIn(e.advances ?? 0, cur)}
                      {D(e.advances_carried ?? 0).gt(0) && <div className="text-[10px] text-muted">يُرحَّل منها {moneyIn(e.advances_carried!, cur)}</div>}
                    </td>
                    <td className="num p-3 text-end font-black">{moneyIn(e.net_salary, cur)}</td>
                    <td className="p-3">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تفصيل أيام ${e.emp_name}`} onClick={() => setDetail(e)}>
                          <ListChecks className="size-4" />
                        </Button>
                        {status && ADJUSTABLE.includes(status) && (
                          <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل راتب ${e.emp_name}`}
                                  onClick={() => setAdjusting({ entry: e, bonus: D(e.bonus ?? 0).toFixed(2), deductions: D(e.deductions ?? 0).toFixed(2),
                                                                drawer_variance: D(e.drawer_variance ?? 0).toFixed(2), notes: e.notes ?? "" })}>
                            <Pencil className="size-4" />
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={() => printDocument(`/hr/payroll/report/employee/${e.employee_id}`, { month, report_type: "ticket" })}>
                          قسيمة
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              <tr className="bg-elevated font-black">
                <td className="p-3">الإجمالي</td>
                <td colSpan={5} />
                <td className="num p-3 text-end">{moneyIn(totalNet, cur)}</td>
                <td />
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const ENTRY_LINES: { key: string; label: string; sign: "+" | "-" | "" }[] = [
  { key: "base_salary", label: "الراتب الأساسي", sign: "" },
  { key: "base_pay", label: "المستحق عن ساعات العمل", sign: "" },
  { key: "overtime_pay", label: "العمل الإضافي", sign: "+" },
  { key: "bonus_payment", label: "أيام إضافية", sign: "+" },
  { key: "bonus", label: "مكافآت", sign: "+" },
  { key: "drawer_variance", label: "فرق الدرج", sign: "+" },
  { key: "lateness_deduction", label: "خصم التأخير والانصراف المبكر", sign: "-" },
  { key: "deductions", label: "خصومات", sign: "-" },
  { key: "advances", label: "سلف", sign: "-" },
  { key: "advances_carried", label: "منها يُرحَّل للشهر التالي", sign: "" },
  { key: "net_salary", label: "الصافي", sign: "" },
];

function BreakdownModal({ entry, onClose, currency }: { entry: Entry | null; onClose: () => void; currency: string }) {
  const q = useQuery({
    queryKey: ["payroll-breakdown", entry?.id],
    queryFn: () => api.get<Breakdown>(`/hr/payroll/${entry!.id}/breakdown`),
    enabled: !!entry,
  });
  const d = q.data;
  return (
    <Modal open={!!entry} onClose={onClose} title={`تفصيل راتب ${entry?.emp_name ?? ""}`} wide>
      {q.isLoading ? <Rows n={4} /> : q.isError ? (
        <ErrorBox message={(q.error as Error).message} onRetry={() => q.refetch()} />
      ) : d ? (
        <div className="flex flex-col gap-4">
          <table className="w-full text-sm">
            <tbody>
              {ENTRY_LINES.filter((l) => d.entry[l.key] != null && (l.key === "net_salary" || l.key === "base_salary" || !D(String(d.entry[l.key])).isZero())).map((l) => (
                <tr key={l.key} className={`border-b border-line/60 ${l.key === "net_salary" ? "font-black" : ""}`}>
                  <td className="p-2">{l.label}</td>
                  <td className="num p-2 text-end">{l.sign === "-" ? "−" : l.sign}{moneyIn(String(d.entry[l.key]), currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="max-h-96 overflow-auto rounded-xl border border-line">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card">
                <tr className="border-b border-line text-muted">
                  <th className="p-2 text-start">اليوم</th>
                  <th className="p-2 text-start">الحالة</th>
                  <th className="p-2 text-start">حضور</th>
                  <th className="p-2 text-start">انصراف</th>
                  <th className="p-2 text-end">ساعات</th>
                  <th className="p-2 text-end">تأخير (د)</th>
                  <th className="p-2 text-end">إضافي (س)</th>
                  <th className="p-2 text-start">ملاحظة</th>
                </tr>
              </thead>
              <tbody>
                {(d.breakdown ?? []).map((day) => {
                  const st = ATTENDANCE_STATUS[day.status] ?? { label: day.status, tone: "muted" as const };
                  return (
                    <tr key={day.date} className="border-b border-line/50 last:border-0">
                      <td className="p-2 whitespace-nowrap">{fmtDate(day.date)}</td>
                      <td className="p-2"><Badge tone={st.tone}>{st.label}</Badge></td>
                      <td className="num p-2" dir="ltr">{clockOf(day.check_in)}</td>
                      <td className="num p-2" dir="ltr">{clockOf(day.check_out)}</td>
                      <td className="num p-2 text-end">{day.work_hours || "—"}</td>
                      <td className="num p-2 text-end">{day.late_minutes || "—"}</td>
                      <td className="num p-2 text-end">{day.overtime_hours || "—"}</td>
                      <td className="p-2 text-muted">{day.note || ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
