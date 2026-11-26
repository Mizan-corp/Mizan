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
  blood_glucose?: number | null;
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

export type ClinicTab = "appointments" | "patients" | "emr" | "rx_labs" | "beds" | "billing" | "claims" | "privacy" | "scheduling" | "referrals";

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

export type ReferralPriority = "routine" | "urgent" | "emergency";
export type ReferralStatus = "pending" | "accepted" | "declined" | "completed";

/** GET /clinic/referrals (#45). reason and triage_notes are null for coordinators (clinic:manage). */
export interface Referral {
  id: string;
  referral_ref: string;
  patient_id: string;
  patient_name: string;
  patient_mrn: string;
  from_doctor_user_id: string | null;
  from_doctor_name: string;
  to_department_id: string;
  to_department_name: string;
  to_doctor_user_id: string | null;
  to_doctor_name: string | null;
  priority: ReferralPriority;
  status: ReferralStatus;
  encounter_id: string | null;
  reason: string | null;
  triage_notes: string | null;
  response_note: string;
  responded_at: string | null;
  created_at: string;
  direction: "incoming" | "outgoing" | null;
  can_respond: boolean;
  can_complete: boolean;
}

/** GET /clinic/referrals/{id}: the encounter summary only with access to the record. */
export interface ReferralDetail extends Referral {
  record_access: boolean;
  last_encounter: (Pick<Encounter, "id" | "encounter_ref" | "encounter_date" | "doctor_name" | "department" | "bp_systolic"
    | "bp_diastolic" | "heart_rate" | "temperature" | "spo2" | "chief_complaint" | "icd10_code" | "icd10_description"
    | "clinical_notes">) | null;
}

/** GET /clinic/patients/{id}/vitals-history (#42): one point per encounter, oldest first; null = not recorded. */
export interface VitalsPoint {
  encounter_id: string;
  encounter_ref: string;
  date: string;
  bp_systolic: number | null;
  bp_diastolic: number | null;
  heart_rate: number | null;
  spo2: number | null;
  temperature: number | null;
  blood_glucose: number | null;
}

export interface VitalsHistory {
  patient_id: string;
  patient_name: string;
  points: VitalsPoint[];
  glucose_labs: { order_ref: string; test_name: string; value: number; unit: string; date: string }[];
}

export type ConsentKind = "procedure" | "surgery" | "data_sharing" | "other";
export type SignerRelation = "self" | "guardian" | "parent" | "spouse" | "other";

/** GET /clinic/patients/{id}/consents (#43). The signature is fetched through a signed link. */
export interface Consent {
  id: string;
  consent_ref: string;
  patient_id: string;
  encounter_id: string | null;
  kind: ConsentKind;
  title: string;
  body: string;
  signer_name: string;
  signer_relation: SignerRelation;
  signed_at: string;
  witness_name: string;
  revoked_at: string | null;
  revoke_reason: string;
  status: "active" | "revoked";
}

export type ImageModality = "XR" | "US" | "CT" | "MRI" | "other";

/** GET /clinic/patients/{id}/images (#44); url is a short-lived signed link (5 minutes). */
export interface ClinicImage {
  id: string;
  patient_id: string;
  encounter_id: string | null;
  modality: ImageModality;
  content_type: string;
  size: number;
  original_name: string;
  notes: string;
  uploaded_by: string | null;
  uploaded_by_name: string;
  created_at: string;
  is_dicom: boolean;
  url: string;
  expires_at: string;
}

/** The patient chart dialog's sections. */
export type ChartSection = "vitals" | "consents" | "images";
