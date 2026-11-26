import { createContext, useContext } from "react";
import type { ClinicPerms } from "./permissions";
import type { ClinicActions } from "./useClinicActions";
import type { ClinicData, Paging } from "./useClinicData";
import type { Bed, ChartSection, ClinicTab, Encounter, LabOrder, PatientRef, Prescription } from "./types";

export interface PagingControl extends Paging {
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
}

/** Which clinic dialog is open, with what it was opened for. */
export type ClinicDialog =
  | { kind: "patient" }
  | { kind: "booking"; patient?: PatientRef }
  | { kind: "encounter"; patient?: PatientRef }
  | { kind: "prescription"; patient?: PatientRef }
  | { kind: "lab"; patient?: PatientRef }
  | { kind: "admit"; bed: Bed }
  | { kind: "labResult"; order: LabOrder }
  | { kind: "referral"; patient: PatientRef; encounterId?: string }
  | { kind: "chart"; patient: PatientRef; section?: ChartSection; encounterId?: string }
  | null;

// The page (ClinicHealthcarePage) provides the data, the acting role's permissions, the row actions
// and the dialog opener; each tab under tabs/ reads them with useClinic().
export interface ClinicContextValue {
  perms: ClinicPerms;
  data: ClinicData;
  actions: ClinicActions;
  tab: ClinicTab;
  handleTabChange: (tab: string) => void;
  /** The search box; patients and appointments are searched on the server (#39). */
  search: string;
  paging: { patients: PagingControl; appointments: PagingControl };
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
