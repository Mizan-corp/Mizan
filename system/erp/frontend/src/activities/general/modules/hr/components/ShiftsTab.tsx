// Work shifts: create, edit, stop (a shift employees or days still name) or delete (an unused one).
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Clock, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { sound } from "@/lib/sound";
import { Badge, Button, ConfirmDialog, Empty, ErrorBox, Input, Modal, Spinner, useToast } from "@/components/ui";
import { shiftHours } from "../lib";
import { Rows, type Shift, useShifts } from "./common";

type Form = { id?: string; name: string; start_time: string; end_time: string; description: string };

export function ShiftsTab() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const list = useShifts();
  const [form, setForm] = useState<Form | null>(null);
  const [removing, setRemoving] = useState<Shift | null>(null);
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["hr-shifts"] });
    qc.invalidateQueries({ queryKey: ["hr-employees"] });
  };
  const save = useMutation({
    mutationFn: (f: Form) => {
      const body = { name: f.name.trim(), start_time: f.start_time, end_time: f.end_time, description: f.description.trim() };
      return f.id ? api.put(`/hr/shifts/${f.id}`, body) : api.post("/hr/shifts", body);
    },
    onSuccess: (_r, f) => {
      sound.success();
      toast("success", f.id ? "حُفظت الوردية" : "أُضيفت الوردية");
      setForm(null);
      refresh();
    },
    onError: () => sound.error(),
  });
  const remove = useMutation({
    mutationFn: (s: Shift) => api.del(`/hr/shifts/${s.id}`),
    onSuccess: () => {
      toast("success", "حُذفت الوردية أو أُوقفت إن كانت مستخدمة");
      setRemoving(null);
      refresh();
    },
    onError: (e) => {
      setRemoving(null);
      toast("error", (e as Error).message);
    },
  });
  const activate = useMutation({
    mutationFn: (s: Shift) => api.put(`/hr/shifts/${s.id}`, { is_active: true }),
    onSuccess: () => { toast("success", "أُعيد تفعيل الوردية"); refresh(); },
    onError: (e) => toast("error", (e as Error).message),
  });
  const valid = (f: Form) => f.name.trim() && /^\d{2}:\d{2}$/.test(f.start_time) && /^\d{2}:\d{2}$/.test(f.end_time);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">مواعيد الدوام التي يُحسب منها التأخير والانصراف المبكر والإضافي. تُحسب بالساعات الكاملة (الدقائق في المواعيد لا تُحتسب).</p>
        <Button onClick={() => setForm({ name: "", start_time: "09:00", end_time: "17:00", description: "" })}><Plus className="size-4" /> وردية</Button>
      </div>
      {list.isLoading ? <Rows n={3} /> : list.isError ? (
        <ErrorBox message={(list.error as Error).message} onRetry={() => list.refetch()} />
      ) : !list.data?.length ? (
        <Empty text="لا توجد ورديات" hint="بدون وردية يُحسب الموظف على الوردية الافتراضية من الإعدادات" icon={<Clock className="size-10" />} />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line bg-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th className="p-3 text-start">الوردية</th>
                <th className="p-3 text-start">من</th>
                <th className="p-3 text-start">إلى</th>
                <th className="p-3 text-end">الساعات</th>
                <th className="p-3 text-end">الموظفون</th>
                <th className="p-3 text-start">الحالة</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {list.data.map((s) => (
                <tr key={s.id} className={`border-b border-line/60 last:border-0 ${s.is_active ? "" : "opacity-60"}`}>
                  <td className="p-3 font-bold">{s.name}{s.description ? <div className="text-[11px] font-normal text-muted">{s.description}</div> : null}</td>
                  <td className="num p-3" dir="ltr">{s.start_time}</td>
                  <td className="num p-3" dir="ltr">{s.end_time}</td>
                  <td className="num p-3 text-end">{shiftHours(s.start_time, s.end_time)}</td>
                  <td className="num p-3 text-end">{s.employees}</td>
                  <td className="p-3">{s.is_active ? <Badge tone="success">نشطة</Badge> : <Badge tone="muted">موقوفة</Badge>}</td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تعديل ${s.name}`}
                              onClick={() => setForm({ id: s.id, name: s.name, start_time: s.start_time.slice(0, 5), end_time: s.end_time.slice(0, 5), description: s.description ?? "" })}>
                        <Pencil className="size-4" />
                      </Button>
                      {s.is_active ? (
                        <Button variant="ghost" size="icon" className="size-8 px-0! text-danger" aria-label={`حذف ${s.name}`} onClick={() => setRemoving(s)}>
                          <Trash2 className="size-4" />
                        </Button>
                      ) : (
                        <Button variant="ghost" size="icon" className="size-8 px-0!" aria-label={`تفعيل ${s.name}`} disabled={activate.isPending}
                                onClick={() => activate.mutate(s)}>
                          <Power className="size-4" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "تعديل الوردية" : "وردية جديدة"}>
        {form && (
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (!save.isPending && valid(form)) save.mutate(form); }}>
            <div>
              <label htmlFor="sh-name" className="mb-1 block text-xs font-semibold text-muted">الاسم *</label>
              <Input id="sh-name" autoFocus maxLength={128} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="sh-start" className="mb-1 block text-xs font-semibold text-muted">من *</label>
                <Input id="sh-start" type="time" className="num" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} />
              </div>
              <div>
                <label htmlFor="sh-end" className="mb-1 block text-xs font-semibold text-muted">إلى *</label>
                <Input id="sh-end" type="time" className="num" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} />
              </div>
            </div>
            {valid(form) && <p className="text-xs text-muted">مدة الوردية: <span className="num">{shiftHours(form.start_time, form.end_time)}</span> ساعة{form.end_time <= form.start_time ? " (تنتهي في اليوم التالي)" : ""}</p>}
            <div>
              <label htmlFor="sh-desc" className="mb-1 block text-xs font-semibold text-muted">وصف</label>
              <Input id="sh-desc" maxLength={1000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            {save.isError && <ErrorBox message={(save.error as Error).message} />}
            <Button type="submit" className="w-full h-10 font-bold" disabled={save.isPending || !valid(form)}>{save.isPending ? <Spinner /> : "حفظ"}</Button>
          </form>
        )}
      </Modal>
      <ConfirmDialog
        open={!!removing}
        onClose={() => setRemoving(null)}
        onConfirm={() => removing && !remove.isPending && remove.mutate(removing)}
        title={`حذف الوردية ${removing?.name ?? ""}`}
        message="إن كان موظفون أو أيام حضور يحملون هذه الوردية تُوقف ولا تُحذف، وتبقى لهم كما هي."
        confirmLabel="حذف أو إيقاف"
      />
    </div>
  );
}
