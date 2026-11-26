import { useState } from "react";
import { UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/kit/input";
import { useDialogMutation } from "../useClinicActions";
import { ClinicModal, ModalActions } from "./ClinicModal";
import { labelClass, selectClass } from "./formStyles";

const BLOOD_GROUPS = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"];

// Opens a patient's file in the master patient index (POST /clinic/patients, clinic:manage).
export default function RegisterPatientDialog({ onClose }: { onClose: () => void }) {
  const { run, busy } = useDialogMutation();
  const [form, setForm] = useState({
    full_name: "",
    national_id: "",
    phone: "",
    gender: "ذكر",
    date_of_birth: "1990-01-01",
    blood_group: "O+",
    allergies: "",
    chronic_conditions: "",
    insurance_provider: "كشف نقدي (غير مؤمن)",
    insurance_policy_no: "",
    copay_percent: "0",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const mrn = `MRN-2026-${Math.floor(1000 + Math.random() * 9000)}`;
    const ok = await run(
      () => api.post("/clinic/patients", {
        patient_mrn: mrn,
        full_name: form.full_name,
        national_id: form.national_id,
        phone: form.phone,
        gender: form.gender,
        date_of_birth: form.date_of_birth,
        blood_group: form.blood_group,
        allergies: form.allergies || "لا توجد حساسيات مسجلة",
        chronic_conditions: form.chronic_conditions || "لا توجد أمراض مزمنة",
        insurance_provider: form.insurance_provider,
        insurance_policy_no: form.insurance_policy_no || "N/A",
        copay_percent: parseFloat(form.copay_percent) || 0,
      }),
      `تم فتح ملف المريض بنجاح برقم: ${mrn}`,
      "تعذر حفظ ملف المريض على الخادم",
      ["patients", "summary"],
    );
    if (ok) onClose(); // on an error the form stays open to correct it
  };

  return (
    <ClinicModal
      title="تسجيل ملف مريض جديد (Master Patient Index)"
      icon={<UserPlus className="size-5 text-primary" />}
      onClose={onClose}
      size="lg"
      scroll
    >
      <form onSubmit={submit} className="space-y-3.5 text-xs">
        <div>
          <label className={labelClass}>الاسم الرباعي للمريض *</label>
          <Input required placeholder="مثال: يوسف حسام الدين كمال" value={form.full_name}
            onChange={(e) => set({ full_name: e.target.value })} className="h-9 text-xs" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>الرقم القومي (14 رقم) *</label>
            <Input required placeholder="29801010101234" value={form.national_id}
              onChange={(e) => set({ national_id: e.target.value })} className="h-9 text-xs font-mono" />
          </div>
          <div>
            <label className={labelClass}>رقم الهاتف للتواصل *</label>
            <Input required placeholder="01012345678" value={form.phone}
              onChange={(e) => set({ phone: e.target.value })} className="h-9 text-xs font-mono" />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className={labelClass}>النوع</label>
            <select value={form.gender} onChange={(e) => set({ gender: e.target.value })} className={selectClass}>
              <option value="ذكر">ذكر</option>
              <option value="أنثى">أنثى</option>
            </select>
          </div>
          <div>
            <label className={labelClass}>تاريخ الميلاد</label>
            <Input type="date" value={form.date_of_birth}
              onChange={(e) => set({ date_of_birth: e.target.value })} className="h-9 text-xs font-mono" />
          </div>
          <div>
            <label className={labelClass}>فصيلة الدم</label>
            <select value={form.blood_group} onChange={(e) => set({ blood_group: e.target.value })} className={`${selectClass} font-mono`}>
              {BLOOD_GROUPS.map((bg) => (
                <option key={bg} value={bg}>{bg}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className={labelClass}>الحساسيات الدوائية والغذائية</label>
          <Input placeholder="مثال: حساسية البنسلين، حساسية السلفا..." value={form.allergies}
            onChange={(e) => set({ allergies: e.target.value })} className="h-9 text-xs" />
        </div>

        <div>
          <label className={labelClass}>الأمراض المزمنة والتاريخ المرضي</label>
          <Input placeholder="مثال: سكري، ضغط، ربو..." value={form.chronic_conditions}
            onChange={(e) => set({ chronic_conditions: e.target.value })} className="h-9 text-xs" />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <label className={labelClass}>الجهة الضامنة / التأمين الطبي</label>
            <Input placeholder="بوبا / أكسا / نقدي" value={form.insurance_provider}
              onChange={(e) => set({ insurance_provider: e.target.value })} className="h-9 text-xs" />
          </div>
          <div>
            <label className={labelClass}>نسبة التحمل %</label>
            <Input type="number" value={form.copay_percent}
              onChange={(e) => set({ copay_percent: e.target.value })} className="h-9 text-xs font-mono" />
          </div>
        </div>

        <ModalActions busy={busy} onCancel={onClose} submitLabel="تسجيل الملف الطبي" />
      </form>
    </ClinicModal>
  );
}
