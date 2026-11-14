import { useState } from "react";
import { Microscope } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/kit/input";
import { useDialogMutation } from "../useClinicActions";
import type { PatientRef } from "../types";
import { ClinicModal, ModalActions } from "./ClinicModal";
import PatientPicker from "./PatientPicker";
import { labelClass, selectClass } from "./formStyles";

const LAB_CATEGORIES = [
  { value: "كيمياء حيوية سريرية", label: "كيمياء حيوية سريرية" },
  { value: "أمراض الدم (Hematology)", label: "أمراض الدم" },
  { value: "الأشعة والتصوير الطبي", label: "الأشعة والتصوير" },
  { value: "مناعة ومصليات (Serology)", label: "مناعة ومصليات" },
  { value: "علم الأمراض والأنسجة", label: "علم الأمراض والأنسجة" },
];

// Sends a lab or imaging order to the lab queue (POST /clinic/lab-orders, clinic:doctor).
export default function LabOrderDialog({ patient, onClose }: { patient?: PatientRef; onClose: () => void }) {
  const { run, busy } = useDialogMutation();
  const [form, setForm] = useState(() => ({
    doctor_name: "د. هشام الشناوي",
    test_name: "صورة دم كاملة (CBC)",
    category: "أمراض الدم (Hematology)",
    specimen_barcode: "SPEC-" + Math.floor(1000 + Math.random() * 9000),
    reference_range: "معتمد مخبرياً",
  }));
  const [picked, setPicked] = useState<PatientRef | null>(patient ?? null);
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!picked) return;
    const ok = await run(
      () => api.post("/clinic/lab-orders", {
        patient_id: picked.id,
        patient_name: picked.full_name,
        doctor_name: form.doctor_name,
        test_name: form.test_name,
        category: form.category,
        specimen_barcode: form.specimen_barcode,
        reference_range: form.reference_range,
      }),
      "تم إرسال طلب الفحص إلى المختبر الطبي",
      "تعذر إرسال طلب الفحص إلى الخادم",
      ["labs"],
    );
    if (ok) onClose(); // on an error the form stays open to correct it
  };

  return (
    <ClinicModal title="طلب فحص مخبري أو تصوير طبي" icon={<Microscope className="w-5 h-5 text-purple-400" />} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3.5 text-xs">
        <PatientPicker id="lab-patient" value={picked} onChange={setPicked} />

        <div>
          <label className={labelClass}>اسم الفحص أو التحليل *</label>
          <Input required placeholder="مثال: وظائف كبد كاملة (Liver Function Tests)" value={form.test_name}
            onChange={(e) => set({ test_name: e.target.value })} className="h-9 text-xs" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>القسم المخبري</label>
            <select value={form.category} onChange={(e) => set({ category: e.target.value })} className={selectClass}>
              {LAB_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>باركود العينة</label>
            <Input value={form.specimen_barcode} onChange={(e) => set({ specimen_barcode: e.target.value })} className="h-9 text-xs font-mono" />
          </div>
        </div>

        <ModalActions busy={busy} onCancel={onClose} submitLabel="إرسال أمر الفحص" submitClassName="bg-purple-600 hover:bg-purple-500 text-white font-semibold" />
      </form>
    </ClinicModal>
  );
}
