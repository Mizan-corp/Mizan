import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { sound } from "@/lib/sound";
import { ClinicProvider, type ClinicContextValue, type ClinicDialog } from "./ClinicContext";
import { HEALTHCARE_MODULES_MAP } from "./healthcareModules";
import { useClinicPerms } from "./permissions";
import { useClinicActions } from "./useClinicActions";
import { useClinicData } from "./useClinicData";
import type { ClinicTab } from "./types";
import ClinicDialogs from "./components/ClinicDialogs";
import ClinicHeader from "./components/ClinicHeader";
import ClinicKpis from "./components/ClinicKpis";
import ClinicTabsBar from "./components/ClinicTabsBar";
import HealthcareSuiteNav from "./components/HealthcareSuiteNav";
import StandaloneModuleView from "./components/StandaloneModuleView";
import AppointmentsTab from "./tabs/AppointmentsTab";
import BedsTab from "./tabs/BedsTab";
import BillingTab from "./tabs/BillingTab";
import ClaimsTab from "./tabs/ClaimsTab";
import EMRTab from "./tabs/EMRTab";
import PatientsTab from "./tabs/PatientsTab";
import PrivacyTab from "./tabs/PrivacyTab";
import RxLabsTab from "./tabs/RxLabsTab";

const TAB_VIEWS: Record<ClinicTab, () => React.JSX.Element> = {
  appointments: AppointmentsTab,
  patients: PatientsTab,
  emr: EMRTab,
  rx_labs: RxLabsTab,
  beds: BedsTab,
  billing: BillingTab,
  claims: ClaimsTab,
  privacy: PrivacyTab,
};

const includes = (value: string | null | undefined, q: string) => (value ?? "").toLowerCase().includes(q);

// The clinic: routing (?tab=, /clinic/:moduleSlug), the acting role's permissions, data and dialogs.
// Each tab, dialog and part of the page lives in tabs/ and components/.
export default function ClinicHealthcarePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { moduleSlug } = useParams<{ moduleSlug?: string }>();
  const navigate = useNavigate();
  const perms = useClinicPerms();
  const data = useClinicData(perms);
  const actions = useClinicActions();
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState<ClinicDialog>(null);
  const [activeCategory, setActiveCategory] = useState("All");

  const tabParam = searchParams.get("tab");
  const activeModuleKey = moduleSlug || (tabParam && HEALTHCARE_MODULES_MAP[tabParam] ? tabParam : null);
  const validTabs = ["appointments", "patients", "emr", "rx_labs", "labs", "beds",
    ...(perms.billing ? ["billing", "claims"] : []), ...(perms.privacy ? ["privacy"] : [])];
  const tab: ClinicTab = tabParam && validTabs.includes(tabParam)
    ? (tabParam === "labs" ? "rx_labs" : (tabParam as ClinicTab))
    : "appointments";

  const handleTabChange = (newTab: string) => {
    sound.click();
    if (moduleSlug) navigate(`/clinic?tab=${newTab}`);
    else setSearchParams({ tab: newTab });
  };

  const handleSelectModule = (modKey: string | null) => {
    sound.click();
    if (!modKey) {
      if (moduleSlug) navigate("/clinic");
      else setSearchParams({ tab: "appointments" });
    } else if (moduleSlug) navigate(`/clinic/${modKey}`);
    else setSearchParams({ tab: modKey });
  };

  const q = search.trim().toLowerCase();
  const ctx: ClinicContextValue = {
    perms, data, actions, tab, handleTabChange, search,
    openDialog: setDialog,
    filteredAppts: data.appointments.filter((a) =>
      !q || includes(a.patient_name, q) || includes(a.doctor_name, q) || includes(a.appointment_ref, q)),
    filteredPatients: data.patients.filter((p) =>
      !q || includes(p.full_name, q) || includes(p.patient_mrn, q) || includes(p.phone, q) || includes(p.national_id, q)),
    filteredEncounters: data.encounters.filter((e) =>
      !q || includes(e.patient_name, q) || includes(e.doctor_name, q) || includes(e.chief_complaint, q) || includes(e.icd10_code, q)),
    filteredRx: data.prescriptions.filter((r) =>
      !q || includes(r.patient_name, q) || includes(r.medication_name, q) || includes(r.doctor_name, q)),
    filteredLabs: data.labOrders.filter((l) =>
      !q || includes(l.patient_name, q) || includes(l.test_name, q) || includes(l.specimen_barcode, q)),
  };
  const TabView = TAB_VIEWS[tab];
  const standalone = activeModuleKey ? HEALTHCARE_MODULES_MAP[activeModuleKey] : undefined;

  return (
    <ClinicProvider value={ctx}>
      <div className="p-4 sm:p-6 space-y-6 max-w-7xl mx-auto text-right" dir="rtl">
        {standalone ? (
          <StandaloneModuleView module={standalone} onBack={() => handleSelectModule(null)} />
        ) : (
          <>
            <ClinicHeader />
            <ClinicKpis />
            <HealthcareSuiteNav activeModuleKey={activeModuleKey} onSelect={handleSelectModule}
              activeCategory={activeCategory} onCategoryChange={setActiveCategory} />
            <ClinicTabsBar onSearch={setSearch} />
            <TabView />
          </>
        )}
        <ClinicDialogs dialog={dialog} onClose={() => setDialog(null)} />
      </div>
    </ClinicProvider>
  );
}
