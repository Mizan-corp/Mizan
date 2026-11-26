// Employees: create, edit (hire date, shift, salary…), stop and bring back; an employee's detailed
// report or payslip for a month (opened with a print token).
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Pencil, Power, UserPlus, Users } from "lucide-react";
import { api } from "@/lib/api";
import { date as fmtDate } from "@/lib/format";
import { sound } from "@/lib/sound";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { printDocument } from "@app/lib/documents";
import { moneyIn, useCurrency } from "@app/lib/currency";
import { amountOrNull, pageCount } from "../../finance/lib";
import { currentMonth } from "../lib";
import { EMPLOYEES_PAGE, type Employee, Pager, Rows, useEmployees, useShifts } from "./common";

interface Form {
  id?: string;
  name: string;
  emp_code: string;
  position: string;
  monthly_salary: string;
  hire_date: string;
  shift_id: string;
  shift_schedule: string;
  ignore_lateness: boolean;
  max_lateness: string;
}

const empty: Form = { name: "", emp_code: "", position: "", monthly_salary: "", hire_date: "", shift_id: "", shift_schedule: "",
  ignore_lateness: false, max_lateness: "30" };

const formOf = (e: Employee): Form => ({
  id: e.id, name: e.name, emp_code: e.emp_code ?? "", position: e.position ?? "", monthly_salary: String(e.monthly_salary ?? ""),
  hire_date: e.hire_date ?? "", shift_id: e.shift_id ?? "", shift_schedule: e.shift_schedule ?? "",
  ignore_lateness: !!e.ignore_lateness, max_lateness: String(e.max_lateness_before_overtime_cancellation ?? 30),
});

export function EmployeesTab() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const cur = useCurrency();
  const [all, setAll] = useState(false);
  const [form, setForm] = useState<Form | null>(null);
  const [stopping, setStopping] = useState<Employee | null>(null);
  const [report, setReport] = useState<{ emp: Employee; month: string } | null>(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const list = useEmployees(all, page, q);
  const shifts = useShifts();
  const refresh = () => qc.invalidateQueries({ queryKey: ["hr-employees"] });

  const salaryOk = (f: Form) => !f.monthly_salary.trim() || amountOrNull(f.monthly_salary) !== null || Number(f.monthly_salary) === 0;
  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = {
        name: f.name.trim(), position: f.position.trim() || null,
        monthly_salary: f.monthly_salary.trim() ? amountOrNull(f.monthly_salary) ?? "0" : "0",
        hire_date: f.hire_date || null, shift_id: f.shift_id || null,
        shift_schedule: f.shift_id ? null : f.shift_schedule.trim() || null,
        ignore_lateness: f.ignore_lateness,
        max_lateness_before_overtime_cancellation: Number(f.max_lateness) || 0,
      };
      return f.id ? api.put(`/hr/employees/${f.id}`, body) : api.post("/hr/employees", { ...body, emp_code: f.emp_code.trim() || null });
    },
    onSuccess: (_r, f) => {
      sound.success();
      toast("success", f.id ? "حُفظ الموظف" : "أُضيف الموظف");
      setForm(null);
      refresh();
    },
    onError: () => sound.error(),
  });
  const setActive = useMutation({
    mutationFn: ({ e, active }: { e: Employee; active: boolean }) =>
      active ? api.put(`/hr/employees/${e.id}`, { is_active: true }) : api.del(`/hr/employees/${e.id}`),
    onSuccess: (_r, { active }) => {
      toast("success", active ? "أُعيد تفعيل الموظف" : "أُوقف الموظف");
      setStopping(null);
      refresh();
    },
    onError: (err) => {
      setStopping(null);
      toast("error", (err as Error).message);
    },
  });

  const activeShifts = (shifts.data ?? []).filter((s) => s.is_active || s.id === form?.shift_id);
  const rows = list.data?.items ?? [];
  const total = list.data?.total ?? 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Input className="w-56" type="search" maxLength={100} aria-label="بحث بالاسم أو الكود" placeholder="بحث بالاسم أو الكود"
                 value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          <label className="flex items-center gap-2 text-xs text-muted">
            <input type="checkbox" checked={all} onChange={(e) => { setAll(e.target.checked); setPage(1); }} /> إظهار الموظفين الموقوفين
          </label>
        </div>
        <Button onClick={() => setForm({ ...empty })}><UserPlus className="size-4" /> موظف جديد</Button>
      </div>
      {list.isLoading ? <Rows /> : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !rows.length ? (
        <Empty text={q.trim() ? "لا يوجد موظف بهذا الاسم أو الكود" : "لا يوجد موظفون"} hint="أضف الموظفين برواتبهم ووردياتهم لحساب الرواتب من الحضور" icon={<Users className="size-10" />}
               action={<Button onClick={() => setForm({ ...empty })}><UserPlus className="size-4" /> موظف جديد</Button>} />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">الكود</th>
                <th className="p-3 text-start">الاسم</th>
                <th className="p-3 text-start">الوظيفة</th>
                <th className="p-3 text-start">الوردية</th>
                <th className="p-3 text-start">تاريخ التعيين</th>
                <th className="p-3 text-end">الراتب الشهري</th>
                <th className="p-3 text-start">الحالة</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id} className={`border-b border-line/60 last:border-0 hover:bg-elevated/40 ${e.is_active ? "" : "opacity-60"}`}>
                  <td className="num p-3 text-muted" dir="ltr">{e.emp_code ?? "—"}</td>
                  <td className="p-3 font-bold">{e.name}</td>
                  <td className="p-3">{e.position || "—"}</td>
                  <td className="p-3 text-xs">{e.shift_name ?? (e.shift_schedule ? <span className="num" dir="ltr">{e.shift_schedule}</span> : "الافتراضية")}</td>
                  <td className="p-3 text-xs text-muted">{e.hire_date ? fmtDate(e.hire_date) : "—"}</td>
                  <td className="num p-3 text-end font-bold">{moneyIn(e.monthly_salary, cur)}</td>
                  <td className="p-3"><Badge tone={e.is_active ? "success" : "muted"}>{e.is_active ? "نشط" : "موقوف"}</Badge></td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تقرير ${e.name}`}
                              onClick={() => setReport({ emp: e, month: currentMonth() })}>
                        <FileText className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل ${e.name}`} onClick={() => setForm(formOf(e))}>
                        <Pencil className="size-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={e.is_active ? `إيقاف ${e.name}` : `تفعيل ${e.name}`}
                              disabled={setActive.isPending}
                              onClick={() => (e.is_active ? setStopping(e) : setActive.mutate({ e, active: true }))}>
                        <Power className="size-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <Pager page={page} pages={pageCount(total, EMPLOYEES_PAGE)} total={total} unit="موظف" busy={list.isFetching} onPage={setPage} />
        </>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? `تعديل ${form.name}` : "موظف جديد"} wide>
        {form && (
          <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (!save.isPending && form.name.trim() && salaryOk(form)) save.mutate(form); }}>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-2">
                <label htmlFor="emp-name" className="mb-1 block text-xs font-semibold text-muted">الاسم *</label>
                <Input id="emp-name" autoFocus maxLength={128} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div>
                <label htmlFor="emp-code" className="mb-1 block text-xs font-semibold text-muted">الكود (جهاز البصمة)</label>
                <Input id="emp-code" dir="ltr" maxLength={32} disabled={!!form.id} value={form.emp_code}
                       onChange={(e) => setForm({ ...form, emp_code: e.target.value })} />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label htmlFor="emp-pos" className="mb-1 block text-xs font-semibold text-muted">الوظيفة</label>
                <Input id="emp-pos" maxLength={64} value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} />
              </div>
              <div>
                <label htmlFor="emp-salary" className="mb-1 block text-xs font-semibold text-muted">الراتب الشهري ({cur})</label>
                <Input id="emp-salary" className="num" inputMode="decimal" value={form.monthly_salary}
                       onChange={(e) => setForm({ ...form, monthly_salary: e.target.value })} />
                {!salaryOk(form) && <p className="mt-1 text-[11px] text-danger">رقم موجب بحد أقصى منزلتين عشريتين</p>}
              </div>
              <div>
                <label htmlFor="emp-hire" className="mb-1 block text-xs font-semibold text-muted">تاريخ التعيين</label>
                <Input id="emp-hire" type="date" className="num" value={form.hire_date} onChange={(e) => setForm({ ...form, hire_date: e.target.value })} />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="emp-shift" className="mb-1 block text-xs font-semibold text-muted">الوردية</label>
                <Select id="emp-shift" value={form.shift_id} onChange={(e) => setForm({ ...form, shift_id: e.target.value })}>
                  <option value="">— بلا وردية من القائمة —</option>
                  {activeShifts.map((s) => <option key={s.id} value={s.id}>{`${s.name} (${s.start_time}–${s.end_time})`}</option>)}
                </Select>
              </div>
              {!form.shift_id && (
                <div>
                  <label htmlFor="emp-schedule" className="mb-1 block text-xs font-semibold text-muted">أو مواعيد مكتوبة</label>
                  <Input id="emp-schedule" dir="ltr" className="num" maxLength={64} placeholder="09:00-17:00" value={form.shift_schedule}
                         onChange={(e) => setForm({ ...form, shift_schedule: e.target.value })} />
                  <p className="mt-1 text-[11px] text-muted">فارغ: الوردية الافتراضية من إعدادات الرواتب.</p>
                </div>
              )}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex items-center gap-2 text-xs font-medium">
                <input type="checkbox" checked={form.ignore_lateness} onChange={(e) => setForm({ ...form, ignore_lateness: e.target.checked })} />
                لا يُخصم منه تأخير
              </label>
              <div>
                <label htmlFor="emp-maxlate" className="mb-1 block text-xs font-semibold text-muted">تأخير يلغي الإضافي (دقائق)</label>
                <Input id="emp-maxlate" type="number" min={0} max={1440} className="num" value={form.max_lateness}
                       onChange={(e) => setForm({ ...form, max_lateness: e.target.value })} />
              </div>
            </div>
            <p className="text-[11px] text-muted">يُطبَّق الراتب والوردية الجديدان من الحساب التالي؛ الشهر المعتمد يبقى كما اعتُمد. كل تعديل يُسجَّل في سجل التدقيق.</p>
            {save.isError && <ErrorBox message={(save.error as Error).message} />}
            <Button type="submit" className="w-full h-10 font-bold" disabled={save.isPending || !form.name.trim() || !salaryOk(form)}>
              {save.isPending ? <Spinner /> : "حفظ"}
            </Button>
          </form>
        )}
      </Modal>

      <Modal open={!!report} onClose={() => setReport(null)} title={`تقرير ${report?.emp.name ?? ""}`}>
        {report && (
          <div className="flex flex-col gap-4">
            <div>
              <label htmlFor="rep-month" className="mb-1 block text-xs font-semibold text-muted">الشهر</label>
              <Input id="rep-month" type="month" className="num w-44" value={report.month} onChange={(e) => setReport({ ...report, month: e.target.value })} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={!report.month}
                      onClick={() => printDocument(`/hr/payroll/report/employee/${report.emp.id}`, { month: report.month, report_type: "detailed" })}>
                <FileText className="size-4" /> التقرير التفصيلي
              </Button>
              <Button variant="outline" disabled={!report.month}
                      onClick={() => printDocument(`/hr/payroll/report/employee/${report.emp.id}`, { month: report.month, report_type: "ticket" })}>
                <FileText className="size-4" /> قسيمة الراتب
              </Button>
            </div>
            <p className="text-[11px] text-muted">الشهر المعتمد يُعرض كما اعتُمد؛ الشهر الذي لم يُحسب بعد يُعرض تقديراً من الحضور الحالي.</p>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!stopping}
        onClose={() => setStopping(null)}
        onConfirm={() => stopping && setActive.mutate({ e: stopping, active: false })}
        title={`إيقاف ${stopping?.name ?? ""}`}
        message="لا يدخل الموظف الموقوف في حساب الرواتب القادمة ولا يُختار في الحضور والسلف، ويبقى سجله ورواتبه السابقة. يمكن إعادة تفعيله."
        confirmLabel="إيقاف"
      />
    </div>
  );
}
