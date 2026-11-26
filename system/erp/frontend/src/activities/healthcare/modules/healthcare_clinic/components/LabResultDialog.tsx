import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/kit/input";
import { useDialogMutation } from "../useClinicActions";
import type { LabOrder } from "../types";
import { ClinicModal, ModalActions } from "./ClinicModal";
import { labelClass } from "./formStyles";

// Records and signs off a lab result (POST /clinic/lab-orders/{id}/result, clinic:lab).
export default function LabResultDialog({ order, onClose }: { order: LabOrder; onClose: () => void }) {
  const { run, busy } = useDialogMutation();
  const [value, setValue] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const ok = await run(
      () => api.post(`/clinic/lab-orders/${order.id}/result`, { result_value: value, is_signed_off: true }),
      "تم اعتماد نتيجة التحليل الطبي وإرفاقها بملف المريض",
      "تعذر اعتماد نتيجة التحليل على الخادم",
      ["labs"],
    );
    if (ok) onClose(); // on an error the form stays open to correct it
  };

  return (
    <ClinicModal
      title="اعتماد نتيجة الفحص المخبري"
      icon={<CheckCircle2 className="w-5 h-5 text-purple-400" />}
      subtitle={`${order.test_name} — المريض: ${order.patient_name}`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-3.5 text-xs">
        <div>
          <label className={labelClass}>النتيجة المخبرية المقروءة *</label>
          <Input required placeholder="مثال: 11.5 g/dL (طبيعي) أو سليم" value={value}
            onChange={(e) => setValue(e.target.value)} className="h-9 text-xs" />
        </div>
        <ModalActions busy={busy} onCancel={onClose} submitLabel="اعتماد النتيجة بملف المريض" submitClassName="bg-purple-600 hover:bg-purple-500 text-white font-semibold" />
      </form>
    </ClinicModal>
  );
}
