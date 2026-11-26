import { useState } from "react";
import { HeartPulse } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/kit/input";
import { useDialogMutation } from "../useClinicActions";
import type { PatientRef } from "../types";
import { ClinicModal, ModalActions } from "./ClinicModal";
import PatientPicker from "./PatientPicker";
import { labelClass } from "./formStyles";
import { localToday } from "../dates";

const VITALS = [
  { key: "bp_systolic", label: "ضغط الدم الانقباضي", placeholder: "120" },
  { key: "bp_diastolic", label: "الانبساطي", placeholder: "80" },
  { key: "heart_rate", label: "النبض HR", placeholder: "75" },
  { key: "spo2", label: "الأكسجين SpO2", placeholder: "99" },
  { key: "temperature", label: "الحرارة °C", placeholder: "37.0" },
  { key: "blood_glucose", label: "سكر الدم mg/dL", placeholder: "اختياري" },
] as const;

// Documents a clinical encounter (POST /clinic/encounters, clinic:doctor + access to the patient).
export default function EncounterDialog({ patient, onClose }: { patient?: PatientRef; onClose: () => void }) {
  const { run, busy } = useDialogMutation();
  const [form, setForm] = useState({
    doctor_name: "د. هشام الشناوي",
    department: "الباطنة العامة",
    encounter_date: localToday(),
    bp_systolic: "120",
    bp_diastolic: "80",
    heart_rate: "75",
    temperature: "37.0",
    spo2: "99",
    blood_glucose: "",
    chief_complaint: "",
    icd10_code: "E11.9",
    icd10_description: "داء السكري النوع الثاني",
    clinical_notes: "",
  });
  const [picked, setPicked] = useState<PatientRef | null>(patient ?? null);
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!picked) return;
    const ok = await run(
      () => api.post("/clinic/encounters", {
        patient_id: picked.id,
        patient_name: picked.full_name,
        doctor_name: form.doctor_name,
        department: form.department,
        encounter_date: form.encounter_date,
        bp_systolic: parseInt(form.bp_systolic) || 120,
        bp_diastolic: parseInt(form.bp_diastolic) || 80,
        heart_rate: parseInt(form.heart_rate) || 75,
        temperature: parseFloat(form.temperature) || 37.0,
        spo2: parseInt(form.spo2) || 99,
        blood_glucose: form.blood_glucose.trim() ? parseFloat(form.blood_glucose) : null,
        chief_complaint: form.chief_complaint,
        icd10_code: form.icd10_code,
        icd10_description: form.icd10_description,
        clinical_notes: form.clinical_notes,
      }),
      "تم توثيق الكشف السريري والتشخيص بنجاح",
      "تعذر حفظ الكشف السريري على الخادم",
      ["encounters"],
    );
    if (ok) onClose(); // on an error the form stays open to correct it
  };

  return (
    <ClinicModal title="توثيق كشف سريري وتشخيص طبي (EMR)" icon={<HeartPulse className="size-5 text-primary" />} onClose={onClose} size="lg" scroll>
      <form onSubmit={submit} className="space-y-3.5 text-xs">
        <PatientPicker id="encounter-patient" value={picked} onChange={setPicked} />

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>الطبيب الفاحص *</label>
            <Input required value={form.doctor_name} onChange={(e) => set({ doctor_name: e.target.value })} className="h-9 text-xs" />
          </div>
          <div>
            <label className={labelClass}>العيادة</label>
            <Input value={form.department} onChange={(e) => set({ department: e.target.value })} className="h-9 text-xs" />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 p-2.5 rounded-lg bg-muted/20 border border-border/30">
          {VITALS.map((v) => (
            <div key={v.key}>
              <label htmlFor={`enc-${v.key}`} className="block text-muted-foreground text-[10px] mb-1">{v.label}</label>
              <Input id={`enc-${v.key}`} inputMode="decimal" placeholder={v.placeholder} value={form[v.key]}
                onChange={(e) => set({ [v.key]: e.target.value })} className="h-8 text-xs font-mono" />
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>كود التشخيص الدولي (ICD-10)</label>
            <Input value={form.icd10_code} onChange={(e) => set({ icd10_code: e.target.value })} className="h-9 text-xs font-mono" />
          </div>
          <div>
            <label className={labelClass}>وصف التشخيص</label>
            <Input value={form.icd10_description} onChange={(e) => set({ icd10_description: e.target.value })} className="h-9 text-xs" />
          </div>
        </div>

        <div>
          <label className={labelClass}>الشكوى المرضية</label>
          <Input value={form.chief_complaint} onChange={(e) => set({ chief_complaint: e.target.value })} className="h-9 text-xs" />
        </div>

        <div>
          <label className={labelClass}>الملاحظات السريرية وخطة العلاج</label>
          <textarea
            rows={3}
            value={form.clinical_notes}
            onChange={(e) => set({ clinical_notes: e.target.value })}
            className="w-full rounded-md border border-input bg-background p-2.5 text-xs"
            placeholder="تدوين فحص الطبيب والتوصيات وخطة المتابعة..."
          />
        </div>

        <ModalActions busy={busy} onCancel={onClose} submitLabel="حفظ الكشف الطبي" />
      </form>
    </ClinicModal>
  );
}
