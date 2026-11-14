import type { ClinicDialog } from "../ClinicContext";
import AdmitBedDialog from "./AdmitBedDialog";
import BookAppointmentDialog from "./BookAppointmentDialog";
import EncounterDialog from "./EncounterDialog";
import LabOrderDialog from "./LabOrderDialog";
import LabResultDialog from "./LabResultDialog";
import PrescriptionDialog from "./PrescriptionDialog";
import RegisterPatientDialog from "./RegisterPatientDialog";

/** The open clinic dialog, if any. Each dialog owns its form and its request. */
export default function ClinicDialogs({ dialog, onClose }: { dialog: ClinicDialog; onClose: () => void }) {
  switch (dialog?.kind) {
    case "patient":
      return <RegisterPatientDialog onClose={onClose} />;
    case "booking":
      return <BookAppointmentDialog patient={dialog.patient} onClose={onClose} />;
    case "encounter":
      return <EncounterDialog patient={dialog.patient} onClose={onClose} />;
    case "prescription":
      return <PrescriptionDialog patient={dialog.patient} onClose={onClose} />;
    case "lab":
      return <LabOrderDialog patient={dialog.patient} onClose={onClose} />;
    case "admit":
      return <AdmitBedDialog bed={dialog.bed} onClose={onClose} />;
    case "labResult":
      return <LabResultDialog order={dialog.order} onClose={onClose} />;
    default:
      return null;
  }
}
