import { lazy, type ComponentType, type LazyExoticComponent } from "react";
import { Activity, BarChart3, Bed, Bell, Briefcase, Building2, Calculator, Calendar, DoorOpen, FileText, Flame, FlaskConical, HeartPulse, Laptop, Package, Pill, Scan, Scissors, ShieldCheck, Stethoscope, UserCheck, Users, Video, type LucideIcon } from "lucide-react";

export interface HealthcareModule {
  code: string;
  title: string;
  category: string;
  icon: LucideIcon;
  component: LazyExoticComponent<ComponentType>;
  preview?: boolean;
}

export const HEALTHCARE_CATEGORIES = ["All", "Core", "Patients", "Clinical", "Hospital", "Diagnostics", "Revenue"];

// Standalone 24 Healthcare ERP Modules (HLT-01..24)
// preview: the screen runs on sample data and isn't wired to the API yet; it says so (#47).
export const HEALTHCARE_MODULES_MAP: Record<string, HealthcareModule> = {
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
  access_control: { code: "SEC-01", title: "المستخدمون والأدوار والمسميات", category: "Core", icon: ShieldCheck, component: lazy(() => import("@app/platform/core/screens/UsersPage")) },
};
