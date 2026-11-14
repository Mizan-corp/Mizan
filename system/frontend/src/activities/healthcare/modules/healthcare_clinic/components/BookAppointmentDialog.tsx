import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/kit/input";
import { errorMessage, useDialogMutation } from "../useClinicActions";
import { InlineRetry } from "./QueryState";
import { CLINIC_KEYS } from "../useClinicData";
import type { Clinician, PatientRef } from "../types";
import { ClinicModal, ModalActions } from "./ClinicModal";
import { labelClass, selectClass } from "./formStyles";
import PatientPicker from "./PatientPicker";
import { localToday } from "../dates";

// Books a consultation (POST /clinic/appointments); the chosen doctor joins the care team (#113).
export default function BookAppointmentDialog({ patient, onClose }: { patient?: PatientRef; onClose: () => void }) {
  const { run, busy } = useDialogMutation();
  const [picked, setPicked] = useState<PatientRef | null>(patient ?? null);
  const [form, setForm] = useState({
    doctor_user_id: "",
    department: "الباطنة العامة",
    appointment_date: localToday(),
    time_slot: "11:30 AM",
    consultation_fee: "350",
    chief_complaint: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const cliniciansQuery = useQuery<Clinician[]>({
    queryKey: CLINIC_KEYS.clinicians,
    queryFn: () => api.get("/clinic/clinicians"),
  });
  const clinicians = cliniciansQuery.data ?? [];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!picked) return;
    const ok = await run(
      () => api.post("/clinic/appointments", {
        patient_id: picked.id,
        patient_name: picked.full_name,
        doctor_user_id: form.doctor_user_id,
        department: form.department,
        appointment_date: form.appointment_date,
        time_slot: form.time_slot,
        consultation_fee: parseFloat(form.consultation_fee) || 250,
        chief_complaint: form.chief_complaint,
      }),
      "تم حجز الموعد وإدراجه في قائمة الانتظار",
      "تعذر حفظ الموعد على الخادم",
      ["appointments", "summary", "patients"],
    );
    if (ok) onClose();
  };

  return (
    <ClinicModal title="حجز موعد كشف واستشارة طبية" icon={<Calendar className="size-5 text-primary" />} onClose={onClose} size="lg">
      <form onSubmit={submit} className="space-y-3.5 text-xs">
        <PatientPicker id="booking-patient" value={picked} onChange={setPicked} />

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>العيادة / التخصص *</label>
            <Input required value={form.department} onChange={(e) => set({ department: e.target.value })} className="h-9 text-xs" />
          </div>
          <div>
            <label htmlFor="booking-doctor" className={labelClass}>الطبيب المعالج *</label>
            <select
              id="booking-doctor"
              required
              value={form.doctor_user_id}
              onChange={(e) => set({ doctor_user_id: e.target.value })}
              className={selectClass}
            >
              <option value="">{clinicians.length ? "اختر الطبيب" : "لا يوجد أطباء مسجلون كمستخدمين"}</option>
              {clinicians.map((d) => (
                <option key={d.id} value={d.id}>{d.full_name}{d.role ? ` — ${d.role}` : ""}</option>
              ))}
            </select>
            {cliniciansQuery.isError ? (
              <InlineRetry message={errorMessage(cliniciansQuery.error, "تعذر تحميل قائمة الأطباء")}
                onRetry={() => void cliniciansQuery.refetch()} />
            ) : (
              <p className="text-[10px] text-muted-foreground mt-1">يُضاف الطبيب إلى فريق رعاية المريض</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>تاريخ الكشف</label>
            <Input type="date" value={form.appointment_date} onChange={(e) => set({ appointment_date: e.target.value })} className="h-9 text-xs font-mono" />
          </div>
          <div>
            <label className={labelClass}>التوقيت</label>
            <Input value={form.time_slot} onChange={(e) => set({ time_slot: e.target.value })} className="h-9 text-xs font-mono" />
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
