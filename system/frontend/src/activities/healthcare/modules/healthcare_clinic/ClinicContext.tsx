import { createContext, useContext } from "react";
import type { ClinicPerms } from "./permissions";
import type { ClinicActions } from "./useClinicActions";
import type { ClinicData } from "./useClinicData";
import type { Appointment, Bed, ClinicTab, Encounter, LabOrder, Patient, PatientRef, Prescription } from "./types";

/** Which clinic dialog is open, with what it was opened for. */
export type ClinicDialog =
  | { kind: "patient" }
  | { kind: "booking"; patient?: PatientRef }
  | { kind: "encounter"; patient?: PatientRef }
  | { kind: "prescription"; patient?: PatientRef }
  | { kind: "lab"; patient?: PatientRef }
  | { kind: "admit"; bed: Bed }
  | { kind: "labResult"; order: LabOrder }
  | null;

// The page (ClinicHealthcarePage) provides the data, the acting role's permissions, the row actions
// and the dialog opener; each tab under tabs/ reads them with useClinic().
export interface ClinicContextValue {
  perms: ClinicPerms;
  data: ClinicData;
  actions: ClinicActions;
  tab: ClinicTab;
  handleTabChange: (tab: string) => void;
  search: string;
  filteredAppts: Appointment[];
  filteredPatients: Patient[];
  filteredEncounters: Encounter[];
  filteredRx: Prescription[];
  filteredLabs: LabOrder[];
  openDialog: (dialog: Exclude<ClinicDialog, null>) => void;
}

export const ClinicContext = createContext<ClinicContextValue | null>(null);

export function useClinic(): ClinicContextValue {
  const ctx = useContext(ClinicContext);
  if (!ctx) throw new Error("useClinic must be used within ClinicProvider");
  return ctx;
}

export const ClinicProvider = ClinicContext.Provider;
