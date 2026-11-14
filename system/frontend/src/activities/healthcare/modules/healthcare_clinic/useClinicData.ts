import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ClinicPerms } from "./permissions";
import type { Appointment, Bed, Claim, ClinicSummary, Encounter, Invoice, LabOrder, Patient, Prescription } from "./types";

/** Query keys of the clinic's lists, for invalidation after a change. */
export const CLINIC_KEYS = {
  summary: ["clinic-summary"],
  appointments: ["clinic-appointments"],
  patients: ["clinic-patients"],
  clinicians: ["clinic-clinicians"],
  encounters: ["clinic-encounters"],
  prescriptions: ["clinic-prescriptions"],
  labs: ["clinic-labs"],
  beds: ["clinic-beds"],
  invoices: ["clinic-invoices"],
  claims: ["clinic-claims"],
} as const;

/** Every list the clinic screen shows. Billing lists load only for clinic:billing (#131). */
export function useClinicData(perms: ClinicPerms) {
  const summaryQuery = useQuery<ClinicSummary>({
    queryKey: CLINIC_KEYS.summary,
    queryFn: () => api.get("/clinic/summary"),
  });
  const appointmentsQuery = useQuery<Appointment[]>({
    queryKey: CLINIC_KEYS.appointments,
    queryFn: () => api.get("/clinic/appointments"),
  });
  const patientsQuery = useQuery<Patient[]>({
    queryKey: CLINIC_KEYS.patients,
    queryFn: () => api.get("/clinic/patients"),
  });
  const encountersQuery = useQuery<Encounter[]>({
    queryKey: CLINIC_KEYS.encounters,
    queryFn: () => api.get("/clinic/encounters"),
  });
  const prescriptionsQuery = useQuery<Prescription[]>({
    queryKey: CLINIC_KEYS.prescriptions,
    queryFn: () => api.get("/clinic/prescriptions"),
  });
  const labOrdersQuery = useQuery<LabOrder[]>({
    queryKey: CLINIC_KEYS.labs,
    queryFn: () => api.get("/clinic/lab-orders"),
  });
  const bedsQuery = useQuery<Bed[]>({
    queryKey: CLINIC_KEYS.beds,
    queryFn: () => api.get("/clinic/beds"),
  });
  const invoicesQuery = useQuery<Invoice[]>({
    queryKey: CLINIC_KEYS.invoices,
    queryFn: () => api.get("/clinic/invoices"),
    enabled: perms.billing,
  });
  const claimsQuery = useQuery<Claim[]>({
    queryKey: CLINIC_KEYS.claims,
    queryFn: () => api.get("/clinic/claims"),
    enabled: perms.billing,
  });

  const patients = patientsQuery.data ?? [];
  const appointments = appointmentsQuery.data ?? [];
  const encounters = encountersQuery.data ?? [];
  const prescriptions = prescriptionsQuery.data ?? [];
  const labOrders = labOrdersQuery.data ?? [];
  const beds = bedsQuery.data ?? [];
  const invoices = invoicesQuery.data ?? [];
  const claims = claimsQuery.data ?? [];

  const occupied = beds.filter((b) => b.status === "occupied").length;
  const summary: ClinicSummary = summaryQuery.data || {
    total_registered_patients: patients.length,
    today_appointments_count: appointments.length,
    waiting_queue_count: appointments.filter((a) => a.status === "waiting" || a.status === "in_consultation").length,
    total_beds: beds.length,
    occupied_beds: occupied,
    bed_occupancy_percent: Math.round((occupied / (beds.length || 1)) * 100),
    pending_lab_orders_count: labOrders.filter((l) => l.status !== "reported").length,
  };

  return {
    queries: {
      summary: summaryQuery,
      appointments: appointmentsQuery,
      patients: patientsQuery,
      encounters: encountersQuery,
      prescriptions: prescriptionsQuery,
      labOrders: labOrdersQuery,
      beds: bedsQuery,
      invoices: invoicesQuery,
      claims: claimsQuery,
    },
    summary,
    patients,
    appointments,
    encounters,
    prescriptions,
    labOrders,
    beds,
    invoices,
    claims,
  };
}

export type ClinicData = ReturnType<typeof useClinicData>;
