import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/kit/input";
import { errorMessage, useDialogMutation } from "../useClinicActions";
import { InlineRetry } from "./QueryState";
import { CLINIC_KEYS } from "../useClinicData";
import type { Clinician, Department, PatientRef, SlotList } from "../types";
import { ClinicModal, ModalActions } from "./ClinicModal";
import { labelClass, selectClass } from "./formStyles";
import PatientPicker from "./PatientPicker";
import { localToday } from "../dates";

// Books a consultation (POST /clinic/appointments); the chosen doctor joins the care team (#113).
// Department from the master, doctors from its roster, times from the doctor's roster (#36).
export default function BookAppointmentDialog({ patient, onClose }: { patient?: PatientRef; onClose: () => void }) {
  const { run, busy } = useDialogMutation();
  const [picked, setPicked] = useState<PatientRef | null>(patient ?? null);
  const [form, setForm] = useState({
    doctor_user_id: "",
    department_id: "",
    appointment_date: localToday(),
    time_slot: "",
    consultation_fee: "350",
    chief_complaint: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const departmentsQuery = useQuery<Department[]>({
    queryKey: CLINIC_KEYS.departments,
    queryFn: () => api.get("/clinic/departments"),
  });
  const departments = departmentsQuery.data ?? [];
  const rosterQuery = useQuery<Clinician[]>({
    queryKey: [...CLINIC_KEYS.clinicians, form.department_id],
    queryFn: () => api.get("/clinic/clinicians", { department_id: form.department_id }),
    enabled: !!form.department_id,
  });
  const cliniciansQuery = useQuery<Clinician[]>({
    queryKey: CLINIC_KEYS.clinicians,
    queryFn: () => api.get("/clinic/clinicians"),
  });
  const roster = rosterQuery.data ?? [];
  // A department with no roster yet: every clinician, booked at a free time.
  const noRoster = !!form.department_id && rosterQuery.isSuccess && roster.length === 0;
  const clinicians = form.department_id && !noRoster ? roster : cliniciansQuery.data ?? [];
  const doctorsError = rosterQuery.isError ? rosterQuery : cliniciansQuery.isError ? cliniciansQuery : null;

  const slotsQuery = useQuery<SlotList>({
    queryKey: [...CLINIC_KEYS.schedules, "slots", form.doctor_user_id, form.appointment_date, form.department_id],
    queryFn: () => api.get("/clinic/schedule/slots", {
      doctor_user_id: form.doctor_user_id, date: form.appointment_date, department_id: form.department_id || undefined,
    }),
    enabled: !!form.doctor_user_id && !!form.appointment_date,
  });
  const slotList = slotsQuery.data;
  const rostered = !!slotList?.has_roster;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!picked) return;
    const ok = await run(
      () => api.post("/clinic/appointments", {
        patient_id: picked.id,
        patient_name: picked.full_name,
        doctor_user_id: form.doctor_user_id,
        department_id: form.department_id || null,
        department: departments.find((d) => d.id === form.department_id)?.name ?? "",
        appointment_date: form.appointment_date,
        time_slot: form.time_slot,
        consultation_fee: parseFloat(form.consultation_fee) || 250,
        chief_complaint: form.chief_complaint,
      }),
      "تم حجز الموعد وإدراجه في قائمة الانتظار",
      "تعذر حفظ الموعد على الخادم",
      ["appointments", "summary", "patients", "schedules"],
    );
    if (ok) onClose();
  };

  return (
    <ClinicModal title="حجز موعد كشف واستشارة طبية" icon={<Calendar className="size-5 text-primary" />} onClose={onClose} size="lg">
      <form onSubmit={submit} className="space-y-3.5 text-xs">
        <PatientPicker id="booking-patient" value={picked} onChange={setPicked} />

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="booking-department" className={labelClass}>القسم / التخصص *</label>
            <select
              id="booking-department"
              required
              value={form.department_id}
              onChange={(e) => set({ department_id: e.target.value, doctor_user_id: "", time_slot: "" })}
              className={selectClass}
            >
              <option value="">{departmentsQuery.isLoading ? "جارٍ التحميل..." : "اختر القسم"}</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
            {departmentsQuery.isError && (
              <InlineRetry message={errorMessage(departmentsQuery.error, "تعذر تحميل الأقسام")}
                onRetry={() => void departmentsQuery.refetch()} />
            )}
          </div>
          <div>
            <label htmlFor="booking-doctor" className={labelClass}>الطبيب المعالج *</label>
            <select
              id="booking-doctor"
              required
              value={form.doctor_user_id}
              onChange={(e) => set({ doctor_user_id: e.target.value, time_slot: "" })}
              className={selectClass}
            >
              <option value="">{clinicians.length ? "اختر الطبيب" : "لا يوجد أطباء مسجلون كمستخدمين"}</option>
              {clinicians.map((d) => (
                <option key={d.id} value={d.id}>{d.full_name}{d.role ? ` — ${d.role}` : ""}</option>
              ))}
            </select>
            {doctorsError ? (
              <InlineRetry message={errorMessage(doctorsError.error, "تعذر تحميل قائمة الأطباء")}
                onRetry={() => void doctorsError.refetch()} />
            ) : (
              <p className="text-[10px] text-muted-foreground mt-1">
                {noRoster ? "لا يوجد جدول أطباء لهذا القسم بعد؛ تُعرض جميع الأطباء" : "يُضاف الطبيب إلى فريق رعاية المريض"}
              </p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="booking-date" className={labelClass}>تاريخ الكشف</label>
            <Input id="booking-date" type="date" required value={form.appointment_date}
              onChange={(e) => set({ appointment_date: e.target.value, time_slot: "" })} className="h-9 text-xs font-mono" />
          </div>
          <div>
            <label htmlFor="booking-time" className={labelClass}>التوقيت *</label>
            {rostered ? (
              <select id="booking-time" required value={form.time_slot} onChange={(e) => set({ time_slot: e.target.value })}
                className={`${selectClass} font-mono`} disabled={!slotList?.slots.length}>
                <option value="">{slotList?.slots.length ? "اختر وقتاً من جدول الطبيب" : "الطبيب لا يعمل في هذا اليوم"}</option>
                {slotList?.slots.map((s) => (
                  <option key={`${s.time}-${s.room_id}`} value={s.time} disabled={!s.available}>
                    {s.time}{s.room_name ? ` · ${s.room_name}` : ""}{s.available ? "" : " — محجوز"}
                  </option>
                ))}
              </select>
            ) : (
              <Input id="booking-time" type="time" required value={form.time_slot}
                onChange={(e) => set({ time_slot: e.target.value })} className="h-9 text-xs font-mono" />
            )}
            {slotsQuery.isError && (
              <InlineRetry message={errorMessage(slotsQuery.error, "تعذر تحميل أوقات الطبيب")}
                onRetry={() => void slotsQuery.refetch()} />
            )}
          </div>
        </div>

        <div>
          <label className={labelClass}>أتعاب الكشف (ج.م)</label>
          <Input type="number" value={form.consultation_fee} onChange={(e) => set({ consultation_fee: e.target.value })} className="h-9 text-xs font-mono" />
        </div>

        <div>
          <label className={labelClass}>الشكوى الأولية والأعراض</label>
          <Input placeholder="مثال: متابعة السكر وضغط الدم" value={form.chief_complaint}
            onChange={(e) => set({ chief_complaint: e.target.value })} className="h-9 text-xs" />
        </div>

        <ModalActions busy={busy} onCancel={onClose} submitLabel="تأكيد الحجز وقيد الانتظار" />
      </form>
    </ClinicModal>
  );
}
