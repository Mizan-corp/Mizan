import { lazy, Suspense } from "react";
const DashboardPage = lazy(() => import("@app/features/dashboard/DashboardPage"));
const PosPage = lazy(() => import("@modules/general/pos/PosPage"));
const ProductsPage = lazy(() => import("@app/features/products/ProductsPage"));
const SalesPage = lazy(() => import("@modules/general/sales/SalesPage"));
const PurchasesPage = lazy(() => import("@modules/general/purchases/PurchasesPage"));
const PayrollPage = lazy(() => import("@modules/general/hr/PayrollPage"));
const ShiftsPage = lazy(() => import("@app/features/shifts/ShiftsPage"));
const CustomersPage = lazy(() => import("@app/features/customers/CustomersPage"));
const SettingsPage = lazy(() => import("@app/features/settings/SettingsPage"));
const DesignerPage = lazy(() => import("@app/features/designer/DesignerPage"));
const FinancePage = lazy(() => import("@modules/general/finance/FinancePage"));
const SuppliersPage = lazy(() => import("@app/features/suppliers/SuppliersPage"));
const UsersPage = lazy(() => import("@app/features/users/UsersPage"));
const HrPage = lazy(() => import("@modules/general/hr/HrPage"));
const InventoryPage = lazy(() => import("@modules/general/inventory/InventoryPage"));
const ReportsPage = lazy(() => import("@app/features/reports/ReportsPage"));
const ArchivePage = lazy(() => import("@app/features/archive/ArchivePage"));
const OperationsPage = lazy(() => import("@app/features/operations/OperationsPage"));
const ModulesPage = lazy(() => import("@app/features/modules/ModulesPage"));
const RestaurantTablesPage = lazy(() => import("@modules/restaurant/restaurant/RestaurantTablesPage"));
const KitchenDisplayPage = lazy(() => import("@modules/restaurant/kitchen_display/KitchenDisplayPage"));
const SchoolStudentsPage = lazy(() => import("@modules/school/school/SchoolStudentsPage"));
const PharmacyPage = lazy(() => import("@modules/pharmacy/pharmacy/PharmacyPage"));
const ServicesConsultingPage = lazy(() => import("@modules/consulting/services/ServicesConsultingPage"));
const WholesaleDistributionPage = lazy(() => import("@modules/wholesale/wholesale/WholesaleDistributionPage"));
const LogisticsFleetPage = lazy(() => import("@modules/logistics/logistics/LogisticsFleetPage"));
const WmsWarehousePage = lazy(() => import("@modules/warehousing/wms/WmsWarehousePage"));
const EcommerceHubPage = lazy(() => import("@modules/ecommerce/ecommerce/EcommerceHubPage"));
const ClinicHealthcarePage = lazy(() => import("@modules/healthcare/healthcare_clinic/ClinicHealthcarePage"));
const WhatsAppGatewayPage = lazy(() => import("@app/integrations/whatsapp_gateway/WhatsAppGatewayPage"));
const LawPracticePage = lazy(() => import("@modules/legal/law/LawPracticePage"));
const TravelTourismPage = lazy(() => import("@modules/travel/travel/TravelTourismPage"));
const HospitalityPmsPage = lazy(() => import("@modules/hotel/hospitality/HospitalityPmsPage"));
const GymFitnessPage = lazy(() => import("@modules/gym/gym/GymFitnessPage"));
const SalonSpaPage = lazy(() => import("@modules/salon/salon/SalonSpaPage"));
const CreativeAgencyPage = lazy(() => import("@modules/agency/agency/CreativeAgencyPage"));
const FieldServicePage = lazy(() => import("@modules/maintenance/field_service/FieldServicePage"));
const DiscreteManufacturingPage = lazy(() => import("@modules/manufacturing/manufacturing/DiscreteManufacturingPage"));
const FoodProcessingPage = lazy(() => import("@modules/food/food_manufacturing/FoodProcessingPage"));
const PharmaGmpPage = lazy(() => import("@modules/pharmaceuticals/pharma_manufacturing/PharmaGmpPage"));
const PrintingPackagingPage = lazy(() => import("@modules/printing/printing/PrintingPackagingPage"));
const ConstructionPage = lazy(() => import("@modules/construction/construction/ConstructionPage"));
const RealEstatePage = lazy(() => import("@modules/property/real_estate/RealEstatePage"));
const AgricultureFarmPage = lazy(() => import("@modules/agriculture/agriculture/AgricultureFarmPage"));
const EnergyPowerPlantPage = lazy(() => import("@modules/energy/energy/EnergyPowerPlantPage"));
const BankingPage = lazy(() => import("@modules/banking/banking/BankingPage"));
const InsurancePage = lazy(() => import("@modules/insurance/insurance/InsurancePage"));
const GovernmentPage = lazy(() => import("@modules/government/government/GovernmentPage"));
const EntertainmentPage = lazy(() => import("@modules/entertainment/events/EntertainmentPage"));
const OilGasPage = lazy(() => import("@modules/petroleum/oil_gas/OilGasPage"));
const StorefrontAdminPage = lazy(() => import("@modules/general/storefront/StorefrontAdminPage"));
const PublicStorefrontPage = lazy(() => import("@modules/general/storefront/public/PublicStorefrontPage"));
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
  return <Navigate to={signInPath()} replace />;
}
import { useModulesStore } from "@app/stores/modules";
import { useRoleScreens } from "@app/lib/nav";
import { HOST_WORKSPACE, signInPath, useTenantNav } from "@app/lib/tenant";
import { appUrl } from "@/lib/urls";
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
  const roleScreens = useRoleScreens();

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
    const fallback = roleScreens.data?.screens[0] ? { to: roleScreens.data.home || roleScreens.data.screens[0].path, label: roleScreens.data.screens[0].label } : undefined;
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
      <Route path="suppliers" element={<Guard perm="inventory|purchases"><SuppliersPage /></Guard>} />
      <Route path="finance" element={<Guard perm="finance"><FinancePage /></Guard>} />
      <Route path="hr" element={<Guard perm="payroll"><HrPage /></Guard>} />
      <Route path="hr/payroll" element={<Guard perm="payroll"><PayrollPage /></Guard>} />
      <Route path="shifts" element={<Guard perm="shifts"><ShiftsPage /></Guard>} />
      <Route path="archive" element={<Guard perm="archive"><ArchivePage /></Guard>} />
      <Route path="reports" element={<Guard perm="reports"><ReportsPage /></Guard>} />
      <Route path="users" element={<Guard perm="users"><UsersPage /></Guard>} />
      <Route path="settings" element={<Guard perm="settings"><SettingsPage /></Guard>} />
      <Route path="designer" element={<Guard perm="designer"><DesignerPage /></Guard>} />
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
      <Route path="mfg" element={<Guard perm="" module="manufacturing"><DiscreteManufacturingPage /></Guard>} />
      <Route path="fod" element={<Guard perm="" module="food_manufacturing"><FoodProcessingPage /></Guard>} />
      <Route path="phm" element={<Guard perm="" module="pharma_manufacturing"><PharmaGmpPage /></Guard>} />
      <Route path="prn" element={<Guard perm="" module="printing"><PrintingPackagingPage /></Guard>} />
      <Route path="cst" element={<Guard perm="" module="construction"><ConstructionPage /></Guard>} />
      <Route path="rec" element={<Guard perm="" module="real_estate"><RealEstatePage /></Guard>} />
      <Route path="agr" element={<Guard perm="" module="agriculture"><AgricultureFarmPage /></Guard>} />
      <Route path="eng" element={<Guard perm="" module="energy"><EnergyPowerPlantPage /></Guard>} />
      <Route path="bnk" element={<Guard perm="" module="banking"><BankingPage /></Guard>} />
      <Route path="ins" element={<Guard perm="" module="insurance"><InsurancePage /></Guard>} />
      <Route path="gov" element={<Guard perm="" module="government"><GovernmentPage /></Guard>} />
      <Route path="ent" element={<Guard perm="" module="events"><EntertainmentPage /></Guard>} />
      <Route path="oil" element={<Guard perm="" module="oil_gas"><OilGasPage /></Guard>} />
      <Route path="storefront" element={<Guard perm="" module="storefront"><StorefrontAdminPage /></Guard>} />
      <Route path="pricing" element={<Guard perm=""><PricingPage /></Guard>} />
      <Route path="login" element={<LoginPage />} />
    </>
  );
}

/** Cloud, no workspace in the address: owners sign in on the owner panel (ADR-008). */
function ToOwnerSignIn() {
  window.location.replace(appUrl("owner", `/login${window.location.search}`));
  return null;
}

export default function App() {
  if (HOST_WORKSPACE) {
    // The workspace's own address (<slug>.allmizan.live): every route is that workspace's.
    return (
      <Routes>
        <Route path="/store/:tenantSlug" element={<Page><PublicStorefrontPage /></Page>} />
        <Route path="/c/:tenantSlug/*" element={<Navigate to="/" replace />} />
        <Route path="/" element={<Page><TenantScopeLayout /></Page>}>
          {renderErpChildRoutes()}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }
  return (
    <Routes>
      {/* Cloud: owners sign in on the owner panel; employees use their workspace's page.
          On-premise there are no owner accounts: /login is the workspace's own sign-in. */}
      <Route path="/login" element={IS_ON_PREMISE ? <LoginPage /> : <ToOwnerSignIn />} />

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
