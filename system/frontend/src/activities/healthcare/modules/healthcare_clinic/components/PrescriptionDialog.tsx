import { useState } from "react";
import { Pill } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/kit/input";
import { useClinicMutation } from "../useClinicActions";
import type { PatientRef } from "../types";
import { ClinicModal, ModalActions } from "./ClinicModal";
import PatientPicker from "./PatientPicker";
import { labelClass } from "./formStyles";

// Issues an e-prescription to the pharmacy queue (POST /clinic/prescriptions, clinic:doctor).
export default function PrescriptionDialog({ patient, onClose }: { patient?: PatientRef; onClose: () => void }) {
  const run = useClinicMutation();
  const [form, setForm] = useState({
    doctor_name: "د. هشام الشناوي",
    issue_date: "2026-11-05",
    medication_name: "",
    dosage: "500mg",
    frequency: "قرص كل 12 ساعة",
    duration_days: "14",
    instructions: "يؤخذ بعد الأكل مع كوب ماء كامل",
  });
  const [picked, setPicked] = useState<PatientRef | null>(patient ?? null);
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!picked) return;
    await run(
      () => api.post("/clinic/prescriptions", {
        patient_id: picked.id,
        patient_name: picked.full_name,
        doctor_name: form.doctor_name,
        issue_date: form.issue_date,
        medication_name: form.medication_name,
        dosage: form.dosage,
        frequency: form.frequency,
        duration_days: parseInt(form.duration_days) || 14,
        instructions: form.instructions,
      }),
      "تم إصدار الروشتة الطبية وتوجيهها للصيدلية",
      "تعذر إصدار الروشتة على الخادم",
      ["prescriptions"],
    );
    onClose();
  };

  return (
    <ClinicModal title="إصدار روشتة طبية رقمية (e-Prescription)" icon={<Pill className="size-5 text-primary" />} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3.5 text-xs">
        <PatientPicker id="rx-patient" value={picked} onChange={setPicked} />

        <div>
          <label className={labelClass}>اسم الدواء والمادة الفعالة *</label>
          <Input required placeholder="مثال: أوجمنتين 1 جم (Augmentin 1g)" value={form.medication_name}
            onChange={(e) => set({ medication_name: e.target.value })} className="h-9 text-xs" />
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className={labelClass}>الجرعة</label>
            <Input value={form.dosage} onChange={(e) => set({ dosage: e.target.value })} className="h-9 text-xs" />
          </div>
          <div>
            <label className={labelClass}>التكرار</label>
            <Input value={form.frequency} onChange={(e) => set({ frequency: e.target.value })} className="h-9 text-xs" />
          </div>
          <div>
            <label className={labelClass}>المدة (أيام)</label>
            <Input type="number" value={form.duration_days} onChange={(e) => set({ duration_days: e.target.value })} className="h-9 text-xs font-mono" />
          </div>
        </div>

        <div>
          <label className={labelClass}>تعليمات الصيدلي والمريض</label>
          <Input value={form.instructions} onChange={(e) => set({ instructions: e.target.value })} className="h-9 text-xs" />
        </div>

        <ModalActions onCancel={onClose} submitLabel="إصدار وإرسال للصيدلية" />
      </form>
    </ClinicModal>
  );
}
