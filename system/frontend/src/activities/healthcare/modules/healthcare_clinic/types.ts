// The clinic's API records, as /clinic/* returns them (healthcare_clinic/router.py).

/** How the acting user reads a patient's clinical record (#113); null: demographics only. */
export type PatientAccess = "all" | "setting" | "team" | "break_glass" | null;

export interface ClinicSummary {
  total_registered_patients: number;
  today_appointments_count: number;
  waiting_queue_count: number;
  total_beds: number;
  occupied_beds: number;
  bed_occupancy_percent: number;
  pending_lab_orders_count: number;
  // Only for clinic:billing (#131).
  total_revenue_billed?: number;
  total_revenue_collected?: number;
  total_revenue_pending?: number;
  insurance_claims_total?: number;
  insurance_claims_approved?: number;
  insurance_claims_count?: number;
}

export interface Patient {
  id: string;
  patient_mrn: string;
  full_name: string;
  national_id: string;
  phone: string;
  gender: string;
  date_of_birth: string;
  blood_group: string | null;
  allergies: string | null;
  chronic_conditions: string | null;
  insurance_provider: string;
  insurance_policy_no: string;
  copay_percent: number;
  clinical_access: boolean;
  access: PatientAccess;
}

/** A patient picked for a form: enough to send patient_id and show the name. */
export type PatientRef = Pick<Patient, "id" | "full_name"> & { patient_mrn?: string };

export type AppointmentStatus = "scheduled" | "waiting" | "in_consultation" | "completed" | "cancelled" | "no_show";

export interface Appointment {
  id: string;
  appointment_ref: string;
  patient_id: string;
  patient_name: string;
  doctor_name: string;
  doctor_user_id: string | null;
  department: string;
  department_id?: string | null;
  room_id?: string | null;
  appointment_date: string;
  /** "HH:MM" (24h) since #36; older appointments may hold "10:30 AM". */
  time_slot: string;
  queue_number: number;
  status: AppointmentStatus;
  consultation_fee: number;
  chief_complaint: string;
}

export interface Encounter {
  id: string;
  encounter_ref: string;
  patient_id: string;
  patient_name: string;
  doctor_name: string;
  department: string;
  encounter_date: string;
  bp_systolic: number;
  bp_diastolic: number;
  heart_rate: number;
  temperature: number;
  spo2: number;
  chief_complaint: string;
  icd10_code: string;
  icd10_description: string;
  clinical_notes: string;
}

export interface Prescription {
  id: string;
  rx_ref: string;
  encounter_ref?: string;
  patient_id: string;
  patient_name: string;
  doctor_name: string;
  issue_date: string;
  medication_name: string;
  dosage: string;
  frequency: string;
  duration_days: number;
  quantity?: number;
  instructions: string;
  status: "pending" | "dispensed";
}

export interface LabOrder {
  id: string;
  order_ref: string;
  patient_id: string;
  patient_name: string;
  doctor_name: string;
  test_name: string;
  category: string;
  specimen_barcode: string;
  reference_range: string;
  result_value: string;
  numeric_value?: number | null;
  unit?: string;
  is_critical?: boolean;
  status: "ordered" | "collected" | "reported";
  is_signed_off: boolean;
}

export interface Bed {
  id: string;
  bed_code: string;
  ward_name: string;
  room_number: string;
  bed_type: string;
  daily_rate: number;
  status: "available" | "occupied" | "cleaning" | "maintenance";
  current_patient_id?: string | null;
  current_patient_name: string;
  admission_date: string;
}

export interface InvoiceCharge {
  description: string;
  amount: number;
}

export interface Invoice {
  id: string;
  invoice_ref: string;
  patient_id: string;
  patient_name: string;
  appointment_id: string | null;
  total: number;
  copay_percent: number;
  insurance_amount: number;
  patient_amount: number;
  paid_amount: number;
  status: string;
  payment_method: string;
  created_at: string;
  charges: InvoiceCharge[];
}

export interface Claim {
  id: string;
  claim_ref: string;
  patient_id: string;
  patient_name: string;
  invoice_id: string | null;
  insurance_provider: string;
  policy_no: string;
  copay_percent: number;
  claimed_amount: number;
  approved_amount: number;
  status: string;
  submitted_at: string;
  notes: string;
}

/** A workspace user who acts clinically (GET /clinic/clinicians). */
export interface Clinician {
  id: string;
  full_name: string;
  role: string | null;
  is_doctor: boolean;
}

export type ClinicTab = "appointments" | "patients" | "emr" | "rx_labs" | "beds" | "billing" | "claims" | "privacy" | "scheduling";

/** Department master (#36). */
export interface Department {
  id: string;
  code: string;
  name: string;
  specialty_code: string;
  active: boolean;
}

export interface Room {
  id: string;
  name: string;
  department_id: string | null;
  active: boolean;
}

/** A doctor's weekly roster row; weekday 0 = Monday … 6 = Sunday. */
export interface DoctorSchedule {
  id: string;
  doctor_user_id: string;
  doctor_name: string;
  department_id: string;
  department_name: string | null;
  room_id: string | null;
  room_name: string | null;
  weekday: number;
  weekday_name: string;
  start_time: string;
  end_time: string;
  slot_minutes: number;
  active: boolean;
}

/** GET /clinic/schedule/slots */
export interface SlotList {
  has_roster: boolean;
  slots: { time: string; minutes: number; available: boolean; department_id: string; room_id: string | null; room_name: string | null }[];
}

/** A page of a server-side list (GET /clinic/patients, /clinic/appointments; #39). */
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pages: number;
}
