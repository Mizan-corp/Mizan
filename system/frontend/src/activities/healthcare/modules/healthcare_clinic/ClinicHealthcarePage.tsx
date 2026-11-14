import React, { useState, lazy, Suspense } from "react";
import { useSearchParams, useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, BarChart3, Bed, Bell, Briefcase, Building2, Calculator, Calendar, CheckCircle2, DoorOpen, FileText, Flame, FlaskConical, HeartPulse, Hospital, Laptop, Lock, Microscope, Package, Pill, RefreshCw, Scan, Scissors, Search, ShieldCheck, Stethoscope, UserCheck, UserPlus, Users, Video, X } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui";
import { Badge } from "@/components/kit/badge";
import { Button } from "@/components/kit/button";
import { Card } from "@/components/kit/card";
import { Input } from "@/components/kit/input";
import { sound } from "@/lib/sound";
import { ClinicProvider } from "./ClinicContext";
import AppointmentsTab from "./tabs/AppointmentsTab";
import EMRTab from "./tabs/EMRTab";
import RxLabsTab from "./tabs/RxLabsTab";
import BedsTab from "./tabs/BedsTab";
import BillingTab from "./tabs/BillingTab";
import ClaimsTab from "./tabs/ClaimsTab";
import PatientsTab from "./tabs/PatientsTab";
import PrivacyTab from "./tabs/PrivacyTab";
import type { Clinician } from "./components/CareTeamDialog";
import { useClinicPerms } from "./permissions";

// Standalone 24 Healthcare ERP Modules (HLT-01..24)
// preview: the screen runs on sample data and isn't wired to the API yet; it says so (#47).
export const HEALTHCARE_MODULES_MAP: Record<string, { code: string; title: string; category: string; icon: any; component: React.LazyExoticComponent<any>; preview?: boolean }> = {
  facility_management: { code: "HLT-01", title: "إدارة المنشآت والمرافق", category: "Core", icon: Building2, component: lazy(() => import("@activities/healthcare/modules/facility_management/FacilityManagementPage")), preview: true },
  patient_identity: { code: "HLT-02", title: "تسجيل وهوية المرضى (MPI)", category: "Patients", icon: Users, component: lazy(() => import("@activities/healthcare/modules/patient_identity/PatientIdentityPage")) },
  appointments_sched: { code: "HLT-03", title: "المواعيد وجدولة الأطباء", category: "Patients", icon: Calendar, component: lazy(() => import("@activities/healthcare/modules/appointments/AppointmentsPage")) },
  medical_staff: { code: "HLT-04", title: "الأطباء والكوادر الطبية", category: "Core", icon: UserCheck, component: lazy(() => import("@activities/healthcare/modules/medical_staff/MedicalStaffPage")) },
  emr_records: { code: "HLT-05", title: "السجل الطبي التراكمي (EMR)", category: "Clinical", icon: FileText, component: lazy(() => import("@activities/healthcare/modules/emr/EmrPage")) },
  consultation: { code: "HLT-06", title: "الكشف السريري (SOAP)", category: "Clinical", icon: Stethoscope, component: lazy(() => import("@activities/healthcare/modules/consultation/ConsultationPage")) },
  admissions: { code: "HLT-07", title: "التنويم والإدخال والخروج", category: "Hospital", icon: DoorOpen, component: lazy(() => import("@activities/healthcare/modules/admissions/AdmissionsPage")) },
  beds_mgmt: { code: "HLT-08", title: "إدارة الأسرة والأجنحة", category: "Hospital", icon: Bed, component: lazy(() => import("@activities/healthcare/modules/beds/BedsPage")) },
  nursing: { code: "HLT-09", title: "التمريض وسجل الأدوية (MAR)", category: "Hospital", icon: HeartPulse, component: lazy(() => import("@activities/healthcare/modules/nursing/NursingPage")) },
  laboratory: { code: "HLT-10", title: "المختبرات والتحاليل (LIS)", category: "Diagnostics", icon: FlaskConical, component: lazy(() => import("@activities/healthcare/modules/laboratory/LaboratoryPage")) },
  radiology: { code: "HLT-11", title: "الأشعة والتصوير (RIS/PACS)", category: "Diagnostics", icon: Scan, component: lazy(() => import("@activities/healthcare/modules/radiology/RadiologyPage")) },
  pharmacy: { code: "HLT-12", title: "صيدلية المستشفى وصرف الدواء", category: "Diagnostics", icon: Pill, component: lazy(() => import("@activities/healthcare/modules/hospital_pharmacy/PharmacyPage")) },
  emergency: { code: "HLT-13", title: "قسم الطوارئ والفرز (ER)", category: "Hospital", icon: Flame, component: lazy(() => import("@activities/healthcare/modules/emergency/EmergencyPage")) },
  surgery: { code: "HLT-14", title: "العمليات الجراحية (OT)", category: "Hospital", icon: Scissors, component: lazy(() => import("@activities/healthcare/modules/surgery/SurgeryPage")) },
  billing_accounts: { code: "HLT-15", title: "الفوترة الطبية وحسابات المرضى", category: "Revenue", icon: FileText, component: lazy(() => import("@activities/healthcare/modules/medical_billing/BillingPage")) },
  insurance_claims: { code: "HLT-16", title: "التأمين الطبي والمطالبات", category: "Revenue", icon: ShieldCheck, component: lazy(() => import("@activities/healthcare/modules/health_insurance/InsurancePage")) },
  inventory_procurement: { code: "HLT-17", title: "المستودعات الطبية والمشتريات", category: "Revenue", icon: Package, component: lazy(() => import("@activities/healthcare/modules/medical_supplies/InventoryProcurementPage")) },
  accounting_cost: { code: "HLT-18", title: "المحاسبة ومراكز التكلفة", category: "Revenue", icon: Calculator, component: lazy(() => import("@activities/healthcare/modules/medical_accounting/AccountingPage")) },
  hr_workforce: { code: "HLT-19", title: "الموارد البشرية والامتيازات", category: "Core", icon: Briefcase, component: lazy(() => import("@activities/healthcare/modules/medical_workforce/HrWorkforcePage")) },
  equipment_maintenance: { code: "HLT-20", title: "الأجهزة والمعايرة الحيوية", category: "Diagnostics", icon: Activity, component: lazy(() => import("@activities/healthcare/modules/equipment_maintenance/EquipmentMaintenancePage")) },
  patient_portal: { code: "HLT-21", title: "بوابة المريض والخدمات الذاتية", category: "Patients", icon: Laptop, component: lazy(() => import("@activities/healthcare/modules/patient_portal/PatientPortalPage")) },
  telemedicine: { code: "HLT-22", title: "الطب الاتصالي والاستشارات المرئية", category: "Clinical", icon: Video, component: lazy(() => import("@activities/healthcare/modules/telemedicine/TelemedicinePage")) },
  notifications: { code: "HLT-23", title: "الإشعارات والتنبيهات الطبية", category: "Patients", icon: Bell, component: lazy(() => import("@activities/healthcare/modules/patient_notifications/NotificationsPage")) },
  analytics: { code: "HLT-24", title: "المؤشرات والذكاء السريري", category: "Revenue", icon: BarChart3, component: lazy(() => import("@activities/healthcare/modules/hospital_analytics/AnalyticsPage")) },
  access_control: { code: "SEC-01", title: "المستخدمون والأدوار والمسميات", category: "Core", icon: ShieldCheck, component: lazy(() => import("@app/features/users/UsersPage")) },
};


// ─── Interfaces ─────────────────────────────────────────────────────────────
interface ClinicSummary {
  total_registered_patients: number;
  today_appointments_count: number;
  waiting_queue_count: number;
  total_beds: number;
  occupied_beds: number;
  bed_occupancy_percent: number;
  pending_lab_orders_count: number;
}

interface ClinicPatient {
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
  access: "all" | "setting" | "team" | "break_glass" | null;
}

interface ClinicAppointment {
  id: string;
  appointment_ref: string;
  patient_id: string;
  patient_name: string;
  doctor_name: string;
  department: string;
  appointment_date: string;
  time_slot: string;
  queue_number: number;
  status: "scheduled" | "waiting" | "in_consultation" | "completed" | "cancelled";
  consultation_fee: number;
  chief_complaint: string;
}

interface ClinicEncounter {
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

interface ClinicPrescription {
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
  instructions: string;
  status: "pending" | "dispensed";
}

interface ClinicLabOrder {
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
  status: "ordered" | "collected" | "reported";
  is_signed_off: boolean;
}

interface ClinicBed {
  id: string;
  bed_code: string;
  ward_name: string;
  room_number: string;
  bed_type: string;
  daily_rate: number;
  status: "available" | "occupied" | "cleaning" | "maintenance";
  current_patient_name: string;
  admission_date: string;
}

interface ClinicInvoice {
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
  charges: { description: string; amount: number }[];
}

interface ClinicInsuranceClaim {
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

const moneyEGP = (amount: number) =>
  `${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ج.م`;

// ─── Main Component ─────────────────────────────────────────────────────────
export default function ClinicHealthcarePage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  // Tab routing with URL parameter sync
  const { moduleSlug } = useParams<{ moduleSlug?: string }>();
  const navigate = useNavigate();
  const tabParam = searchParams.get("tab");
  const activeModuleKey = moduleSlug || (tabParam && HEALTHCARE_MODULES_MAP[tabParam] ? tabParam : null);
  const [activeCategory, setActiveCategory] = useState<string>("All");

  const perms = useClinicPerms();
  const canPrivacy = perms.privacy;
  const validTabs = ["appointments", "patients", "emr", "rx_labs", "labs", "beds", ...(perms.billing ? ["billing", "claims"] : []), ...(canPrivacy ? ["privacy"] : [])];
  const tab = tabParam && validTabs.includes(tabParam)
    ? (tabParam === "labs" ? "rx_labs" : (tabParam as "appointments" | "patients" | "emr" | "rx_labs" | "beds" | "billing" | "claims" | "privacy"))
    : "appointments";

  const handleTabChange = (newTab: string) => {
    sound.click();
    if (moduleSlug) {
      navigate(`/clinic?tab=${newTab}`);
    } else {
      setSearchParams({ tab: newTab });
    }
  };

  const handleSelectModule = (modKey: string | null) => {
    sound.click();
    if (!modKey) {
      if (moduleSlug) navigate("/clinic");
      else setSearchParams({ tab: "appointments" });
    } else {
      if (moduleSlug) navigate(`/clinic/${modKey}`);
      else setSearchParams({ tab: modKey });
    }
  };

  const [search, setSearch] = useState("");

  // Modals state
  const [isBookingOpen, setIsBookingOpen] = useState(false);
  const [isPatientModalOpen, setIsPatientModalOpen] = useState(false);
  const [isEncounterModalOpen, setIsEncounterModalOpen] = useState(false);
  const [isRxModalOpen, setIsRxModalOpen] = useState(false);
  const [isLabModalOpen, setIsLabModalOpen] = useState(false);
  const [admitBedTarget, setAdmitBedTarget] = useState<ClinicBed | null>(null);
  const [admitPatientName, setAdmitPatientName] = useState("");
  const [labResultModalTarget, setLabResultModalTarget] = useState<ClinicLabOrder | null>(null);
  const [labResultValue, setLabResultValue] = useState("");

  // Forms State
  const [bookingForm, setBookingForm] = useState({
    patient_id: "",
    patient_name: "",
    doctor_user_id: "",
    department: "الباطنة العامة",
    appointment_date: "2026-11-05",
    time_slot: "11:30 AM",
    consultation_fee: "350",
    chief_complaint: "",
  });

  const [patientForm, setPatientForm] = useState({
    full_name: "",
    national_id: "",
    phone: "",
    gender: "ذكر",
    date_of_birth: "1990-01-01",
    blood_group: "O+",
    allergies: "",
    chronic_conditions: "",
    insurance_provider: "كشف نقدي (غير مؤمن)",
    insurance_policy_no: "",
    copay_percent: "0",
  });

  const [encounterForm, setEncounterForm] = useState({
    patient_id: "",
    patient_name: "",
    doctor_name: "د. هشام الشناوي",
    department: "الباطنة العامة",
    encounter_date: "2026-11-05",
    bp_systolic: "120",
    bp_diastolic: "80",
    heart_rate: "75",
    temperature: "37.0",
    spo2: "99",
    chief_complaint: "",
    icd10_code: "E11.9",
    icd10_description: "داء السكري النوع الثاني",
    clinical_notes: "",
  });

  const [rxForm, setRxForm] = useState({
    patient_id: "",
    patient_name: "",
    doctor_name: "د. هشام الشناوي",
    issue_date: "2026-11-05",
    medication_name: "",
    dosage: "500mg",
    frequency: "قرص كل 12 ساعة",
    duration_days: "14",
    instructions: "يؤخذ بعد الأكل مع كوب ماء كامل",
  });

  const [labForm, setLabForm] = useState({
    patient_id: "",
    patient_name: "",
    doctor_name: "د. هشام الشناوي",
    test_name: "صورة دم كاملة (CBC)",
    category: "أمراض الدم (Hematology)",
    specimen_barcode: "SPEC-" + Math.floor(1000 + Math.random() * 9000),
    reference_range: "معتمد مخبرياً",
  });

  // Queries with auto-fallback to realistic data
  const { data: summaryData, isLoading: isSummaryLoading } = useQuery<ClinicSummary>({
    queryKey: ["clinic-summary"],
    queryFn: () => api.get("/clinic/summary"),
  });

  const { data: appointmentsData = [] } = useQuery<ClinicAppointment[]>({
    queryKey: ["clinic-appointments"],
    queryFn: () => api.get("/clinic/appointments"),
  });

  const { data: patientsData = [] } = useQuery<ClinicPatient[]>({
    queryKey: ["clinic-patients"],
    queryFn: () => api.get("/clinic/patients"),
  });

  const { data: cliniciansData = [] } = useQuery<Clinician[]>({
    queryKey: ["clinic-clinicians"],
    queryFn: () => api.get("/clinic/clinicians"),
    enabled: isBookingOpen,
  });

  const { data: encountersData = [] } = useQuery<ClinicEncounter[]>({
    queryKey: ["clinic-encounters"],
    queryFn: () => api.get("/clinic/encounters"),
  });

  const { data: prescriptionsData = [] } = useQuery<ClinicPrescription[]>({
    queryKey: ["clinic-prescriptions"],
    queryFn: () => api.get("/clinic/prescriptions"),
  });

  const { data: labOrdersData = [] } = useQuery<ClinicLabOrder[]>({
    queryKey: ["clinic-labs"],
    queryFn: () => api.get("/clinic/lab-orders"),
  });

  const { data: bedsData = [] } = useQuery<ClinicBed[]>({
    queryKey: ["clinic-beds"],
    queryFn: () => api.get("/clinic/beds"),
  });

  const { data: invoicesData = [] } = useQuery<ClinicInvoice[]>({
    queryKey: ["clinic-invoices"],
    queryFn: () => api.get("/clinic/invoices"),
    enabled: perms.billing,
  });

  const { data: claimsData = [] } = useQuery<ClinicInsuranceClaim[]>({
    queryKey: ["clinic-claims"],
    queryFn: () => api.get("/clinic/claims"),
    enabled: perms.billing,
  });

  // Datasets from API queries
  const patients = patientsData;
  const appointments = appointmentsData;
  const encounters = encountersData;
  const prescriptions = prescriptionsData;
  const labOrders = labOrdersData;
  const beds = bedsData;

  const summary: ClinicSummary = summaryData || {
    total_registered_patients: patients.length,
    today_appointments_count: appointments.length,
    waiting_queue_count: appointments.filter((a) => a.status === "waiting" || a.status === "in_consultation").length,
    total_beds: beds.length,
    occupied_beds: beds.filter((b) => b.status === "occupied").length,
    bed_occupancy_percent: Math.round((beds.filter((b) => b.status === "occupied").length / (beds.length || 1)) * 100),
    pending_lab_orders_count: labOrders.filter((l) => l.status !== "reported").length,
  };

  // Handlers
  const handleUpdateApptStatus = async (apptId: string, newStatus: string) => {
    sound.click();
    try {
      await api.post(`/clinic/appointments/${apptId}/status`, { status: newStatus });
      toast("success", "تم تحديث حالة الموعد الطبي بنجاح");
      queryClient.invalidateQueries({ queryKey: ["clinic-appointments"] });
      queryClient.invalidateQueries({ queryKey: ["clinic-summary"] });
      queryClient.invalidateQueries({ queryKey: ["clinic-invoices"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || "تعذر تحديث حالة الموعد على الخادم");
    }
  };

  const handleCreateAppointment = async (e: React.FormEvent) => {
    e.preventDefault();
    sound.click();
    try {
      await api.post("/clinic/appointments", {
        patient_id: bookingForm.patient_id,
        patient_name: bookingForm.patient_name,
        doctor_user_id: bookingForm.doctor_user_id,
        department: bookingForm.department,
        appointment_date: bookingForm.appointment_date,
        time_slot: bookingForm.time_slot,
        consultation_fee: parseFloat(bookingForm.consultation_fee) || 250,
        chief_complaint: bookingForm.chief_complaint,
      });
      toast("success", "تم حجز الموعد وإدراجه في قائمة الانتظار");
      setIsBookingOpen(false);
      queryClient.invalidateQueries({ queryKey: ["clinic-appointments"] });
      queryClient.invalidateQueries({ queryKey: ["clinic-summary"] });
      queryClient.invalidateQueries({ queryKey: ["clinic-patients"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر حفظ الموعد على الخادم");
    }
  };

  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    sound.click();
    const mrn = `MRN-2026-${Math.floor(1000 + Math.random() * 9000)}`;
    try {
      await api.post("/clinic/patients", {
        patient_mrn: mrn,
        full_name: patientForm.full_name,
        national_id: patientForm.national_id,
        phone: patientForm.phone,
        gender: patientForm.gender,
        date_of_birth: patientForm.date_of_birth,
        blood_group: patientForm.blood_group,
        allergies: patientForm.allergies || "لا توجد حساسيات مسجلة",
        chronic_conditions: patientForm.chronic_conditions || "لا توجد أمراض مزمنة",
        insurance_provider: patientForm.insurance_provider,
        insurance_policy_no: patientForm.insurance_policy_no || "N/A",
        copay_percent: parseFloat(patientForm.copay_percent) || 0,
      });
      toast("success", `تم فتح ملف المريض بنجاح برقم: ${mrn}`);
      setIsPatientModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["clinic-patients"] });
      queryClient.invalidateQueries({ queryKey: ["clinic-summary"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر حفظ ملف المريض على الخادم");
      setIsPatientModalOpen(false);
    }
  };

  const handleCreateEncounter = async (e: React.FormEvent) => {
    e.preventDefault();
    sound.click();
    try {
      await api.post("/clinic/encounters", {
        patient_id: encounterForm.patient_id || "pat-" + Date.now(),
        patient_name: encounterForm.patient_name,
        doctor_name: encounterForm.doctor_name,
        department: encounterForm.department,
        encounter_date: encounterForm.encounter_date,
        bp_systolic: parseInt(encounterForm.bp_systolic) || 120,
        bp_diastolic: parseInt(encounterForm.bp_diastolic) || 80,
        heart_rate: parseInt(encounterForm.heart_rate) || 75,
        temperature: parseFloat(encounterForm.temperature) || 37.0,
        spo2: parseInt(encounterForm.spo2) || 99,
        chief_complaint: encounterForm.chief_complaint,
        icd10_code: encounterForm.icd10_code,
        icd10_description: encounterForm.icd10_description,
        clinical_notes: encounterForm.clinical_notes,
      });
      toast("success", "تم توثيق الكشف السريري والتشخيص بنجاح");
      setIsEncounterModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["clinic-encounters"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر حفظ الكشف السريري على الخادم");
      setIsEncounterModalOpen(false);
    }
  };

  const handleCreatePrescription = async (e: React.FormEvent) => {
    e.preventDefault();
    sound.click();
    try {
      await api.post("/clinic/prescriptions", {
        patient_id: rxForm.patient_id || "pat-" + Date.now(),
        patient_name: rxForm.patient_name,
        doctor_name: rxForm.doctor_name,
        issue_date: rxForm.issue_date,
        medication_name: rxForm.medication_name,
        dosage: rxForm.dosage,
        frequency: rxForm.frequency,
        duration_days: parseInt(rxForm.duration_days) || 14,
        instructions: rxForm.instructions,
      });
      toast("success", "تم إصدار الروشتة الطبية وتوجيهها للصيدلية");
      setIsRxModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["clinic-prescriptions"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر إصدار الروشتة على الخادم");
      setIsRxModalOpen(false);
    }
  };

  const handleCreateLabOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    sound.click();
    try {
      await api.post("/clinic/lab-orders", {
        patient_id: labForm.patient_id || "pat-" + Date.now(),
        patient_name: labForm.patient_name,
        doctor_name: labForm.doctor_name,
        test_name: labForm.test_name,
        category: labForm.category,
        specimen_barcode: labForm.specimen_barcode,
        reference_range: labForm.reference_range,
      });
      toast("success", "تم إرسال طلب الفحص إلى المختبر الطبي");
      setIsLabModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["clinic-labs"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر إرسال طلب الفحص إلى الخادم");
      setIsLabModalOpen(false);
    }
  };

  const handleDispenseRx = async (rxId: string) => {
    sound.click();
    try {
      await api.post(`/clinic/prescriptions/${rxId}/dispense`, {});
      toast("success", "تم صرف الروشتة الطبية من الصيدلية بنجاح");
      queryClient.invalidateQueries({ queryKey: ["clinic-prescriptions"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر اعتماد صرف الروشتة على الخادم");
    }
  };

  const handleAdmitBed = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!admitBedTarget) return;
    sound.click();
    try {
      await api.post(`/clinic/beds/${admitBedTarget.id}/admit`, {
        patient_name: admitPatientName,
        admission_date: "2026-11-05",
      });
      toast("success", `تم تسكين المريض بالسرير ${admitBedTarget.bed_code}`);
      setAdmitBedTarget(null);
      setAdmitPatientName("");
      queryClient.invalidateQueries({ queryKey: ["clinic-beds"] });
      queryClient.invalidateQueries({ queryKey: ["clinic-summary"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر تسكين المريض على الخادم");
      setAdmitBedTarget(null);
    }
  };

  const handleDischargeBed = async (bedId: string) => {
    sound.click();
    try {
      await api.post(`/clinic/beds/${bedId}/discharge`, {});
      toast("success", "تم خروج المريض بنجاح واحتساب الفاتورة وتحويل السرير للتعقيم");
      queryClient.invalidateQueries({ queryKey: ["clinic-beds"] });
      queryClient.invalidateQueries({ queryKey: ["clinic-summary"] });
      queryClient.invalidateQueries({ queryKey: ["clinic-invoices"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر إخلاء السرير");
    }
  };

  const handleCleanBed = async (bedId: string) => {
    sound.click();
    try {
      await api.post(`/clinic/beds/${bedId}/clean`, {});
      toast("success", "تم اعتماد تعقيم السرير وجاهزيته للاستقبال");
      queryClient.invalidateQueries({ queryKey: ["clinic-beds"] });
      queryClient.invalidateQueries({ queryKey: ["clinic-summary"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر اعتماد تعقيم السرير على الخادم");
    }
  };

  const handleBillAppointment = async (apptId: string) => {
    sound.click();
    try {
      await api.post(`/clinic/appointments/${apptId}/bill`, {});
      toast("success", "تم إصدار فاتورة الكشف بنجاح");
      queryClient.invalidateQueries({ queryKey: ["clinic-invoices"] });
    } catch (e: any) {
      toast("error", e?.response?.data?.detail || e?.message || "تعذر إصدار الفاتورة");
    }
  };

  const handlePayInvoice = async (inv: ClinicInvoice) => {
    const amt = window.prompt(`المبلغ للدفع (المتبقي: ${inv.patient_amount - inv.paid_amount}):`, String(inv.patient_amount - inv.paid_amount));
    if (!amt) return;
    sound.click();
    try {
      await api.post(`/clinic/invoices/${inv.id}/pay`, { amount: parseFloat(amt), payment_method: "cash" });
      toast("success", "تم تسجيل الدفع بنجاح");
      queryClient.invalidateQueries({ queryKey: ["clinic-invoices"] });
    } catch (e: any) {
      toast("error", e?.response?.data?.detail || e?.message || "تعذر تسجيل الدفع");
    }
  };

  const handleRecordLabResult = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!labResultModalTarget) return;
    sound.click();
    try {
      await api.post(`/clinic/lab-orders/${labResultModalTarget.id}/result`, {
        result_value: labResultValue,
        is_signed_off: true,
      });
      toast("success", "تم اعتماد نتيجة التحليل الطبي وإرفاقها بملف المريض");
      setLabResultModalTarget(null);
      setLabResultValue("");
      queryClient.invalidateQueries({ queryKey: ["clinic-labs"] });
    } catch (err: any) {
      toast("error", err?.response?.data?.detail || err?.message || "تعذر اعتماد نتيجة التحليل على الخادم");
      setLabResultModalTarget(null);
    }
  };

  // Filtered lists by search
  const q = search.trim().toLowerCase();
  const filteredAppts = appointments.filter(
    (a) =>
      !q ||
      a.patient_name.toLowerCase().includes(q) ||
      a.doctor_name.toLowerCase().includes(q) ||
      a.appointment_ref.toLowerCase().includes(q)
  );

  const filteredPatients = patients.filter(
    (p) =>
      !q ||
      p.full_name.toLowerCase().includes(q) ||
      p.patient_mrn.toLowerCase().includes(q) ||
      p.phone.includes(q) ||
      p.national_id.includes(q)
  );

  const filteredEncounters = encounters.filter(
    (e) =>
      !q ||
      e.patient_name.toLowerCase().includes(q) ||
      e.doctor_name.toLowerCase().includes(q) ||
      e.chief_complaint.toLowerCase().includes(q) ||
      e.icd10_code.toLowerCase().includes(q)
  );

  const filteredRx = prescriptions.filter(
    (r) =>
      !q ||
      r.patient_name.toLowerCase().includes(q) ||
      r.medication_name.toLowerCase().includes(q) ||
      r.doctor_name.toLowerCase().includes(q)
  );

  const filteredLabs = labOrders.filter(
    (l) =>
      !q ||
      l.patient_name.toLowerCase().includes(q) ||
      l.test_name.toLowerCase().includes(q) ||
      l.specimen_barcode.toLowerCase().includes(q)
  );

  const ctx = {
    summaryData, isSummaryLoading, appointmentsData, patientsData, encountersData,
    prescriptionsData, labOrdersData, bedsData, invoicesData, claimsData,
    patients, appointments, encounters, prescriptions, labOrders, beds, summary,
    search, tab, handleTabChange, isBookingOpen, setIsBookingOpen,
    isPatientModalOpen, setIsPatientModalOpen, isEncounterModalOpen, setIsEncounterModalOpen,
    isRxModalOpen, setIsRxModalOpen, isLabModalOpen, setIsLabModalOpen,
    admitBedTarget, setAdmitBedTarget, admitPatientName, setAdmitPatientName,
    labResultModalTarget, setLabResultModalTarget, labResultValue, setLabResultValue,
    bookingForm, setBookingForm, patientForm, setPatientForm, encounterForm, setEncounterForm,
    rxForm, setRxForm, labForm, setLabForm,
    handleUpdateApptStatus, handleCreateAppointment, handleCreatePatient, handleCreateEncounter,
    handleCreatePrescription, handleCreateLabOrder, handleDispenseRx, handleAdmitBed,
    handleDischargeBed, handleCleanBed, handleRecordLabResult, handleBillAppointment, handlePayInvoice,
    filteredAppts, filteredPatients, filteredEncounters, filteredRx, filteredLabs,
    sound, moneyEGP, queryClient, toast, searchParams, setSearchParams, perms,
  };
  return (
    <ClinicProvider value={ctx}>
    <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto text-right" dir="rtl">
      {/* If a standalone healthcare module is active, render it directly full-width without duplicate headers */}
      {activeModuleKey && HEALTHCARE_MODULES_MAP[activeModuleKey] ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-border/60">
            <button
              onClick={() => handleSelectModule(null)}
              className="inline-flex items-center gap-2 text-xs font-semibold text-[#1E3A8A] hover:text-[#0A2540] bg-blue-50/80 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
            >
              ← العودة إلى دفتر العيادات السريعة
            </button>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-mono bg-muted/50 px-2.5 py-0.5 rounded-md">
                {HEALTHCARE_MODULES_MAP[activeModuleKey].code} • {HEALTHCARE_MODULES_MAP[activeModuleKey].title}
              </span>
            </div>
          </div>
          {HEALTHCARE_MODULES_MAP[activeModuleKey].preview && (
            <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-relaxed text-amber-900">
              <strong className="font-semibold">معاينة:</strong> هذه الشاشة تعرض بيانات توضيحية، والتعديلات عليها لا تُحفظ بعد.
              إدارة المنشآت والمباني والغرف الفعلية قيد التطوير.
            </div>
          )}
          <Suspense
            fallback={
              <div className="p-16 text-center text-muted-foreground bg-card border border-border rounded-2xl">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-[#1E3A8A]" />
                <p className="text-sm font-medium">جاري تحميل الوحدة الطبية المستقلة...</p>
                <p className="text-xs text-muted-foreground mt-1">تطبيق قواعد العزل الأمني والتكامل المؤسسي</p>
              </div>
            }
          >
            {React.createElement(HEALTHCARE_MODULES_MAP[activeModuleKey].component)}
          </Suspense>
        </div>
      ) : (
        <>
          {/* Editorial Masthead Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-border/80">
            <div>
              <div className="flex items-center gap-2">
                <span className="grid size-9 place-items-center rounded-xl bg-primary/10 text-primary border border-primary/20">
                  <Hospital className="size-5" />
                </span>
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground font-serif">
                  دفتر العيادات والمجمع الطبي التخصصي
                </h1>
                <Badge variant="outline" className="border-primary/30 text-primary bg-primary/5 text-xs font-mono">
                  سجل سريري نشط
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground mt-1">
                إدارة متكاملة للسجلات الطبية (EMR)، حجز المواعيد والكشوفات، الروشتات الإلكترونية (e-Rx)، والمختبرات وأسِرّة التنويم ومطالبات التأمين
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {perms.manage && (
              <Button
                onClick={() => {
                  sound.click();
                  setIsPatientModalOpen(true);
                }}
                variant="outline"
                className="border-primary/30 text-foreground hover:bg-primary/5 gap-1.5 h-9 text-xs font-semibold"
              >
                <UserPlus className="size-4 text-primary" />
                فتح ملف مريض جديد (EMR)
              </Button>
              )}

              {perms.book && (
              <Button
                onClick={() => {
                  sound.click();
                  setIsBookingOpen(true);
                }}
                className="bg-primary hover:bg-primary/90 text-primary-foreground gap-1.5 h-9 text-xs font-semibold shadow-xs"
              >
                <Calendar className="size-4" />
                حجز موعد كشف فوري
              </Button>
              )}
            </div>
          </div>

          {/* KPI Overview Cards - Warm Editorial Daily Ledger Metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <Card className="p-4 border-border/70 bg-card/80 shadow-xs hover:border-primary/40 transition-colors">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-medium">مواعيد وكشوفات اليوم</span>
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Calendar className="size-4" />
                </div>
              </div>
              <div className="mt-3">
                <div className="num text-2xl font-bold tracking-tight text-foreground">
                  {summary.today_appointments_count}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  <span className="num font-semibold text-primary">{summary.waiting_queue_count}</span> في صالة الانتظار
                </p>
              </div>
            </Card>

            <Card className="p-4 border-border/70 bg-card/80 shadow-xs hover:border-primary/40 transition-colors">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-medium">إشغال أسِرّة التنويم والأجنحة</span>
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Bed className="size-4" />
                </div>
              </div>
              <div className="mt-3">
                <div className="num text-2xl font-bold tracking-tight text-foreground">
                  {summary.bed_occupancy_percent}%
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  <span className="num font-semibold">{summary.occupied_beds}</span> شاغر من <span className="num font-semibold">{summary.total_beds}</span> سرير
                </p>
              </div>
            </Card>

            <Card className="p-4 border-border/70 bg-card/80 shadow-xs hover:border-primary/40 transition-colors">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-medium">سجلات المرضى النشطة (Master Index)</span>
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Users className="size-4" />
                </div>
              </div>
              <div className="mt-3">
                <div className="num text-2xl font-bold tracking-tight text-foreground">
                  {summary.total_registered_patients}
                </div>
                <p className="text-xs text-muted-foreground mt-1">ملف طبي إلكتروني معتمد</p>
              </div>
            </Card>

            <Card className="p-4 border-border/70 bg-card/80 shadow-xs hover:border-primary/40 transition-colors">
              <div className="flex items-center justify-between text-muted-foreground">
                <span className="text-xs font-medium">الفحوصات والتحاليل المعلقة</span>
                <div className="p-2 rounded-lg bg-primary/10 text-primary">
                  <Microscope className="size-4" />
                </div>
              </div>
              <div className="mt-3">
                <div className="num text-2xl font-bold tracking-tight text-foreground">
                  {summary.pending_lab_orders_count}
                </div>
                <p className="text-xs text-muted-foreground mt-1">بانتظار الاعتماد المخبري</p>
              </div>
            </Card>
          </div>

          {/* Enterprise Healthcare Suite Header & 24 Standalone Modules Navigator */}
          <div className="bg-card border border-border/80 rounded-2xl p-4 shadow-xs space-y-3">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-[#651E2C] text-[#FAF6F0]">
                  Mizan Healthcare ERP
                </span>
                <span className="text-xs text-muted-foreground font-medium">
                  مصفوفة الرعاية الصحية والمستشفيات (24 وحدة معتمدة HLT-01..24)
                </span>
              </div>

              <div className="flex items-center gap-1.5 flex-wrap">
                <button
                  onClick={() => handleSelectModule(null)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 cursor-pointer ${
                    !activeModuleKey
                      ? "bg-[#651E2C] text-[#FAF6F0] shadow-xs"
                      : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <Hospital className="w-3.5 h-3.5" />
                  العيادة السريعة اليومية
                </button>

                {["All", "Core", "Patients", "Clinical", "Hospital", "Diagnostics", "Revenue"].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-medium transition-colors ${
                      activeCategory === cat
                        ? "bg-[#651E2C]/10 text-[#651E2C] font-semibold"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted/40"
                    }`}
                  >
                    {cat === "All" ? "الكل (24)" : cat}
                  </button>
                ))}
              </div>
            </div>

            {/* 24 Modules Horizontal Drawer / Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 pt-0.5 scrollbar-thin">
              {Object.entries(HEALTHCARE_MODULES_MAP)
                .filter(([_, mod]) => activeCategory === "All" || mod.category === activeCategory)
                .map(([key, mod]) => {
                  const IconComp = mod.icon;
                  const isSelected = activeModuleKey === key;
                  return (
                    <button
                      key={key}
                      onClick={() => handleSelectModule(key)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-all border shrink-0 cursor-pointer ${
                        isSelected
                          ? "bg-[#651E2C] text-[#FAF6F0] border-[#651E2C] shadow-xs font-semibold"
                          : "bg-card border-border/70 text-muted-foreground hover:border-[#651E2C]/40 hover:text-foreground hover:bg-muted/30"
                      }`}
                    >
                      <IconComp className="w-3.5 h-3.5" />
                      <span className="font-mono text-[10px] opacity-75">{mod.code}</span>
                      <span>{mod.title}</span>
                      {mod.preview && (
                        <span className="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">معاينة</span>
                      )}
                    </button>
                  );
                })}
            </div>
          </div>

      {/* Main Content Area - Ledger Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/70 pb-1">
            <div className="flex flex-wrap items-center gap-1">
              <button
                onClick={() => handleTabChange("appointments")}
                className={`px-3.5 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "appointments"
                    ? "border-primary text-primary bg-primary/[0.06] rounded-t-lg font-bold"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40 rounded-t-lg"
                }`}
              >
                <Calendar className="size-3.5" />
                الكشوفات والانتظار (<span className="num">{appointments.length}</span>)
              </button>

              <button
                onClick={() => handleTabChange("patients")}
                className={`px-3.5 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "patients"
                    ? "border-primary text-primary bg-primary/[0.06] rounded-t-lg font-bold"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40 rounded-t-lg"
                }`}
              >
                <Users className="size-3.5" />
                سجلات المرضى (EMR) (<span className="num">{patients.length}</span>)
              </button>

              <button
                onClick={() => handleTabChange("emr")}
                className={`px-3.5 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "emr"
                    ? "border-primary text-primary bg-primary/[0.06] rounded-t-lg font-bold"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40 rounded-t-lg"
                }`}
              >
                <HeartPulse className="size-3.5" />
                الكشوفات السريرية (<span className="num">{encounters.length}</span>)
              </button>

              <button
                onClick={() => handleTabChange("rx_labs")}
                className={`px-3.5 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "rx_labs"
                    ? "border-primary text-primary bg-primary/[0.06] rounded-t-lg font-bold"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40 rounded-t-lg"
                }`}
              >
                <Pill className="size-3.5" />
                الروشتات والتحاليل (<span className="num">{prescriptions.length + labOrders.length}</span>)
              </button>

              <button
                onClick={() => handleTabChange("beds")}
                className={`px-3.5 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "beds"
                    ? "border-primary text-primary bg-primary/[0.06] rounded-t-lg font-bold"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40 rounded-t-lg"
                }`}
              >
                <Bed className="size-3.5" />
                أسرّة التنويم (<span className="num">{beds.length}</span>)
              </button>

              {perms.billing && (
              <button
                onClick={() => handleTabChange("billing")}
                className={`px-3.5 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "billing"
                    ? "border-primary text-primary bg-primary/[0.06] rounded-t-lg font-bold"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40 rounded-t-lg"
                }`}
              >
                <FileText className="size-3.5" />
                الفواتير والتحصيل (<span className="num">{invoicesData.length}</span>)
              </button>
              )}

              {canPrivacy && (
                <button
                  onClick={() => handleTabChange("privacy")}
                  className={`px-3.5 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                    tab === "privacy"
                      ? "border-primary text-primary bg-primary/[0.06] rounded-t-lg font-bold"
                      : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40 rounded-t-lg"
                  }`}
                >
                  <Lock className="size-3.5" />
                  الخصوصية والوصول
                </button>
              )}

              {perms.billing && (
              <button
                onClick={() => handleTabChange("claims")}
                className={`px-3.5 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5 cursor-pointer ${
                  tab === "claims"
                    ? "border-primary text-primary bg-primary/[0.06] rounded-t-lg font-bold"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40 rounded-t-lg"
                }`}
              >
                <ShieldCheck className="size-3.5" />
                مطالبات التأمين (<span className="num">{claimsData.length}</span>)
              </button>
              )}
            </div>

            <div className="relative w-full sm:w-64">
              <Search className="size-4 absolute right-3 top-2.5 text-muted-foreground" />
              <Input
                placeholder="بحث بالمريض، الطبيب، أو الكود..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pr-9 h-9 text-xs"
              />
            </div>
          </div>

          {tab === "appointments" && <AppointmentsTab />}
          {tab === "patients" && <PatientsTab />}
          {tab === "emr" && <EMRTab />}
          {tab === "rx_labs" && <RxLabsTab />}
          {tab === "beds" && <BedsTab />}
          {tab === "billing" && <BillingTab />}
          {tab === "claims" && <ClaimsTab />}
          {tab === "privacy" && <PrivacyTab />}
        </>
      )}

      {/* ── Modal: Register Patient ────────────────────────────────────────── */}
      {isPatientModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <Card className="w-full max-w-lg p-6 bg-card border-border shadow-2xl relative text-right max-h-[90vh] overflow-y-auto" dir="rtl">
            <button
              onClick={() => setIsPatientModalOpen(false)}
              className="absolute left-4 top-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <X className="w-4 h-4" />
            </button>
            <h3 className="text-base font-bold text-foreground mb-4 flex items-center gap-2">
              <UserPlus className="size-5 text-primary" />
              تسجيل ملف مريض جديد (Master Patient Index)
            </h3>
            <form onSubmit={handleCreatePatient} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-muted-foreground mb-1">الاسم الرباعي للمريض *</label>
                <Input
                  required
                  placeholder="مثال: يوسف حسام الدين كمال"
                  value={patientForm.full_name}
                  onChange={(e) => setPatientForm({ ...patientForm, full_name: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted-foreground mb-1">الرقم القومي (14 رقم) *</label>
                  <Input
                    required
                    placeholder="29801010101234"
                    value={patientForm.national_id}
                    onChange={(e) => setPatientForm({ ...patientForm, national_id: e.target.value })}
                    className="h-9 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">رقم الهاتف للتواصل *</label>
                  <Input
                    required
                    placeholder="01012345678"
                    value={patientForm.phone}
                    onChange={(e) => setPatientForm({ ...patientForm, phone: e.target.value })}
                    className="h-9 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-muted-foreground mb-1">النوع</label>
                  <select
                    value={patientForm.gender}
                    onChange={(e) => setPatientForm({ ...patientForm, gender: e.target.value })}
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs"
                  >
                    <option value="ذكر">ذكر</option>
                    <option value="أنثى">أنثى</option>
                  </select>
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">تاريخ الميلاد</label>
                  <Input
                    type="date"
                    value={patientForm.date_of_birth}
                    onChange={(e) => setPatientForm({ ...patientForm, date_of_birth: e.target.value })}
                    className="h-9 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">فصيلة الدم</label>
                  <select
                    value={patientForm.blood_group}
                    onChange={(e) => setPatientForm({ ...patientForm, blood_group: e.target.value })}
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs font-mono"
                  >
                    {["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"].map((bg) => (
                      <option key={bg} value={bg}>{bg}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-muted-foreground mb-1">الحساسيات الدوائية والغذائية</label>
                <Input
                  placeholder="مثال: حساسية البنسلين، حساسية السلفا..."
                  value={patientForm.allergies}
                  onChange={(e) => setPatientForm({ ...patientForm, allergies: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div>
                <label className="block text-muted-foreground mb-1">الأمراض المزمنة والتاريخ المرضي</label>
                <Input
                  placeholder="مثال: سكري، ضغط، ربو..."
                  value={patientForm.chronic_conditions}
                  onChange={(e) => setPatientForm({ ...patientForm, chronic_conditions: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="block text-muted-foreground mb-1">الجهة الضامنة / التأمين الطبي</label>
                  <Input
                    placeholder="بوبا / أكسا / نقدي"
                    value={patientForm.insurance_provider}
                    onChange={(e) => setPatientForm({ ...patientForm, insurance_provider: e.target.value })}
                    className="h-9 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">نسبة التحمل %</label>
                  <Input
                    type="number"
                    value={patientForm.copay_percent}
                    onChange={(e) => setPatientForm({ ...patientForm, copay_percent: e.target.value })}
                    className="h-9 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/40">
                <Button type="button" variant="outline" onClick={() => setIsPatientModalOpen(false)} className="h-8 text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="h-8 text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-xs">
                  تسجيل الملف الطبي
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* ── Modal: Book Appointment ────────────────────────────────────────── */}
      {isBookingOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <Card className="w-full max-w-lg p-6 bg-card border-border shadow-2xl relative text-right" dir="rtl">
            <button
              onClick={() => setIsBookingOpen(false)}
              className="absolute left-4 top-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <X className="w-4 h-4" />
            </button>
            <h3 className="text-base font-bold text-foreground mb-4 flex items-center gap-2">
              <Calendar className="size-5 text-primary" />
              حجز موعد كشف واستشارة طبية
            </h3>
            <form onSubmit={handleCreateAppointment} className="space-y-3.5 text-xs">
              <div>
                <label htmlFor="booking-patient" className="block text-muted-foreground mb-1">المريض *</label>
                <select
                  id="booking-patient"
                  required
                  value={bookingForm.patient_id}
                  onChange={(e) => {
                    const p = patients.find((x) => x.id === e.target.value);
                    setBookingForm({ ...bookingForm, patient_id: e.target.value, patient_name: p?.full_name || "" });
                  }}
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs"
                >
                  <option value="">اختر ملف المريض</option>
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>{p.full_name} — {p.patient_mrn}</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted-foreground mb-1">العيادة / التخصص *</label>
                  <Input
                    required
                    value={bookingForm.department}
                    onChange={(e) => setBookingForm({ ...bookingForm, department: e.target.value })}
                    className="h-9 text-xs"
                  />
                </div>
                <div>
                  <label htmlFor="booking-doctor" className="block text-muted-foreground mb-1">الطبيب المعالج *</label>
                  <select
                    id="booking-doctor"
                    required
                    value={bookingForm.doctor_user_id}
                    onChange={(e) => setBookingForm({ ...bookingForm, doctor_user_id: e.target.value })}
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs"
                  >
                    <option value="">{cliniciansData.length ? "اختر الطبيب" : "لا يوجد أطباء مسجلون كمستخدمين"}</option>
                    {cliniciansData.map((d) => (
                      <option key={d.id} value={d.id}>{d.full_name}{d.role ? ` — ${d.role}` : ""}</option>
                    ))}
                  </select>
                  <p className="text-[10px] text-muted-foreground mt-1">يُضاف الطبيب إلى فريق رعاية المريض</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted-foreground mb-1">تاريخ الكشف</label>
                  <Input
                    type="date"
                    value={bookingForm.appointment_date}
                    onChange={(e) => setBookingForm({ ...bookingForm, appointment_date: e.target.value })}
                    className="h-9 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">التوقيت</label>
                  <Input
                    value={bookingForm.time_slot}
                    onChange={(e) => setBookingForm({ ...bookingForm, time_slot: e.target.value })}
                    className="h-9 text-xs font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-muted-foreground mb-1">أتعاب الكشف (ج.م)</label>
                <Input
                  type="number"
                  value={bookingForm.consultation_fee}
                  onChange={(e) => setBookingForm({ ...bookingForm, consultation_fee: e.target.value })}
                  className="h-9 text-xs font-mono"
                />
              </div>

              <div>
                <label className="block text-muted-foreground mb-1">الشكوى الأولية والأعراض</label>
                <Input
                  placeholder="مثال: متابعة السكر وضغط الدم"
                  value={bookingForm.chief_complaint}
                  onChange={(e) => setBookingForm({ ...bookingForm, chief_complaint: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/40">
                <Button type="button" variant="outline" onClick={() => setIsBookingOpen(false)} className="h-8 text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="h-8 text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-xs">
                  تأكيد الحجز وقيد الانتظار
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* ── Modal: Clinical Encounter ──────────────────────────────────────── */}
      {isEncounterModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <Card className="w-full max-w-lg p-6 bg-card border-border shadow-2xl relative text-right max-h-[90vh] overflow-y-auto" dir="rtl">
            <button
              onClick={() => setIsEncounterModalOpen(false)}
              className="absolute left-4 top-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <X className="w-4 h-4" />
            </button>
            <h3 className="text-base font-bold text-foreground mb-4 flex items-center gap-2">
              <HeartPulse className="size-5 text-primary" />
              توثيق كشف سريري وتشخيص طبي (EMR)
            </h3>
            <form onSubmit={handleCreateEncounter} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-muted-foreground mb-1">اسم المريض *</label>
                <Input
                  required
                  placeholder="مثال: طارق عبد الحميد محمود"
                  value={encounterForm.patient_name}
                  onChange={(e) => setEncounterForm({ ...encounterForm, patient_name: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted-foreground mb-1">الطبيب الفاحص *</label>
                  <Input
                    required
                    value={encounterForm.doctor_name}
                    onChange={(e) => setEncounterForm({ ...encounterForm, doctor_name: e.target.value })}
                    className="h-9 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">العيادة</label>
                  <Input
                    value={encounterForm.department}
                    onChange={(e) => setEncounterForm({ ...encounterForm, department: e.target.value })}
                    className="h-9 text-xs"
                  />
                </div>
              </div>

              {/* Vitals Form */}
              <div className="grid grid-cols-4 gap-2 p-2.5 rounded-lg bg-muted/20 border border-border/30">
                <div>
                  <label className="block text-muted-foreground text-[10px] mb-1">ضغط الدم الانقباضي</label>
                  <Input
                    placeholder="120"
                    value={encounterForm.bp_systolic}
                    onChange={(e) => setEncounterForm({ ...encounterForm, bp_systolic: e.target.value })}
                    className="h-8 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground text-[10px] mb-1">الانبساطي</label>
                  <Input
                    placeholder="80"
                    value={encounterForm.bp_diastolic}
                    onChange={(e) => setEncounterForm({ ...encounterForm, bp_diastolic: e.target.value })}
                    className="h-8 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground text-[10px] mb-1">النبض HR</label>
                  <Input
                    placeholder="75"
                    value={encounterForm.heart_rate}
                    onChange={(e) => setEncounterForm({ ...encounterForm, heart_rate: e.target.value })}
                    className="h-8 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground text-[10px] mb-1">الأكسجين SpO2</label>
                  <Input
                    placeholder="99"
                    value={encounterForm.spo2}
                    onChange={(e) => setEncounterForm({ ...encounterForm, spo2: e.target.value })}
                    className="h-8 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted-foreground mb-1">كود التشخيص الدولي (ICD-10)</label>
                  <Input
                    value={encounterForm.icd10_code}
                    onChange={(e) => setEncounterForm({ ...encounterForm, icd10_code: e.target.value })}
                    className="h-9 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">وصف التشخيص</label>
                  <Input
                    value={encounterForm.icd10_description}
                    onChange={(e) => setEncounterForm({ ...encounterForm, icd10_description: e.target.value })}
                    className="h-9 text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-muted-foreground mb-1">الشكوى المرضية</label>
                <Input
                  value={encounterForm.chief_complaint}
                  onChange={(e) => setEncounterForm({ ...encounterForm, chief_complaint: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div>
                <label className="block text-muted-foreground mb-1">الملاحظات السريرية وخطة العلاج</label>
                <textarea
                  rows={3}
                  value={encounterForm.clinical_notes}
                  onChange={(e) => setEncounterForm({ ...encounterForm, clinical_notes: e.target.value })}
                  className="w-full rounded-md border border-input bg-background p-2.5 text-xs"
                  placeholder="تدوين فحص الطبيب والتوصيات وخطة المتابعة..."
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/40">
                <Button type="button" variant="outline" onClick={() => setIsEncounterModalOpen(false)} className="h-8 text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="h-8 text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-xs">
                  حفظ الكشف الطبي
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* ── Modal: Issue Prescription ──────────────────────────────────────── */}
      {isRxModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <Card className="w-full max-w-md p-6 bg-card border-border shadow-2xl relative text-right" dir="rtl">
            <button
              onClick={() => setIsRxModalOpen(false)}
              className="absolute left-4 top-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <X className="w-4 h-4" />
            </button>
            <h3 className="text-base font-bold text-foreground mb-4 flex items-center gap-2">
              <Pill className="size-5 text-primary" />
              إصدار روشتة طبية رقمية (e-Prescription)
            </h3>
            <form onSubmit={handleCreatePrescription} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-muted-foreground mb-1">اسم المريض *</label>
                <Input
                  required
                  placeholder="مثال: فاطمة الزهراء علي"
                  value={rxForm.patient_name}
                  onChange={(e) => setRxForm({ ...rxForm, patient_name: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div>
                <label className="block text-muted-foreground mb-1">اسم الدواء والمادة الفعالة *</label>
                <Input
                  required
                  placeholder="مثال: أوجمنتين 1 جم (Augmentin 1g)"
                  value={rxForm.medication_name}
                  onChange={(e) => setRxForm({ ...rxForm, medication_name: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-muted-foreground mb-1">الجرعة</label>
                  <Input
                    value={rxForm.dosage}
                    onChange={(e) => setRxForm({ ...rxForm, dosage: e.target.value })}
                    className="h-9 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">التكرار</label>
                  <Input
                    value={rxForm.frequency}
                    onChange={(e) => setRxForm({ ...rxForm, frequency: e.target.value })}
                    className="h-9 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">المدة (أيام)</label>
                  <Input
                    type="number"
                    value={rxForm.duration_days}
                    onChange={(e) => setRxForm({ ...rxForm, duration_days: e.target.value })}
                    className="h-9 text-xs font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-muted-foreground mb-1">تعليمات الصيدلي والمريض</label>
                <Input
                  value={rxForm.instructions}
                  onChange={(e) => setRxForm({ ...rxForm, instructions: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/40">
                <Button type="button" variant="outline" onClick={() => setIsRxModalOpen(false)} className="h-8 text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="h-8 text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-xs">
                  إصدار وإرسال للصيدلية
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* ── Modal: Order Lab Test ──────────────────────────────────────────── */}
      {isLabModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <Card className="w-full max-w-md p-6 bg-card border-border shadow-2xl relative text-right" dir="rtl">
            <button
              onClick={() => setIsLabModalOpen(false)}
              className="absolute left-4 top-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <X className="w-4 h-4" />
            </button>
            <h3 className="text-base font-bold text-foreground mb-4 flex items-center gap-2">
              <Microscope className="w-5 h-5 text-purple-400" />
              طلب فحص مخبري أو تصوير طبي
            </h3>
            <form onSubmit={handleCreateLabOrder} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-muted-foreground mb-1">اسم المريض *</label>
                <Input
                  required
                  placeholder="مثال: طارق عبد الحميد"
                  value={labForm.patient_name}
                  onChange={(e) => setLabForm({ ...labForm, patient_name: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div>
                <label className="block text-muted-foreground mb-1">اسم الفحص أو التحليل *</label>
                <Input
                  required
                  placeholder="مثال: وظائف كبد كاملة (Liver Function Tests)"
                  value={labForm.test_name}
                  onChange={(e) => setLabForm({ ...labForm, test_name: e.target.value })}
                  className="h-9 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-muted-foreground mb-1">القسم المخبري</label>
                  <select
                    value={labForm.category}
                    onChange={(e) => setLabForm({ ...labForm, category: e.target.value })}
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-xs"
                  >
                    <option value="كيمياء حيوية سريرية">كيمياء حيوية سريرية</option>
                    <option value="أمراض الدم (Hematology)">أمراض الدم</option>
                    <option value="الأشعة والتصوير الطبي">الأشعة والتصوير</option>
                    <option value="مناعة ومصليات (Serology)">مناعة ومصليات</option>
                    <option value="علم الأمراض والأنسجة">علم الأمراض والأنسجة</option>
                  </select>
                </div>
                <div>
                  <label className="block text-muted-foreground mb-1">باركود العينة</label>
                  <Input
                    value={labForm.specimen_barcode}
                    onChange={(e) => setLabForm({ ...labForm, specimen_barcode: e.target.value })}
                    className="h-9 text-xs font-mono"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/40">
                <Button type="button" variant="outline" onClick={() => setIsLabModalOpen(false)} className="h-8 text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="h-8 text-xs bg-purple-600 hover:bg-purple-500 text-white font-semibold">
                  إرسال أمر الفحص
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* ── Modal: Admit Bed ──────────────────────────────────────────────── */}
      {admitBedTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <Card className="w-full max-w-md p-6 bg-card border-border shadow-2xl relative text-right" dir="rtl">
            <button
              onClick={() => setAdmitBedTarget(null)}
              className="absolute left-4 top-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <X className="w-4 h-4" />
            </button>
            <h3 className="text-base font-bold text-foreground mb-1 flex items-center gap-2">
              <Bed className="size-5 text-primary" />
              تسكين مريض بالسرير: {admitBedTarget.bed_code}
            </h3>
            <p className="text-xs text-muted-foreground mb-4 font-mono">
              {admitBedTarget.ward_name} — {admitBedTarget.room_number} ({moneyEGP(admitBedTarget.daily_rate)} / اليوم)
            </p>
            <form onSubmit={handleAdmitBed} className="space-y-4 text-xs">
              <div>
                <label className="block text-muted-foreground mb-1">اسم المريض المراد تسكينه *</label>
                <Input
                  required
                  placeholder="مثال: محمود صبري حسن"
                  value={admitPatientName}
                  onChange={(e) => setAdmitPatientName(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/40">
                <Button type="button" variant="outline" onClick={() => setAdmitBedTarget(null)} className="h-8 text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="h-8 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-semibold">
                  اعتماد التسكين
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* ── Modal: Record Lab Result ───────────────────────────────────────── */}
      {labResultModalTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <Card className="w-full max-w-md p-6 bg-card border-border shadow-2xl relative text-right" dir="rtl">
            <button
              onClick={() => setLabResultModalTarget(null)}
              className="absolute left-4 top-4 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <X className="w-4 h-4" />
            </button>
            <h3 className="text-base font-bold text-foreground mb-1 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-purple-400" />
              اعتماد نتيجة الفحص المخبري
            </h3>
            <p className="text-xs text-muted-foreground mb-3 font-mono">
              {labResultModalTarget.test_name} — المريض: {labResultModalTarget.patient_name}
            </p>
            <form onSubmit={handleRecordLabResult} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-muted-foreground mb-1">النتيجة المخبرية المقروءة *</label>
                <Input
                  required
                  placeholder="مثال: 11.5 g/dL (طبيعي) أو سليم"
                  value={labResultValue}
                  onChange={(e) => setLabResultValue(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/40">
                <Button type="button" variant="outline" onClick={() => setLabResultModalTarget(null)} className="h-8 text-xs">
                  إلغاء
                </Button>
                <Button type="submit" className="h-8 text-xs bg-purple-600 hover:bg-purple-500 text-white font-semibold">
                  اعتماد النتيجة بملف المريض
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
    </ClinicProvider>
  );
}
