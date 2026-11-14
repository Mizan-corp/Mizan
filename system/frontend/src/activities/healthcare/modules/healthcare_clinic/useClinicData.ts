import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ClinicPerms } from "./permissions";
import type { Appointment, Bed, Claim, ClinicSummary, Encounter, Invoice, LabOrder, Page, Patient, Prescription } from "./types";

export interface Paging {
  page: number;
  pageSize: number;
}

export const DEFAULT_PAGE_SIZE = 25;

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

/** Every list the clinic screen shows. Patients and appointments are searched and paged on the
 *  server (#39); billing lists load only for clinic:billing (#131). */
export function useClinicData(
  perms: ClinicPerms,
  { search, patients: patientsPaging, appointments: appointmentsPaging }: { search: string; patients: Paging; appointments: Paging },
) {
  const summaryQuery = useQuery<ClinicSummary>({
    queryKey: CLINIC_KEYS.summary,
    queryFn: () => api.get("/clinic/summary"),
  });
  const appointmentsQuery = useQuery<Page<Appointment>>({
    queryKey: [...CLINIC_KEYS.appointments, search, appointmentsPaging.page, appointmentsPaging.pageSize],
    queryFn: () => api.get("/clinic/appointments", {
      search: search || undefined, page: appointmentsPaging.page, page_size: appointmentsPaging.pageSize,
    }),
    placeholderData: keepPreviousData,
  });
  const patientsQuery = useQuery<Page<Patient>>({
    queryKey: [...CLINIC_KEYS.patients, search, patientsPaging.page, patientsPaging.pageSize],
    queryFn: () => api.get("/clinic/patients", {
      search: search || undefined, page: patientsPaging.page, page_size: patientsPaging.pageSize,
    }),
    placeholderData: keepPreviousData,
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

  const patientsPage = patientsQuery.data;
  const appointmentsPage = appointmentsQuery.data;
  const patients = patientsPage?.items ?? [];
  const appointments = appointmentsPage?.items ?? [];
  const encounters = encountersQuery.data ?? [];
  const prescriptions = prescriptionsQuery.data ?? [];
  const labOrders = labOrdersQuery.data ?? [];
  const beds = bedsQuery.data ?? [];
  const invoices = invoicesQuery.data ?? [];
  const claims = claimsQuery.data ?? [];

  const occupied = beds.filter((b) => b.status === "occupied").length;
  const summary: ClinicSummary = summaryQuery.data || {
    total_registered_patients: patientsPage?.total ?? 0,
    today_appointments_count: appointmentsPage?.total ?? 0,
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
    patientsTotal: patientsPage?.total ?? 0,
    patientsPages: patientsPage?.pages ?? 1,
    appointmentsTotal: appointmentsPage?.total ?? 0,
    appointmentsPages: appointmentsPage?.pages ?? 1,
    encounters,
    prescriptions,
    labOrders,
    beds,
    invoices,
    claims,
  };
}

export type ClinicData = ReturnType<typeof useClinicData>;
