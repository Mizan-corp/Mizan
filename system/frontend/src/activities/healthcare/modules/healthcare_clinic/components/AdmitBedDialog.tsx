import { useState } from "react";
import { Bed as BedIcon } from "lucide-react";
import { api } from "@/lib/api";
import { moneyEGP } from "../format";
import { useClinicMutation } from "../useClinicActions";
import type { Bed, PatientRef } from "../types";
import { ClinicModal, ModalActions } from "./ClinicModal";
import PatientPicker from "./PatientPicker";

// Admits a patient to an available bed (POST /clinic/beds/{id}/admit, clinic:nurse or clinic:manage).
export default function AdmitBedDialog({ bed, onClose }: { bed: Bed; onClose: () => void }) {
  const run = useClinicMutation();
  const [picked, setPicked] = useState<PatientRef | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!picked) return;
    await run(
      () => api.post(`/clinic/beds/${bed.id}/admit`, { patient_id: picked.id, patient_name: picked.full_name, admission_date: new Date().toISOString().slice(0, 10) }),
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
        <PatientPicker id="admit-patient" label="المريض المراد تسكينه *" value={picked} onChange={setPicked} />
        <ModalActions onCancel={onClose} submitLabel="اعتماد التسكين" submitClassName="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold" />
      </form>
    </ClinicModal>
  );
}
