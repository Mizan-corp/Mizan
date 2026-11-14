import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, UserPlus } from "lucide-react";
import { Skeleton } from "@/components/kit/skeleton";
import { api } from "@/lib/api";
import { D, date as fmtDate, money, moneyEGP } from "@/lib/format";
import { Badge, Button, Empty, ErrorBox, Input, Modal, Select, Spinner } from "@/components/ui";
import { PaySourceSelect, sourceFields } from "@app/components/PaySourceSelect";

interface Employee { id: string; emp_code: string | null; name: string; position: string | null; monthly_salary: string; is_active: boolean }
interface Attendance { id: string; employee_id: string; work_date: string; check_in: string | null; check_out: string | null; status: string }
interface Advance { id: string; employee_id: string; amount: string; date: string; note: string | null; record_type: string | null }

export default function HrPage() {
  const [tab, setTab] = useState("employees");
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">الموارد البشرية</h1>
      <div className="flex flex-wrap gap-2">
        {[
          { k: "employees", l: "الموظفون" },
          { k: "attendance", l: "الحضور" },
          { k: "advances", l: "السلف" },
        ].map((t) => (
          <button
            key={t.k}
            onClick={() => setTab(t.k)}
            className={`rounded-full px-4 py-2 text-sm font-semibold ${tab === t.k ? "bg-brand text-brand-ink" : "border border-line text-muted hover:text-ink"}`}
          >
            {t.l}
          </button>
        ))}
      </div>
      {tab === "employees" && <EmployeesTab />}
      {tab === "attendance" && <AttendanceTab />}
      {tab === "advances" && <AdvancesTab />}
    </div>
  );
}

function EmployeesTab() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", emp_code: "", position: "", monthly_salary: "" });

  const list = useQuery({ queryKey: ["hr-employees"], queryFn: () => api.get<Employee[]>("/hr/employees") });
  const create = useMutation({
    mutationFn: () =>
      api.post("/hr/employees", {
        name: form.name,
        emp_code: form.emp_code || undefined,
        position: form.position || undefined,
        monthly_salary: form.monthly_salary ? D(form.monthly_salary).toNumber() : undefined,
      }),
    onSuccess: () => { setCreating(false); setForm({ name: "", emp_code: "", position: "", monthly_salary: "" }); qc.invalidateQueries({ queryKey: ["hr-employees"] }); },
  });

  const empList: Employee[] = Array.isArray(list.data) ? list.data : ((list.data as any)?.items ?? []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-end">
        <Button onClick={() => setCreating(true)}><UserPlus size={16} /> موظف جديد</Button>
      </div>
      {list.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
          <Skeleton className="h-10 w-full" />
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !empList.length ? (
        <Empty text="لا يوجد موظفون" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted bg-secondary/20">
                <th className="p-3 text-start">الكود</th>
                <th className="p-3 text-start">الاسم</th>
                <th className="p-3 text-start">الوظيفة</th>
                <th className="p-3 text-start">الراتب الشهري</th>
                <th className="p-3 text-start">الحالة</th>
              </tr>
            </thead>
            <tbody>
              {empList.map((e) => (
                <tr key={e.id} className="border-b border-line/60 last:border-0 hover:bg-secondary/10 transition-colors">
                  <td className="num p-3 text-muted" dir="ltr">{e.emp_code ?? "—"}</td>
                  <td className="p-3 font-bold">{e.name}</td>
                  <td className="p-3">{e.position ?? "—"}</td>
                  <td className="num p-3 font-bold">{moneyEGP(e.monthly_salary)}</td>
                  <td className="p-3"><Badge tone={e.is_active ? "success" : "muted"}>{e.is_active ? "نشط" : "موقوف"}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title="موظف جديد">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!create.isPending && form.name) create.mutate();
          }}
          className="flex flex-col gap-3"
        >
          <div>
            <label className="mb-1 block text-sm font-medium">الاسم *</label>
            <Input autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">الكود</label>
              <Input dir="ltr" value={form.emp_code} onChange={(e) => setForm({ ...form, emp_code: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">الوظيفة</label>
              <Input value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">الراتب الشهري</label>
            <Input className="num" inputMode="decimal" value={form.monthly_salary} onChange={(e) => setForm({ ...form, monthly_salary: e.target.value })} />
          </div>
          {create.isError && <ErrorBox message={(create.error as Error).message} />}
          <Button type="submit" className="w-full h-10 font-bold" disabled={create.isPending || !form.name}>
            {create.isPending ? <Spinner /> : "حفظ الموظف"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}

function AttendanceTab() {
  const qc = useQueryClient();
  const now = new Date();
  const [month, setMonth] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ employee_id: "", work_date: "", check_in: "", check_out: "", status: "present" });

  const employees = useQuery({ queryKey: ["hr-employees"], queryFn: () => api.get<Employee[]>("/hr/employees") });
  const att = useQuery({
    queryKey: ["hr-attendance", month],
    queryFn: () => api.get<Attendance[]>("/hr/attendance", { month }),
  });
  const add = useMutation({
    mutationFn: () =>
      api.post("/hr/attendance", {
        employee_id: form.employee_id,
        work_date: form.work_date,
        check_in: form.check_in || undefined,
        check_out: form.check_out || undefined,
        status: form.status,
      }),
    onSuccess: () => { setAdding(false); qc.invalidateQueries({ queryKey: ["hr-attendance"] }); },
  });

  const empList: Employee[] = Array.isArray(employees.data) ? employees.data : ((employees.data as any)?.items ?? []);
  const attList: Attendance[] = Array.isArray(att.data) ? att.data : ((att.data as any)?.items ?? []);
  const nameOf = (id: string) => empList.find((e) => e.id === id)?.name ?? "—";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <input type="month" className="num rounded-lg border border-line bg-surface px-3 py-2 text-sm" value={month} onChange={(e) => setMonth(e.target.value)} aria-label="الشهر" />
        <Button onClick={() => setAdding(true)}><Plus size={16} /> تسجيل حضور</Button>
      </div>
      {att.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
          <Skeleton className="h-10 w-full" />
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : att.isError ? (
        <ErrorBox message={(att.error as Error).message} onRetry={() => att.refetch()} />
      ) : !attList.length ? (
        <Empty text="لا توجد سجلات حضور هذا الشهر" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted bg-secondary/20">
                <th className="p-3 text-start">الموظف</th>
                <th className="p-3 text-start">اليوم</th>
                <th className="p-3 text-start">الحضور</th>
                <th className="p-3 text-start">الانصراف</th>
                <th className="p-3 text-start">الحالة</th>
              </tr>
            </thead>
            <tbody>
              {attList.slice(0, 100).map((a) => (
                <tr key={a.id} className="border-b border-line/60 last:border-0 hover:bg-secondary/10 transition-colors">
                  <td className="p-3 font-bold">{nameOf(a.employee_id)}</td>
                  <td className="p-3 text-muted">{fmtDate(a.work_date)}</td>
                  <td className="num p-3" dir="ltr">{a.check_in?.slice(11, 16) ?? "—"}</td>
                  <td className="num p-3" dir="ltr">{a.check_out?.slice(11, 16) ?? "—"}</td>
                  <td className="p-3"><Badge tone={a.status === "present" ? "success" : "warning"}>{a.status === "present" ? "حاضر" : a.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal open={adding} onClose={() => setAdding(false)} title="تسجيل حضور">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!add.isPending && form.employee_id && form.work_date) add.mutate();
          }}
          className="flex flex-col gap-3"
        >
          <Select autoFocus value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}>
            <option value="">— اختر الموظف —</option>
            {employees.data?.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </Select>
          <div className="grid grid-cols-3 gap-3">
            <Input type="date" className="num" value={form.work_date} onChange={(e) => setForm({ ...form, work_date: e.target.value })} aria-label="اليوم" />
            <Input type="time" className="num" value={form.check_in} onChange={(e) => setForm({ ...form, check_in: e.target.value })} aria-label="الحضور" />
            <Input type="time" className="num" value={form.check_out} onChange={(e) => setForm({ ...form, check_out: e.target.value })} aria-label="الانصراف" />
          </div>
          <Select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
            <option value="present">حاضر</option>
            <option value="leave">إجازة</option>
            <option value="absent">غائب</option>
          </Select>
          {add.isError && <ErrorBox message={(add.error as Error).message} />}
          <Button type="submit" className="w-full h-10 font-bold" disabled={add.isPending || !form.employee_id || !form.work_date}>
            {add.isPending ? <Spinner /> : "حفظ الحضور"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}

function AdvancesTab() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const emptyForm = { employee_id: "", amount: "", note: "", record_type: "سلفة", source: "" };
  const [form, setForm] = useState(emptyForm);
  const isAdvance = form.record_type === "سلفة";

  const employees = useQuery({ queryKey: ["hr-employees"], queryFn: () => api.get<Employee[]>("/hr/employees") });
  const list = useQuery({ queryKey: ["hr-advances"], queryFn: () => api.get<Advance[]>("/hr/advances") });
  const create = useMutation({
    mutationFn: () =>
      api.post("/hr/advances", {
        employee_id: form.employee_id,
        amount: D(form.amount).toNumber(),
        note: form.note || null,
        record_type: form.record_type,
        ...(isAdvance ? sourceFields(form.source) : {}),
      }),
    onSuccess: () => {
      setCreating(false);
      setForm(emptyForm);
      qc.invalidateQueries({ queryKey: ["hr-advances"] });
      qc.invalidateQueries({ queryKey: ["safes"] });
      qc.invalidateQueries({ queryKey: ["wallets"] });
    },
  });

  const empList: Employee[] = Array.isArray(employees.data) ? employees.data : ((employees.data as any)?.items ?? []);
  const advList: Advance[] = Array.isArray(list.data) ? list.data : ((list.data as any)?.items ?? []);
  const nameOf = (id: string) => empList.find((e) => e.id === id)?.name ?? "—";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-end">
        <Button onClick={() => setCreating(true)}><Plus size={16} /> سلفة أو خصم أو مكافأة</Button>
      </div>
      {list.isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-label="جارٍ التحميل">
          <Skeleton className="h-10 w-full" />
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !advList.length ? (
        <Empty text="لا توجد سلف" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted bg-secondary/20">
                <th className="p-3 text-start">الموظف</th>
                <th className="p-3 text-start">النوع</th>
                <th className="p-3 text-start">المبلغ</th>
                <th className="p-3 text-start">التاريخ</th>
                <th className="p-3 text-start">ملاحظة</th>
              </tr>
            </thead>
            <tbody>
              {advList.slice(0, 60).map((a) => (
                <tr key={a.id} className="border-b border-line/60 last:border-0 hover:bg-secondary/10 transition-colors">
                  <td className="p-3 font-bold">{nameOf(a.employee_id)}</td>
                  <td className="p-3">
                    <Badge tone={a.record_type === "مكافأة" ? "success" : a.record_type === "خصم" ? "danger" : "warning"}>
                      {a.record_type ?? "سلفة"}
                    </Badge>
                  </td>
                  <td className="num p-3 font-bold text-warning-ink">{money(a.amount)}</td>
                  <td className="p-3 text-xs text-muted">{fmtDate(a.date)}</td>
                  <td className="p-3 text-muted">{a.note ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title="سلفة أو خصم أو مكافأة">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!create.isPending && form.employee_id && form.amount && (!isAdvance || form.source)) create.mutate();
          }}
          className="flex flex-col gap-3"
        >
          <Select autoFocus value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}>
            <option value="">— اختر الموظف —</option>
            {empList.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </Select>
          <div>
            <label htmlFor="adv-type" className="mb-1 block text-sm font-medium">النوع</label>
            <Select id="adv-type" value={form.record_type} onChange={(e) => setForm({ ...form, record_type: e.target.value })}>
              <option value="سلفة">سلفة (تُصرف نقدًا الآن وتُخصم من الراتب)</option>
              <option value="خصم">خصم من الراتب</option>
              <option value="مكافأة">مكافأة تُضاف إلى الراتب</option>
            </Select>
          </div>
          {isAdvance && (
            <div>
              <label htmlFor="adv-source" className="mb-1 block text-sm font-medium">تُصرف من *</label>
              <PaySourceSelect id="adv-source" value={form.source} onChange={(v) => setForm({ ...form, source: v })} />
            </div>
          )}
          <div>
            <label className="mb-1 block text-sm font-medium">المبلغ</label>
            <Input className="num text-lg font-bold" inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">ملاحظة</label>
            <Input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </div>
          {create.isError && <ErrorBox message={(create.error as Error).message} />}
          <Button type="submit" className="w-full h-10 font-bold" disabled={create.isPending || !form.employee_id || !form.amount || (isAdvance && !form.source)}>
            {create.isPending ? <Spinner /> : "حفظ"}
          </Button>
        </form>
      </Modal>
    </div>
  );
}


