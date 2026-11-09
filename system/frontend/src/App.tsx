import { lazy, Suspense } from "react";
const DashboardPage = lazy(() => import("@app/features/dashboard/DashboardPage"));
const PosPage = lazy(() => import("@modules/pos/PosPage"));
const ProductsPage = lazy(() => import("@app/features/products/ProductsPage"));
const SalesPage = lazy(() => import("@modules/sales/SalesPage"));
const PurchasesPage = lazy(() => import("@modules/purchases/PurchasesPage"));
const PayrollPage = lazy(() => import("@modules/hr/PayrollPage"));
const ShiftsPage = lazy(() => import("@app/features/shifts/ShiftsPage"));
const CustomersPage = lazy(() => import("@app/features/customers/CustomersPage"));
const SettingsPage = lazy(() => import("@app/features/settings/SettingsPage"));
const FinancePage = lazy(() => import("@modules/finance/FinancePage"));
const SuppliersPage = lazy(() => import("@app/features/suppliers/SuppliersPage"));
const UsersPage = lazy(() => import("@app/features/users/UsersPage"));
const HrPage = lazy(() => import("@modules/hr/HrPage"));
const InventoryPage = lazy(() => import("@modules/inventory/InventoryPage"));
const ReportsPage = lazy(() => import("@app/features/reports/ReportsPage"));
const ArchivePage = lazy(() => import("@app/features/archive/ArchivePage"));
const OperationsPage = lazy(() => import("@app/features/operations/OperationsPage"));
const ModulesPage = lazy(() => import("@app/features/modules/ModulesPage"));
const RestaurantTablesPage = lazy(() => import("@modules/restaurant/RestaurantTablesPage"));
const KitchenDisplayPage = lazy(() => import("@modules/restaurant/KitchenDisplayPage"));
const SchoolStudentsPage = lazy(() => import("@modules/school/SchoolStudentsPage"));
const PharmacyPage = lazy(() => import("@modules/pharmacy/PharmacyPage"));
const ServicesConsultingPage = lazy(() => import("@modules/services/ServicesConsultingPage"));
const WholesaleDistributionPage = lazy(() => import("@modules/wholesale/WholesaleDistributionPage"));
const LogisticsFleetPage = lazy(() => import("@modules/logistics/LogisticsFleetPage"));
const WmsWarehousePage = lazy(() => import("@modules/wms/WmsWarehousePage"));
const EcommerceHubPage = lazy(() => import("@modules/ecommerce/EcommerceHubPage"));
const ClinicHealthcarePage = lazy(() => import("@modules/healthcare_clinic/ClinicHealthcarePage"));
const WhatsAppGatewayPage = lazy(() => import("@modules/whatsapp_gateway/WhatsAppGatewayPage"));
const LawPracticePage = lazy(() => import("@modules/law/LawPracticePage"));
const TravelTourismPage = lazy(() => import("@modules/travel/TravelTourismPage"));
const HospitalityPmsPage = lazy(() => import("@modules/hospitality/HospitalityPmsPage"));
const GymFitnessPage = lazy(() => import("@modules/gym/GymFitnessPage"));
const SalonSpaPage = lazy(() => import("@modules/salon/SalonSpaPage"));
const CreativeAgencyPage = lazy(() => import("@modules/agency/CreativeAgencyPage"));
const FieldServicePage = lazy(() => import("@modules/field_service/FieldServicePage"));
const DiscreteManufacturingPage = lazy(() => import("@modules/mfg/DiscreteManufacturingPage"));
const FoodProcessingPage = lazy(() => import("@modules/fod/FoodProcessingPage"));
const PharmaGmpPage = lazy(() => import("@modules/phm/PharmaGmpPage"));
const PrintingPackagingPage = lazy(() => import("@modules/prn/PrintingPackagingPage"));
const ConstructionPage = lazy(() => import("@modules/cst/ConstructionPage"));
const RealEstatePage = lazy(() => import("@modules/rec/RealEstatePage"));
const AgricultureFarmPage = lazy(() => import("@modules/agr/AgricultureFarmPage"));
const EnergyPowerPlantPage = lazy(() => import("@modules/eng/EnergyPowerPlantPage"));
const BankingPage = lazy(() => import("@modules/bnk/BankingPage"));
const InsurancePage = lazy(() => import("@modules/ins/InsurancePage"));
const GovernmentPage = lazy(() => import("@modules/gov/GovernmentPage"));
const EntertainmentPage = lazy(() => import("@modules/ent/EntertainmentPage"));
const OilGasPage = lazy(() => import("@modules/oil/OilGasPage"));
const StorefrontAdminPage = lazy(() => import("@modules/storefront/StorefrontAdminPage"));
const PublicStorefrontPage = lazy(() => import("@modules/storefront/public/PublicStorefrontPage"));
const TenantScopeLayout = lazy(() => import("@app/features/tenant/TenantScopeLayout"));



import { Link, Navigate, Route, Routes } from "react-router-dom";
import PricingPage from "@/features/billing/PricingPage";
import { Lock } from "lucide-react";
import { useAuth } from "@/stores/auth";

function WorkspaceHome() {
  const token = useAuth((s) => s.token);
  const user = useAuth((s) => s.user);
  const tenant = useAuth((s) => s.tenant);
  if (token && user) {
    const slug = tenant?.slug;
    if (slug && slug !== "undefined" && slug !== "null") {
      return <Navigate to={`/c/${slug}`} replace />;
    }
    return <Navigate to="/dashboard" replace />;
  }
  return <Navigate to="/login" replace />;
}
import { useModulesStore } from "@app/stores/modules";
import { NAV_ITEMS } from "@app/lib/nav";
import { useTenantNav } from "@app/lib/tenant";
import { Button } from "@/components/kit/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/kit/empty";
import Shell from "@app/components/AppShell";
import LoginPage from "@app/features/auth/LoginPage";
import { IS_ON_PREMISE } from "@app/lib/deployment";

function Page({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="grid place-items-center p-16"><span className="h-6 w-6 animate-spin rounded-full border-2 border-brand border-t-transparent" /></div>}>{children}</Suspense>;
}

function Guard({ perm, module, children }: { perm: string; module?: string; children: React.ReactNode }) {
  const { token, user, can } = useAuth();
  const hasModule = useModulesStore((s) => s.hasModule);
  const { tenantTo } = useTenantNav();

  if (!token || !user) return <Navigate to={tenantTo("/login")} replace />;
  if (module && !hasModule(module)) {
    return (
      <Empty className="mx-auto mt-16 max-w-md border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Lock />
          </EmptyMedia>
          <EmptyTitle>الوحدة غير مفعّلة في منشأتك</EmptyTitle>
          <EmptyDescription>
            هذه الشاشة تتطلب تفعيل وحدة متخصصة لمجال عملك. يمكنك تفعيلها فوراً بنقرة واحدة من مركز الوحدات والتطبيقات.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button nativeButton={false} render={<Link to={tenantTo("/modules")} />}>
            الانتقال إلى مركز الوحدات والتطبيقات
          </Button>
        </EmptyContent>
      </Empty>
    );
  }
  if (perm && !can(perm)) {
    const fallback = NAV_ITEMS.find((n) => (!n.perm || can(n.perm)) && (!n.module || hasModule(n.module)));
    return (
      <Empty className="mx-auto mt-16 max-w-md border border-dashed">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Lock />
          </EmptyMedia>
          <EmptyTitle>لا تملك صلاحية الوصول</EmptyTitle>
          <EmptyDescription>
            دورك الحالي لا يتضمن هذه الشاشة. تواصل مع مدير النظام لمنحك الصلاحية، أو انتقل إلى شاشة متاحة لك.
          </EmptyDescription>
        </EmptyHeader>
        {fallback && (
          <EmptyContent>
            <Button nativeButton={false} render={<Link to={tenantTo(fallback.to)} />}>
              الانتقال إلى {fallback.label}
            </Button>
          </EmptyContent>
        )}
      </Empty>
    );
  }
  return <Page>{children}</Page>;
}

/**
 * Reusable full suite of ERP modules, pages, and operational screens.
 * These are scoped inside the tenant root layout when a tenant prefix is present.
 */
function renderErpChildRoutes(includeIndex: boolean = true) {
  return (
    <>
      {includeIndex && <Route index element={<Guard perm=""><DashboardPage /></Guard>} />}
      <Route path="dashboard" element={<Guard perm=""><DashboardPage /></Guard>} />
      <Route path="pos" element={<Guard perm="pos"><PosPage /></Guard>} />
      <Route path="products" element={<Guard perm="inventory"><ProductsPage /></Guard>} />
      <Route path="sales" element={<Guard perm="sales"><SalesPage /></Guard>} />
      <Route path="inventory" element={<Guard perm="inventory"><InventoryPage /></Guard>} />
      <Route path="operations" element={<Guard perm="operations"><OperationsPage /></Guard>} />
      <Route path="purchases" element={<Guard perm="purchases"><PurchasesPage /></Guard>} />
      <Route path="customers" element={<Guard perm="customers"><CustomersPage /></Guard>} />
      <Route path="suppliers" element={<Guard perm="purchases"><SuppliersPage /></Guard>} />
      <Route path="finance" element={<Guard perm="finance"><FinancePage /></Guard>} />
      <Route path="hr" element={<Guard perm="payroll"><HrPage /></Guard>} />
      <Route path="hr/payroll" element={<Guard perm="payroll"><PayrollPage /></Guard>} />
      <Route path="shifts" element={<Guard perm="shifts"><ShiftsPage /></Guard>} />
      <Route path="archive" element={<Guard perm="archive"><ArchivePage /></Guard>} />
      <Route path="reports" element={<Guard perm="reports"><ReportsPage /></Guard>} />
      <Route path="users" element={<Guard perm="users"><UsersPage /></Guard>} />
      <Route path="settings" element={<Guard perm="settings"><SettingsPage /></Guard>} />
      <Route path="modules" element={<Guard perm=""><ModulesPage /></Guard>} />
      <Route path="restaurant/tables" element={<Guard perm="" module="restaurant"><RestaurantTablesPage /></Guard>} />
      <Route path="restaurant/kitchen" element={<Guard perm="" module="restaurant"><KitchenDisplayPage /></Guard>} />
      <Route path="school/students" element={<Guard perm="" module="school"><SchoolStudentsPage /></Guard>} />
      <Route path="pharmacy" element={<Guard perm="" module="pharmacy"><PharmacyPage /></Guard>} />
      <Route path="services" element={<Guard perm="" module="services"><ServicesConsultingPage /></Guard>} />
      <Route path="wholesale" element={<Guard perm="" module="wholesale"><WholesaleDistributionPage /></Guard>} />
      <Route path="logistics" element={<Guard perm="" module="logistics"><LogisticsFleetPage /></Guard>} />
      <Route path="wms" element={<Guard perm="" module="wms"><WmsWarehousePage /></Guard>} />
      <Route path="ecommerce" element={<Guard perm="" module="ecommerce"><EcommerceHubPage /></Guard>} />
      <Route path="clinic" element={<Guard perm="" module="healthcare_clinic"><ClinicHealthcarePage /></Guard>} />
      <Route path="clinic/:moduleSlug" element={<Guard perm="" module="healthcare_clinic"><ClinicHealthcarePage /></Guard>} />
      <Route path="integrations/whatsapp" element={<Guard perm="" module="whatsapp_gateway"><WhatsAppGatewayPage /></Guard>} />
      <Route path="law" element={<Guard perm="" module="law"><LawPracticePage /></Guard>} />
      <Route path="travel" element={<Guard perm="" module="travel"><TravelTourismPage /></Guard>} />
      <Route path="hospitality" element={<Guard perm="" module="hospitality"><HospitalityPmsPage /></Guard>} />
      <Route path="gym" element={<Guard perm="" module="gym"><GymFitnessPage /></Guard>} />
      <Route path="salon" element={<Guard perm="" module="salon"><SalonSpaPage /></Guard>} />
      <Route path="agency" element={<Guard perm="" module="agency"><CreativeAgencyPage /></Guard>} />
      <Route path="field-service" element={<Guard perm="" module="field_service"><FieldServicePage /></Guard>} />
      <Route path="mfg" element={<Guard perm="" module="mfg"><DiscreteManufacturingPage /></Guard>} />
      <Route path="fod" element={<Guard perm="" module="fod"><FoodProcessingPage /></Guard>} />
      <Route path="phm" element={<Guard perm="" module="phm"><PharmaGmpPage /></Guard>} />
      <Route path="prn" element={<Guard perm="" module="prn"><PrintingPackagingPage /></Guard>} />
      <Route path="cst" element={<Guard perm="" module="cst"><ConstructionPage /></Guard>} />
      <Route path="rec" element={<Guard perm="" module="rec"><RealEstatePage /></Guard>} />
      <Route path="agr" element={<Guard perm="" module="agr"><AgricultureFarmPage /></Guard>} />
      <Route path="eng" element={<Guard perm="" module="eng"><EnergyPowerPlantPage /></Guard>} />
      <Route path="bnk" element={<Guard perm="" module="bnk"><BankingPage /></Guard>} />
      <Route path="ins" element={<Guard perm="" module="ins"><InsurancePage /></Guard>} />
      <Route path="gov" element={<Guard perm="" module="gov"><GovernmentPage /></Guard>} />
      <Route path="ent" element={<Guard perm="" module="ent"><EntertainmentPage /></Guard>} />
      <Route path="oil" element={<Guard perm="" module="oil"><OilGasPage /></Guard>} />
      <Route path="storefront" element={<Guard perm="" module="storefront"><StorefrontAdminPage /></Guard>} />
      <Route path="pricing" element={<Guard perm=""><PricingPage /></Guard>} />
      <Route path="login" element={<LoginPage />} />
    </>
  );
}

export default function App() {
  return (
    <Routes>
      {/* Cloud: owners sign in here (it opens the owner panel); employees use /c/<workspace>/login.
          On-premise there are no owner accounts: /login is the workspace's own sign-in. */}
      <Route path="/login" element={<LoginPage owner={!IS_ON_PREMISE} />} />

      {/* Public Customer-Facing Storefront Routes */}
      <Route path="/store/:tenantSlug" element={<Page><PublicStorefrontPage /></Page>} />
      <Route path="/store" element={<Navigate to="/" replace />} />

      {/* Pattern 1: Canonical Tenant Root at /c/:tenantSlug/* */}
      <Route path="/c/:tenantSlug" element={<Page><TenantScopeLayout /></Page>}>
        {renderErpChildRoutes()}
      </Route>

      <Route path="/" element={<WorkspaceHome />} />

      {/* Direct top-level routes when authenticated without slug (e.g. desktop offline .exe, direct nav) */}
      <Route
        element={
          <Guard perm="">
            <Shell />
          </Guard>
        }
      >
        {renderErpChildRoutes(false)}
      </Route>

      {/* Pattern 2: Direct Tenant Company Root at /:tenantSlug/* (e.g. /monset-gym/pos) */}
      <Route path="/:tenantSlug" element={<Page><TenantScopeLayout /></Page>}>
        {renderErpChildRoutes()}
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
