// Attendance: the month's days, paged and filtered by employee; a day entered or corrected by hand
// (kept by later imports); a CSV import from the fingerprint device; the month's attendance report.
import { useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, FileText, Pencil, Plus, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { date as fmtDate } from "@/lib/format";
import { sound } from "@/lib/sound";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner, useToast } from "@/components/ui";
import { printDocument } from "@app/lib/documents";
import { pageCount } from "../../finance/lib";
import { ATTENDANCE_STATUS, clockOf, currentMonth, type Paged } from "../lib";
import { Pager, Rows, useEmployeeOptions, useShifts } from "./common";

interface Attendance {
  id: string; employee_id: string; emp_name: string; work_date: string; check_in: string | null; check_out: string | null;
  status: string; edited: boolean | null; edit_reason: string | null; notes: string | null; shift_override: string | null;
  excuse_no_late: boolean | null; excuse_no_early: boolean | null; excuse_allow_overtime: boolean | null;
}
interface ImportResult { added: number; updated: number; skipped: number; total: number; errors: string[] }

const PAGE_SIZE = 50;
const emptyForm = { employee_id: "", work_date: "", check_in: "", check_out: "", status: "present", edit_reason: "", notes: "",
  shift_override: "", excuse_no_late: false, excuse_no_early: false, excuse_allow_overtime: false };
type Form = typeof emptyForm;

export function AttendanceTab() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [month, setMonth] = useState(currentMonth());
  const [employee, setEmployee] = useState("");
  const [page, setPage] = useState(1);
  const [form, setForm] = useState<Form | null>(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const file = useRef<HTMLInputElement>(null);

  const employees = useEmployeeOptions();
  const shifts = useShifts();
  const att = useQuery({
    queryKey: ["hr-attendance", month, employee, page],
    queryFn: () => api.get<Paged<Attendance>>("/hr/attendance", { month, employee_id: employee || undefined, page, page_size: PAGE_SIZE }),
    placeholderData: keepPreviousData,
    enabled: !!month,
  });
  const save = useMutation({
    mutationFn: (f: Form) =>
      api.post("/hr/attendance", {
        employee_id: f.employee_id, work_date: f.work_date, check_in: f.check_in || null, check_out: f.check_out || null,
        status: f.status, edit_reason: f.edit_reason || null, notes: f.notes || null, shift_override: f.shift_override || null,
        excuse_no_late: f.excuse_no_late, excuse_no_early: f.excuse_no_early, excuse_allow_overtime: f.excuse_allow_overtime,
      }),
    onSuccess: () => {
      sound.success();
      toast("success", "حُفظ يوم الحضور");
      setForm(null);
      qc.invalidateQueries({ queryKey: ["hr-attendance"] });
    },
    onError: () => sound.error(),
  });
  const upload = useMutation({
    mutationFn: (f: File) => {
      const data = new FormData();
      data.append("file", f);
      return api.postForm<ImportResult>("/hr/attendance/import-csv", data);
    },
    onSuccess: (r) => {
      sound.success();
      setResult(r);
      qc.invalidateQueries({ queryKey: ["hr-attendance"] });
    },
    onError: () => sound.error(),
  });

  const rows = att.data?.items ?? [];
  const pages = pageCount(att.data?.total ?? 0, PAGE_SIZE);
  const editOf = (a: Attendance): Form => ({
    employee_id: a.employee_id, work_date: a.work_date, check_in: clockOf(a.check_in).replace("—", ""), check_out: clockOf(a.check_out).replace("—", ""),
    status: a.status, edit_reason: "", notes: a.notes ?? "", shift_override: a.shift_override ?? "",
    excuse_no_late: !!a.excuse_no_late, excuse_no_early: !!a.excuse_no_early, excuse_allow_overtime: !!a.excuse_allow_overtime,
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3 rounded-xl border border-line bg-card p-3">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="att-month" className="mb-1 block text-xs font-medium text-muted">الشهر</label>
            <Input id="att-month" type="month" className="num w-44" value={month} onChange={(e) => { setMonth(e.target.value); setPage(1); }} />
          </div>
          <div>
            <label htmlFor="att-emp" className="mb-1 block text-xs font-medium text-muted">الموظف</label>
            <Select id="att-emp" className="w-52" value={employee} onChange={(e) => { setEmployee(e.target.value); setPage(1); }}>
              <option value="">كل الموظفين</option>
              {employees.data?.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
            </Select>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={!month} onClick={() => printDocument("/hr/attendance/report", { month })}>
            <FileText className="size-4" /> تقرير الحضور
          </Button>
          <Button variant="outline" onClick={() => { setResult(null); setImporting(true); }}><Upload className="size-4" /> استيراد ملف البصمة</Button>
          <Button onClick={() => setForm({ ...emptyForm, employee_id: employee })}><Plus className="size-4" /> تسجيل يوم</Button>
        </div>
      </div>

      {att.isLoading ? <Rows /> : att.isError ? (
        <ErrorBox message={(att.error as Error).message} onRetry={() => att.refetch()} />
      ) : !rows.length ? (
        <Empty text="لا توجد سجلات حضور في هذا الشهر" hint="استورد ملف جهاز البصمة أو سجّل الأيام يدوياً" icon={<CalendarClock className="size-10" />} />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-card">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-muted">
                  <th className="p-3 text-start">الموظف</th>
                  <th className="p-3 text-start">اليوم</th>
                  <th className="p-3 text-start">الحضور</th>
                  <th className="p-3 text-start">الانصراف</th>
                  <th className="p-3 text-start">الحالة</th>
                  <th className="p-3 text-start">ملاحظات</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => {
                  const st = ATTENDANCE_STATUS[a.status] ?? { label: a.status, tone: "muted" as const };
                  return (
                    <tr key={a.id} className="border-b border-line/60 last:border-0 hover:bg-elevated/40">
                      <td className="p-3 font-bold">{a.emp_name}</td>
                      <td className="p-3 text-xs text-muted">{fmtDate(a.work_date)}</td>
                      <td className="num p-3" dir="ltr">{clockOf(a.check_in)}</td>
                      <td className="num p-3" dir="ltr">{clockOf(a.check_out)}</td>
                      <td className="p-3"><Badge tone={st.tone}>{st.label}</Badge></td>
                      <td className="p-3 text-xs text-muted">
                        {a.edited && <Badge tone="warning">يدوي</Badge>} {[a.edit_reason, a.notes].filter(Boolean).join(" · ")}
                      </td>
                      <td className="p-3">
                        <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل يوم ${a.emp_name}`} onClick={() => setForm(editOf(a))}>
                          <Pencil className="size-4" />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pager page={page} pages={pages} total={att.data?.total ?? 0} unit="يوم حضور" busy={att.isFetching} onPage={setPage} />
        </>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title="تسجيل يوم حضور">
        {form && (
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (!save.isPending && form.employee_id && form.work_date) save.mutate(form); }}>
            <div>
              <label htmlFor="af-emp" className="mb-1 block text-xs font-semibold text-muted">الموظف *</label>
              <Select id="af-emp" autoFocus value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}>
                <option value="">— اختر الموظف —</option>
                {employees.data?.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              </Select>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label htmlFor="af-day" className="mb-1 block text-xs font-semibold text-muted">اليوم *</label>
                <Input id="af-day" type="date" className="num" value={form.work_date} onChange={(e) => setForm({ ...form, work_date: e.target.value })} />
              </div>
              <div>
                <label htmlFor="af-in" className="mb-1 block text-xs font-semibold text-muted">الحضور</label>
                <Input id="af-in" type="time" className="num" value={form.check_in} onChange={(e) => setForm({ ...form, check_in: e.target.value })} />
              </div>
              <div>
                <label htmlFor="af-out" className="mb-1 block text-xs font-semibold text-muted">الانصراف</label>
                <Input id="af-out" type="time" className="num" value={form.check_out} onChange={(e) => setForm({ ...form, check_out: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="af-status" className="mb-1 block text-xs font-semibold text-muted">الحالة</label>
                <Select id="af-status" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                  {["present", "absent", "leave", "mission", "excuse"].map((k) => <option key={k} value={k}>{ATTENDANCE_STATUS[k].label}</option>)}
                </Select>
              </div>
              <div>
                <label htmlFor="af-shift" className="mb-1 block text-xs font-semibold text-muted">وردية مختلفة لهذا اليوم</label>
                <Select id="af-shift" value={form.shift_override} onChange={(e) => setForm({ ...form, shift_override: e.target.value })}>
                  <option value="">— ورديته المعتادة —</option>
                  {shifts.data?.filter((s) => s.is_active).map((s) => <option key={s.id} value={s.id}>{`${s.name} (${s.start_time}–${s.end_time})`}</option>)}
                </Select>
              </div>
            </div>
            {form.status === "excuse" && (
              <div className="flex flex-wrap gap-4 text-xs">
                <label className="flex items-center gap-1.5"><input type="checkbox" checked={form.excuse_no_late} onChange={(e) => setForm({ ...form, excuse_no_late: e.target.checked })} /> بلا خصم تأخير</label>
                <label className="flex items-center gap-1.5"><input type="checkbox" checked={form.excuse_no_early} onChange={(e) => setForm({ ...form, excuse_no_early: e.target.checked })} /> بلا خصم انصراف مبكر</label>
                <label className="flex items-center gap-1.5"><input type="checkbox" checked={form.excuse_allow_overtime} onChange={(e) => setForm({ ...form, excuse_allow_overtime: e.target.checked })} /> يُحتسب الإضافي</label>
              </div>
            )}
            <div>
              <label htmlFor="af-reason" className="mb-1 block text-xs font-semibold text-muted">سبب الإدخال اليدوي</label>
              <Input id="af-reason" maxLength={500} value={form.edit_reason} placeholder="مثلاً: نسي البصمة"
                     onChange={(e) => setForm({ ...form, edit_reason: e.target.value })} />
            </div>
            <p className="text-xs text-muted">اليوم المسجّل يدويًا لا يستبدله استيراد ملف الحضور لاحقًا. لا يُسجّل حضور في شهر رواتبه معتمدة أو مصروفة.</p>
            {save.isError && <ErrorBox message={(save.error as Error).message} />}
            <Button type="submit" className="w-full h-10 font-bold" disabled={save.isPending || !form.employee_id || !form.work_date}>
              {save.isPending ? <Spinner /> : "حفظ"}
            </Button>
          </form>
        )}
      </Modal>

      <Modal open={importing} onClose={() => setImporting(false)} title="استيراد ملف الحضور (CSV)">
        <div className="flex flex-col gap-4">
          <p className="text-xs text-muted leading-relaxed">
            ملف CSV بترميز UTF-8 حتى 5 ميجابايت، فيه عمود لكود الموظف أو اسمه وعمود للتاريخ، وعمودا الحضور والانصراف. الأيام المسجلة يدوياً
            تبقى كما هي، وأيام الأشهر المعتمدة رواتبها لا تُستورد.
          </p>
          <input ref={file} type="file" accept=".csv,text/csv" aria-label="ملف الحضور" className="text-sm"
                 onChange={(e) => { const f = e.target.files?.[0]; if (f) { setResult(null); upload.mutate(f); } }} />
          {upload.isPending && <div className="flex items-center gap-2 text-sm"><Spinner /> جارٍ الاستيراد…</div>}
          {upload.isError && <ErrorBox message={(upload.error as Error).message} />}
          {result && (
            <div className="rounded-xl border border-line bg-elevated/40 p-3 text-sm">
              <p className="font-semibold">أُضيف <span className="num">{result.added}</span> يوماً، وحُدّث <span className="num">{result.updated}</span>، وتُرك <span className="num">{result.skipped}</span>.</p>
              {!!result.errors.length && (
                <ul className="mt-2 list-disc ps-5 text-xs text-danger">{result.errors.map((e, i) => <li key={i}>{e}</li>)}</ul>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
