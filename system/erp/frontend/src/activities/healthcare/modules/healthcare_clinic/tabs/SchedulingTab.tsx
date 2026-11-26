import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Building2, CalendarClock, DoorOpen, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { Input } from "@/components/kit/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/kit/table";
import QueryState from "../components/QueryState";
import { labelClass, selectClass } from "../components/formStyles";
import { useClinicMutation } from "../useClinicActions";
import { CLINIC_KEYS } from "../useClinicData";
import type { Clinician, Department, DoctorSchedule, Room } from "../types";

/** Weekdays in the order an Egyptian week is read (Saturday first); values are Python's weekday(). */
const WEEKDAYS: { value: number; label: string }[] = [
  { value: 5, label: "السبت" },
  { value: 6, label: "الأحد" },
  { value: 0, label: "الاثنين" },
  { value: 1, label: "الثلاثاء" },
  { value: 2, label: "الأربعاء" },
  { value: 3, label: "الخميس" },
  { value: 4, label: "الجمعة" },
];

function Section({ icon, title, hint, children }: { icon: React.ReactNode; title: string; hint: string; children: React.ReactNode }) {
  return (
    <Card className="border-border/70 overflow-hidden shadow-xs bg-card/80">
      <div className="p-4 border-b border-border/60 bg-muted/10">
        <h3 className="font-bold text-sm text-foreground flex items-center gap-2">{icon}{title}</h3>
        <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>
      </div>
      {children}
    </Card>
  );
}

function ActiveBadge({ active }: { active: boolean }) {
  return active
    ? <Badge variant="outline" className="text-[10px] border-primary/30 text-primary bg-primary/5">نشط</Badge>
    : <Badge variant="outline" className="text-[10px] text-muted-foreground">موقوف</Badge>;
}

function Departments() {
  const run = useClinicMutation();
  const query = useQuery<Department[]>({
    queryKey: [...CLINIC_KEYS.departments, "all"],
    queryFn: () => api.get("/clinic/departments", { include_inactive: "true" }),
  });
  const [form, setForm] = useState({ code: "", name: "", specialty_code: "" });
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(() => api.post("/clinic/departments", { ...form, active: true }),
      "تمت إضافة القسم", "تعذر إضافة القسم", ["departments"]);
    if (ok) setForm({ code: "", name: "", specialty_code: "" });
  };
  const toggle = (d: Department) =>
    run(() => api.put(`/clinic/departments/${d.id}`, { ...d, active: !d.active }),
      d.active ? "تم إيقاف القسم" : "تم تفعيل القسم", "تعذر تحديث القسم", ["departments"]);
  return (
    <Section icon={<Building2 className="size-4 text-primary" />} title="الأقسام والتخصصات"
      hint="الأقسام التي يُحجز فيها الكشف؛ القسم الموقوف لا يظهر في الحجز.">
      <form onSubmit={add} className="p-4 grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs border-b border-border/40">
        <div>
          <label htmlFor="dep-code" className={labelClass}>الرمز *</label>
          <Input id="dep-code" required maxLength={16} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="h-9 text-xs font-mono" placeholder="CARD" />
        </div>
        <div>
          <label htmlFor="dep-name" className={labelClass}>اسم القسم *</label>
          <Input id="dep-name" required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-9 text-xs" placeholder="أمراض القلب" />
        </div>
        <div>
          <label htmlFor="dep-spec" className={labelClass}>رمز التخصص</label>
          <Input id="dep-spec" value={form.specialty_code} onChange={(e) => setForm({ ...form, specialty_code: e.target.value })} className="h-9 text-xs font-mono" placeholder="cardiology" />
        </div>
        <div className="flex items-end">
          <Button type="submit" size="sm" className="h-9 text-xs gap-1.5 w-full"><Plus className="size-3.5" />إضافة قسم</Button>
        </div>
      </form>
      <QueryState query={query} what="الأقسام">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30 hover:bg-muted/30">
              <TableHead className="text-right">الرمز</TableHead>
              <TableHead className="text-right">القسم</TableHead>
              <TableHead className="text-right">التخصص</TableHead>
              <TableHead className="text-center">الحالة</TableHead>
              <TableHead className="text-center">إجراء</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(query.data ?? []).map((d) => (
              <TableRow key={d.id}>
                <TableCell className="num text-xs font-bold">{d.code}</TableCell>
                <TableCell className="text-xs">{d.name}</TableCell>
                <TableCell className="num text-xs text-muted-foreground">{d.specialty_code || "—"}</TableCell>
                <TableCell className="text-center"><ActiveBadge active={d.active} /></TableCell>
                <TableCell className="text-center">
                  <Button size="sm" variant="outline" className="h-7 text-[10px]" onClick={() => void toggle(d)}>
                    {d.active ? "إيقاف" : "تفعيل"}
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </QueryState>
    </Section>
  );
}

function Rooms({ departments }: { departments: Department[] }) {
  const run = useClinicMutation();
  const query = useQuery<Room[]>({
    queryKey: [...CLINIC_KEYS.rooms, "all"],
    queryFn: () => api.get("/clinic/rooms", { include_inactive: "true" }),
  });
  const [form, setForm] = useState({ name: "", department_id: "" });
  const depName = (id: string | null) => (id ? departments.find((d) => d.id === id)?.name ?? "—" : "مشتركة بين الأقسام");
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(() => api.post("/clinic/rooms", { name: form.name, department_id: form.department_id || null }),
      "تمت إضافة الغرفة", "تعذر إضافة الغرفة", ["rooms"]);
    if (ok) setForm({ name: "", department_id: "" });
  };
  const toggle = (r: Room) =>
    run(() => api.put(`/clinic/rooms/${r.id}`, { ...r, active: !r.active }),
      r.active ? "تم إيقاف الغرفة" : "تم تفعيل الغرفة", "تعذر تحديث الغرفة", ["rooms"]);
  return (
    <Section icon={<DoorOpen className="size-4 text-primary" />} title="غرف الكشف"
      hint="لا تُحجز غرفة لموعدين في نفس الوقت.">
      <form onSubmit={add} className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs border-b border-border/40">
        <div>
          <label htmlFor="room-name" className={labelClass}>اسم الغرفة *</label>
          <Input id="room-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-9 text-xs" placeholder="غرفة 3" />
        </div>
        <div>
          <label htmlFor="room-dep" className={labelClass}>القسم</label>
          <select id="room-dep" value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })} className={selectClass}>
            <option value="">مشتركة بين الأقسام</option>
            {departments.filter((d) => d.active).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div className="flex items-end">
          <Button type="submit" size="sm" className="h-9 text-xs gap-1.5 w-full"><Plus className="size-3.5" />إضافة غرفة</Button>
        </div>
      </form>
      <QueryState query={query} what="الغرف">
        {(query.data ?? []).length === 0 ? (
          <p className="p-6 text-center text-xs text-muted-foreground">لا توجد غرف كشف بعد.</p>
        ) : (
          <ul className="divide-y divide-border/40">
            {(query.data ?? []).map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-2 px-4 py-2 text-xs">
                <span className="font-semibold">{r.name} <span className="text-muted-foreground font-normal">— {depName(r.department_id)}</span></span>
                <span className="flex items-center gap-2">
                  <ActiveBadge active={r.active} />
                  <Button size="sm" variant="outline" className="h-7 text-[10px]" onClick={() => void toggle(r)}>{r.active ? "إيقاف" : "تفعيل"}</Button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </Section>
  );
}

function Rosters({ departments }: { departments: Department[] }) {
  const run = useClinicMutation();
  const query = useQuery<DoctorSchedule[]>({ queryKey: CLINIC_KEYS.schedules, queryFn: () => api.get("/clinic/schedules") });
  const rooms = useQuery<Room[]>({ queryKey: CLINIC_KEYS.rooms, queryFn: () => api.get("/clinic/rooms") });
  const clinicians = useQuery<Clinician[]>({ queryKey: CLINIC_KEYS.clinicians, queryFn: () => api.get("/clinic/clinicians") });
  const doctors = (clinicians.data ?? []).filter((c) => c.is_doctor);
  const empty = { doctor_user_id: "", department_id: "", room_id: "", weekday: "5", start_time: "09:00", end_time: "13:00", slot_minutes: "15" };
  const [form, setForm] = useState(empty);
  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(() => api.post("/clinic/schedules", {
      ...form, room_id: form.room_id || null, weekday: Number(form.weekday), slot_minutes: Number(form.slot_minutes),
    }), "تمت إضافة الجدول", "تعذر إضافة الجدول", ["schedules"]);
    if (ok) setForm({ ...empty, doctor_user_id: form.doctor_user_id, department_id: form.department_id });
  };
  const remove = (s: DoctorSchedule) => {
    if (!window.confirm(`حذف جدول ${s.doctor_name} يوم ${s.weekday_name}؟ المواعيد المحجوزة تبقى كما هي.`)) return;
    void run(() => api.del(`/clinic/schedules/${s.id}`), "تم حذف الجدول", "تعذر حذف الجدول", ["schedules"]);
  };
  const order = (w: number) => WEEKDAYS.findIndex((d) => d.value === w);
  const rows = [...(query.data ?? [])].sort((a, b) => order(a.weekday) - order(b.weekday) || a.start_time.localeCompare(b.start_time));
  return (
    <Section icon={<CalendarClock className="size-4 text-primary" />} title="جداول الأطباء (الروستر)"
      hint="يُعرض للحجز الطبيب المدرج في جدول القسم، وتُقترح أوقات الكشف من جدوله في ذلك اليوم.">
      <form onSubmit={add} className="p-4 grid grid-cols-2 lg:grid-cols-8 gap-2 text-xs border-b border-border/40">
        <div className="col-span-2">
          <label htmlFor="ros-doc" className={labelClass}>الطبيب *</label>
          <select id="ros-doc" required value={form.doctor_user_id} onChange={(e) => setForm({ ...form, doctor_user_id: e.target.value })} className={selectClass}>
            <option value="">{doctors.length ? "اختر الطبيب" : "لا يوجد أطباء مسجلون"}</option>
            {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="ros-dep" className={labelClass}>القسم *</label>
          <select id="ros-dep" required value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })} className={selectClass}>
            <option value="">اختر</option>
            {departments.filter((d) => d.active).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="ros-room" className={labelClass}>الغرفة</label>
          <select id="ros-room" value={form.room_id} onChange={(e) => setForm({ ...form, room_id: e.target.value })} className={selectClass}>
            <option value="">بدون</option>
            {(rooms.data ?? []).filter((r) => !r.department_id || !form.department_id || r.department_id === form.department_id)
              .map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="ros-day" className={labelClass}>اليوم *</label>
          <select id="ros-day" value={form.weekday} onChange={(e) => setForm({ ...form, weekday: e.target.value })} className={selectClass}>
            {WEEKDAYS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="ros-from" className={labelClass}>من</label>
          <Input id="ros-from" type="time" required value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} className="h-9 text-xs font-mono" />
        </div>
        <div>
          <label htmlFor="ros-to" className={labelClass}>إلى</label>
          <Input id="ros-to" type="time" required value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} className="h-9 text-xs font-mono" />
        </div>
        <div>
          <label htmlFor="ros-slot" className={labelClass}>مدة الكشف (د)</label>
          <Input id="ros-slot" type="number" min={5} max={240} required value={form.slot_minutes} onChange={(e) => setForm({ ...form, slot_minutes: e.target.value })} className="h-9 text-xs font-mono" />
        </div>
        <div className="col-span-2 lg:col-span-8 flex justify-end">
          <Button type="submit" size="sm" className="h-8 text-xs gap-1.5"><Plus className="size-3.5" />إضافة إلى الجدول</Button>
        </div>
      </form>
      <QueryState query={query} what="جداول الأطباء">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30 hover:bg-muted/30">
              <TableHead className="text-right">اليوم</TableHead>
              <TableHead className="text-right">الطبيب</TableHead>
              <TableHead className="text-right">القسم والغرفة</TableHead>
              <TableHead className="text-center">الوقت</TableHead>
              <TableHead className="text-center">مدة الكشف</TableHead>
              <TableHead className="text-center">إجراء</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="text-xs font-semibold">{s.weekday_name}</TableCell>
                <TableCell className="text-xs">{s.doctor_name}</TableCell>
                <TableCell className="text-xs">{s.department_name ?? "—"}{s.room_name ? ` · ${s.room_name}` : ""}</TableCell>
                <TableCell className="num text-xs text-center" dir="ltr">{s.start_time}–{s.end_time}</TableCell>
                <TableCell className="num text-xs text-center">{s.slot_minutes} د</TableCell>
                <TableCell className="text-center">
                  <Button size="sm" variant="outline" className="h-7 w-7 p-0" aria-label={`حذف جدول ${s.doctor_name} يوم ${s.weekday_name}`} onClick={() => remove(s)}>
                    <Trash2 className="size-3.5" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-6 text-center text-xs text-muted-foreground">
                  لا توجد جداول بعد: يُحجز للأطباء بوقت حر حتى تُضاف جداولهم.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </QueryState>
    </Section>
  );
}

// Departments, rooms and doctors' rosters (#36), for the front desk and management (clinic:manage;
// the page offers the tab only to them).
export default function SchedulingTab() {
  const departments = useQuery<Department[]>({
    queryKey: [...CLINIC_KEYS.departments, "all"],
    queryFn: () => api.get("/clinic/departments", { include_inactive: "true" }),
  });
  const list = departments.data ?? [];
  return (
    <div className="space-y-4">
      <Rosters departments={list} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <Departments />
        <Rooms departments={list} />
      </div>
    </div>
  );
}
