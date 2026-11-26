// Advances (cash paid now, deducted from the salary), deductions and bonuses: paged by month and
// employee; cancelled while the month is open. An advance the month's pay couldn't cover is carried
// to the next month by the payroll (HR-9) and is cancelled only by reopening that month.
import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { HandCoins, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { date as fmtDate } from "@/lib/format";
import { sound } from "@/lib/sound";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";
import { moneyIn, useCurrency } from "@app/lib/currency";
import { amountOrNull, pageCount } from "../../finance/lib";
import { type Paged, RECORD_TYPE } from "../lib";
import { Pager, Rows, useEmployeeOptions } from "./common";

interface Advance {
  id: string; employee_id: string; emp_name: string; amount: string; date: string; note: string | null;
  record_type: string | null; status: "active" | "cancelled"; carried_from_period_id: string | null; cancel_reason: string | null;
}

const PAGE_SIZE = 50;
const emptyForm = { employee_id: "", amount: "", date: "", note: "", record_type: "سلفة", source: "" };

export function AdvancesTab() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const cur = useCurrency();
  const [month, setMonth] = useState("");
  const [employee, setEmployee] = useState("");
  const [page, setPage] = useState(1);
  const [form, setForm] = useState<typeof emptyForm | null>(null);
  const [cancelling, setCancelling] = useState<Advance | null>(null);
  const [reason, setReason] = useState("");
  const employees = useEmployeeOptions();
  const list = useQuery({
    queryKey: ["hr-advances", month, employee, page],
    queryFn: () => api.get<Paged<Advance>>("/hr/advances", { month: month || undefined, employee_id: employee || undefined, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["hr-advances"] });
    qc.invalidateQueries({ queryKey: ["safes"] });
    qc.invalidateQueries({ queryKey: ["wallets"] });
  };
  const isAdvance = form?.record_type === "سلفة";
  const amountOk = !!form && amountOrNull(form.amount) !== null;
  const create = useMutation({
    mutationFn: (f: typeof emptyForm) =>
      api.post("/hr/advances", {
        employee_id: f.employee_id, amount: amountOrNull(f.amount), date: f.date || undefined, note: f.note || null,
        record_type: f.record_type, ...(f.record_type === "سلفة" ? sourceFields(f.source) : {}),
      }),
    onSuccess: () => {
      sound.success();
      toast("success", "حُفظ السجل");
      setForm(null);
      refresh();
    },
    onError: () => sound.error(),
  });
  const cancel = useMutation({
    mutationFn: (a: Advance) => api.post(`/hr/advances/${a.id}/cancel`, { reason: reason || null }),
    onSuccess: () => {
      toast("success", "أُلغي السجل");
      setCancelling(null);
      setReason("");
      refresh();
    },
    onError: (e) => {
      setCancelling(null);
      toast("error", (e as Error).message);
    },
  });

  const rows = list.data?.items ?? [];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3 rounded-xl border border-line bg-card p-3">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="adv-month" className="mb-1 block text-xs font-medium text-muted">الشهر</label>
            <Input id="adv-month" type="month" className="num w-44" value={month} onChange={(e) => { setMonth(e.target.value); setPage(1); }} />
          </div>
          <div>
            <label htmlFor="adv-emp" className="mb-1 block text-xs font-medium text-muted">الموظف</label>
            <Select id="adv-emp" className="w-52" value={employee} onChange={(e) => { setEmployee(e.target.value); setPage(1); }}>
              <option value="">كل الموظفين</option>
              {employees.data?.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
            </Select>
          </div>
        </div>
        <Button onClick={() => setForm({ ...emptyForm, employee_id: employee })}><Plus className="size-4" /> سلفة أو خصم أو مكافأة</Button>
      </div>

      {list.isLoading ? <Rows /> : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !rows.length ? (
        <Empty text="لا توجد سلف أو خصومات أو مكافآت" icon={<HandCoins className="size-10" />} />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted">
                  <th className="p-3 text-start">الموظف</th>
                  <th className="p-3 text-start">النوع</th>
                  <th className="p-3 text-end">المبلغ</th>
                  <th className="p-3 text-start">التاريخ</th>
                  <th className="p-3 text-start">ملاحظة</th>
                  <th className="p-3 text-start">الحالة</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => {
                  const t = RECORD_TYPE[a.record_type ?? "سلفة"] ?? { label: a.record_type ?? "", tone: "warning" as const };
                  return (
                    <tr key={a.id} className={`border-b border-line/60 last:border-0 ${a.status === "cancelled" ? "opacity-60" : ""}`}>
                      <td className="p-3 font-bold">{a.emp_name}</td>
                      <td className="p-3">
                        <Badge tone={t.tone}>{t.label}</Badge> {a.carried_from_period_id && <Badge tone="brand">مرحّلة</Badge>}
                      </td>
                      <td className="num p-3 text-end font-bold">{moneyIn(a.amount, cur)}</td>
                      <td className="p-3 text-xs text-muted">{fmtDate(a.date)}</td>
                      <td className="p-3 text-xs text-muted">{a.note || "—"}{a.cancel_reason ? ` · ${a.cancel_reason}` : ""}</td>
                      <td className="p-3">
                        {a.status === "cancelled" ? <Badge tone="muted">ملغى</Badge> : a.carried_from_period_id ? (
                          <span className="text-[11px] text-muted">تُلغى بإعادة فتح شهرها</span>
                        ) : (
                          <Button variant="ghost" size="sm" className="h-7 text-xs text-danger" onClick={() => { setCancelling(a); setReason(""); }}>إلغاء</Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pager page={page} pages={pageCount(list.data?.total ?? 0, PAGE_SIZE)} total={list.data?.total ?? 0} unit="سجل" busy={list.isFetching} onPage={setPage} />
        </>
      )}

      <Modal open={!!cancelling} onClose={() => setCancelling(null)} title={`إلغاء ${cancelling?.record_type ?? "السجل"} — ${cancelling?.emp_name ?? ""}`}>
        <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (cancelling && !cancel.isPending) cancel.mutate(cancelling); }}>
          <p className="text-xs text-muted leading-relaxed">
            {cancelling?.record_type === "سلفة" || !cancelling?.record_type
              ? "يعود مبلغ السلفة إلى الخزنة أو المحفظة التي صُرف منها ويُعكس قيدها."
              : "لن يُحتسب في راتب الشهر."} لا يُلغى سجل في شهر رواتبه معتمدة.
          </p>
          <div>
            <label htmlFor="adv-reason" className="mb-1 block text-xs font-semibold text-muted">السبب</label>
            <Input id="adv-reason" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <Button type="submit" variant="danger" className="h-10 font-bold" disabled={cancel.isPending}>{cancel.isPending ? <Spinner /> : "تأكيد الإلغاء"}</Button>
        </form>
      </Modal>

      <Modal open={!!form} onClose={() => setForm(null)} title="سلفة أو خصم أو مكافأة">
        {form && (
          <form className="flex flex-col gap-3"
                onSubmit={(e) => { e.preventDefault(); if (!create.isPending && form.employee_id && amountOk && (!isAdvance || form.source)) create.mutate(form); }}>
            <div>
              <label htmlFor="advf-emp" className="mb-1 block text-xs font-semibold text-muted">الموظف *</label>
              <Select id="advf-emp" autoFocus value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}>
                <option value="">— اختر الموظف —</option>
                {employees.data?.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              </Select>
            </div>
            <div>
              <label htmlFor="advf-type" className="mb-1 block text-xs font-semibold text-muted">النوع</label>
              <Select id="advf-type" value={form.record_type} onChange={(e) => setForm({ ...form, record_type: e.target.value })}>
                <option value="سلفة">سلفة (تُصرف نقدًا الآن وتُخصم من الراتب)</option>
                <option value="خصم">خصم من الراتب</option>
                <option value="مكافأة">مكافأة تُضاف إلى الراتب</option>
              </Select>
            </div>
            {isAdvance && (
              <div>
                <label htmlFor="advf-source" className="mb-1 block text-xs font-semibold text-muted">تُصرف من *</label>
                <PaySourceSelect id="advf-source" value={form.source} onChange={(v) => setForm({ ...form, source: v })} />
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="advf-amount" className="mb-1 block text-xs font-semibold text-muted">المبلغ ({cur}) *</label>
                <Input id="advf-amount" className="num font-bold" inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
              </div>
              <div>
                <label htmlFor="advf-date" className="mb-1 block text-xs font-semibold text-muted">التاريخ (يحدد الشهر)</label>
                <Input id="advf-date" type="date" className="num" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
              </div>
            </div>
            <div>
              <label htmlFor="advf-note" className="mb-1 block text-xs font-semibold text-muted">ملاحظة</label>
              <Input id="advf-note" maxLength={1000} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
            </div>
            {isAdvance && <p className="text-[11px] text-muted">ما لا يغطيه صافي راتب الشهر من السلفة يُرحَّل للشهر التالي عند اعتماد الرواتب.</p>}
            {create.isError && <ErrorBox message={(create.error as Error).message} />}
            <Button type="submit" className="w-full h-10 font-bold" disabled={create.isPending || !form.employee_id || !amountOk || (isAdvance && !form.source)}>
              {create.isPending ? <Spinner /> : "حفظ"}
            </Button>
          </form>
        )}
      </Modal>
    </div>
  );
}
