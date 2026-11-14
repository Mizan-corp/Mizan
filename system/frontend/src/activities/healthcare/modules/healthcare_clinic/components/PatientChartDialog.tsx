import { useState } from "react";
import { Activity, FileSignature, FolderHeart } from "lucide-react";
import { useClinic } from "../ClinicContext";
import type { ChartSection, PatientRef } from "../types";
import { ClinicModal } from "./ClinicModal";
import ConsentsPanel from "./ConsentsPanel";
import VitalsPanel from "./VitalsPanel";

const SECTIONS: { id: ChartSection; label: string; icon: React.ReactNode }[] = [
  { id: "vitals", label: "العلامات الحيوية", icon: <Activity className="size-3.5" /> },
  { id: "consents", label: "نماذج الموافقة", icon: <FileSignature className="size-3.5" /> },
];

// The patient's chart: clinical sections read with access to the record (#113), each logged.
export default function PatientChartDialog({ patient, section = "vitals", encounterId, onClose }: {
  patient: PatientRef;
  section?: ChartSection;
  encounterId?: string;
  onClose: () => void;
}) {
  const { perms } = useClinic();
  const [active, setActive] = useState<ChartSection>(section);
  return (
    <ClinicModal title={`الملف السريري — ${patient.full_name}`} icon={<FolderHeart className="size-5 text-primary" />}
      onClose={onClose} size="xl" scroll>
      <div className="flex gap-1 border-b border-border/60 mb-4" role="tablist">
        {SECTIONS.map((s) => (
          <button key={s.id} role="tab" aria-selected={active === s.id} onClick={() => setActive(s.id)}
            className={`px-3 py-2 text-xs font-semibold border-b-2 flex items-center gap-1.5 cursor-pointer ${
              active === s.id ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"}`}>
            {s.icon}
            {s.label}
          </button>
        ))}
      </div>
      {active === "vitals" && <VitalsPanel patientId={patient.id} />}
      {active === "consents" && <ConsentsPanel patientId={patient.id} encounterId={encounterId} canSign={perms.clinician} />}
    </ClinicModal>
  );
}
