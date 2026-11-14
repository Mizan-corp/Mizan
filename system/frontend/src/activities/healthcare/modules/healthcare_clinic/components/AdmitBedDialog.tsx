import { useState } from "react";
import { Bed as BedIcon } from "lucide-react";
import { api } from "@/lib/api";
import { Input } from "@/components/kit/input";
import { moneyEGP } from "../format";
import { useClinicMutation } from "../useClinicActions";
import type { Bed } from "../types";
import { ClinicModal, ModalActions } from "./ClinicModal";
import { labelClass } from "./formStyles";

// Admits a patient to an available bed (POST /clinic/beds/{id}/admit, clinic:nurse or clinic:manage).
export default function AdmitBedDialog({ bed, onClose }: { bed: Bed; onClose: () => void }) {
  const run = useClinicMutation();
  const [patientName, setPatientName] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    await run(
      () => api.post(`/clinic/beds/${bed.id}/admit`, { patient_name: patientName, admission_date: "2026-11-05" }),
      `تم تسكين المريض بالسرير ${bed.bed_code}`,
      "تعذر تسكين المريض على الخادم",
      ["beds", "summary"],
    );
    onClose();
  };

  return (
    <ClinicModal
      title={`تسكين مريض بالسرير: ${bed.bed_code}`}
      icon={<BedIcon className="size-5 text-primary" />}
      subtitle={`${bed.ward_name} — ${bed.room_number} (${moneyEGP(bed.daily_rate)} / اليوم)`}
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-4 text-xs">
        <div>
          <label className={labelClass}>اسم المريض المراد تسكينه *</label>
          <Input required placeholder="مثال: محمود صبري حسن" value={patientName}
            onChange={(e) => setPatientName(e.target.value)} className="h-9 text-xs" />
        </div>
        <ModalActions onCancel={onClose} submitLabel="اعتماد التسكين" submitClassName="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold" />
      </form>
    </ClinicModal>
  );
}
