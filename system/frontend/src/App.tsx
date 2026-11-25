import { lazy, Suspense } from "react";
const DashboardPage = lazy(() => import("@app/features/dashboard/DashboardPage"));
const PosPage = lazy(() => import("@activities/general/modules/pos/PosPage"));
const ProductsPage = lazy(() => import("@app/features/products/ProductsPage"));
const SalesPage = lazy(() => import("@activities/general/modules/sales/screens/SalesPage"));
const PurchasesPage = lazy(() => import("@activities/general/modules/purchases/PurchasesPage"));
const PayrollPage = lazy(() => import("@activities/general/modules/hr/PayrollPage"));
const ShiftsPage = lazy(() => import("@activities/general/modules/pos/screens/ShiftsPage"));
const CustomersPage = lazy(() => import("@app/features/customers/CustomersPage"));
const SettingsPage = lazy(() => import("@app/features/settings/SettingsPage"));
const DesignerPage = lazy(() => import("@app/features/designer/DesignerPage"));
const WebsitePage = lazy(() => import("@activities/general/modules/website/WebsitePage"));
const CommunityEntityPage = lazy(() => import("@app/platform/community/screens/EntityPage"));
const FinancePage = lazy(() => import("@activities/general/modules/finance/FinancePage"));
const SuppliersPage = lazy(() => import("@app/features/suppliers/SuppliersPage"));
const UsersPage = lazy(() => import("@app/features/users/UsersPage"));
const HrPage = lazy(() => import("@activities/general/modules/hr/HrPage"));
const InventoryPage = lazy(() => import("@activities/general/modules/inventory/InventoryPage"));
const InventoryCategoriesPage = lazy(() => import("@activities/general/modules/inventory/screens/CategoriesPage"));
const InventoryAdjustmentsPage = lazy(() => import("@activities/general/modules/inventory/screens/AdjustmentsPage"));
const InventoryCollectionsPage = lazy(() => import("@activities/general/modules/inventory/screens/CollectionsPage"));
const InventoryWarehousesPage = lazy(() => import("@activities/general/modules/inventory/screens/WarehousesPage"));
const PurchaseOrderPage = lazy(() => import("@activities/general/modules/purchases/screens/PurchaseOrderPage"));
const PurchaseSuggestionsPage = lazy(() => import("@activities/general/modules/purchases/screens/SuggestionsPage"));
const PurchasePriceHistoryPage = lazy(() => import("@activities/general/modules/purchases/screens/PriceHistoryPage"));
const ReportsPage = lazy(() => import("@app/features/reports/ReportsPage"));
const ArchivePage = lazy(() => import("@app/features/archive/ArchivePage"));
const OperationsPage = lazy(() => import("@app/features/operations/OperationsPage"));
const ModulesPage = lazy(() => import("@app/features/modules/ModulesPage"));
const RestaurantTablesPage = lazy(() => import("@activities/restaurant/modules/restaurant/RestaurantTablesPage"));
const KitchenDisplayPage = lazy(() => import("@activities/restaurant/modules/kitchen_display/KitchenDisplayPage"));
const SchoolStudentsPage = lazy(() => import("@activities/school/modules/school/SchoolStudentsPage"));
const PharmacyPage = lazy(() => import("@activities/pharmacy/modules/pharmacy/PharmacyPage"));
const ServicesConsultingPage = lazy(() => import("@activities/consulting/modules/services/ServicesConsultingPage"));
const WholesaleDistributionPage = lazy(() => import("@activities/wholesale/modules/wholesale/WholesaleDistributionPage"));
const LogisticsFleetPage = lazy(() => import("@activities/logistics/modules/logistics/LogisticsFleetPage"));
const WmsWarehousePage = lazy(() => import("@activities/warehousing/modules/wms/WmsWarehousePage"));
const EcommerceHubPage = lazy(() => import("@activities/ecommerce/modules/ecommerce/EcommerceHubPage"));
const ClinicHealthcarePage = lazy(() => import("@activities/healthcare/modules/healthcare_clinic/ClinicHealthcarePage"));
const WhatsAppGatewayPage = lazy(() => import("@app/integrations/whatsapp_gateway/WhatsAppGatewayPage"));
const LawPracticePage = lazy(() => import("@activities/legal/modules/law/LawPracticePage"));
const TravelTourismPage = lazy(() => import("@activities/travel/modules/travel/TravelTourismPage"));
const HospitalityPmsPage = lazy(() => import("@activities/hotel/modules/hospitality/HospitalityPmsPage"));
const GymFitnessPage = lazy(() => import("@activities/gym/modules/gym/GymFitnessPage"));
const HelpdeskPage = lazy(() => import("./features/helpdesk/HelpdeskPage"));
const SalonSpaPage = lazy(() => import("@activities/salon/modules/salon/SalonSpaPage"));
const CreativeAgencyPage = lazy(() => import("@activities/agency/modules/agency/CreativeAgencyPage"));
const FieldServicePage = lazy(() => import("@activities/maintenance/modules/field_service/FieldServicePage"));
const DiscreteManufacturingPage = lazy(() => import("@activities/manufacturing/modules/manufacturing/DiscreteManufacturingPage"));
const FoodProcessingPage = lazy(() => import("@activities/food/modules/food_manufacturing/FoodProcessingPage"));
const PharmaGmpPage = lazy(() => import("@activities/pharmaceuticals/modules/pharma_manufacturing/PharmaGmpPage"));
const PrintingPackagingPage = lazy(() => import("@activities/printing/modules/printing/PrintingPackagingPage"));
const ConstructionPage = lazy(() => import("@activities/construction/modules/construction/ConstructionPage"));
const RealEstatePage = lazy(() => import("@activities/property/modules/real_estate/RealEstatePage"));
const AgricultureFarmPage = lazy(() => import("@activities/agriculture/modules/agriculture/AgricultureFarmPage"));
const EnergyPowerPlantPage = lazy(() => import("@activities/energy/modules/energy/EnergyPowerPlantPage"));
const BankingPage = lazy(() => import("@activities/banking/modules/banking/BankingPage"));
const InsurancePage = lazy(() => import("@activities/insurance/modules/insurance/InsurancePage"));
const GovernmentPage = lazy(() => import("@activities/government/modules/government/GovernmentPage"));
const EntertainmentPage = lazy(() => import("@activities/entertainment/modules/events/EntertainmentPage"));
const OilGasPage = lazy(() => import("@activities/petroleum/modules/oil_gas/OilGasPage"));
const TenantScopeLayout = lazy(() => import("@app/features/tenant/TenantScopeLayout"));
const AccountingJournalPage = lazy(() => import("@activities/general/modules/accounting/screens/JournalPage"));
const AccountingAccountsPage = lazy(() => import("@activities/general/modules/accounting/screens/AccountsPage"));
const AccountingReportsPage = lazy(() => import("@activities/general/modules/accounting/screens/ReportsPage"));
const AccountingPeriodsPage = lazy(() => import("@activities/general/modules/accounting/screens/PeriodsPage"));
const AccountingOpeningPage = lazy(() => import("@activities/general/modules/accounting/screens/OpeningPage"));



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
      <Route path="inventory/categories" element={<Guard perm="inventory"><InventoryCategoriesPage /></Guard>} />
      <Route path="inventory/adjustments" element={<Guard perm="inventory"><InventoryAdjustmentsPage /></Guard>} />
      <Route path="inventory/collections" element={<Guard perm="inventory"><InventoryCollectionsPage /></Guard>} />
      <Route path="inventory/warehouses" element={<Guard perm="settings"><InventoryWarehousesPage /></Guard>} />
      <Route path="operations" element={<Guard perm="operations"><OperationsPage /></Guard>} />
      <Route path="purchases" element={<Guard perm="purchases|finance"><PurchasesPage /></Guard>} />
      <Route path="purchases/suggestions" element={<Guard perm="purchases|finance"><PurchaseSuggestionsPage /></Guard>} />
      <Route path="purchases/price-history" element={<Guard perm="purchases|finance"><PurchasePriceHistoryPage /></Guard>} />
      <Route path="purchases/:id" element={<Guard perm="purchases|finance"><PurchaseOrderPage /></Guard>} />
      <Route path="customers" element={<Guard perm="customers"><CustomersPage /></Guard>} />
      <Route path="suppliers" element={<Guard perm="purchases|finance"><SuppliersPage /></Guard>} />
      <Route path="finance" element={<Guard perm="finance"><FinancePage /></Guard>} />
      <Route path="accounting/journal" element={<Guard perm="accounting:view|accounting:journal" module="accounting"><AccountingJournalPage /></Guard>} />
      <Route path="accounting/accounts" element={<Guard perm="accounting:view" module="accounting"><AccountingAccountsPage /></Guard>} />
      <Route path="accounting/reports" element={<Guard perm="accounting:view" module="accounting"><AccountingReportsPage /></Guard>} />
      <Route path="accounting/periods" element={<Guard perm="accounting:close|accounting:settings" module="accounting"><AccountingPeriodsPage /></Guard>} />
      <Route path="accounting/opening" element={<Guard perm="accounting:settings" module="accounting"><AccountingOpeningPage /></Guard>} />
      <Route path="hr" element={<Guard perm="payroll"><HrPage /></Guard>} />
      <Route path="hr/payroll" element={<Guard perm="payroll"><PayrollPage /></Guard>} />
      <Route path="shifts" element={<Guard perm="shifts"><ShiftsPage /></Guard>} />
      <Route path="archive" element={<Guard perm="archive"><ArchivePage /></Guard>} />
      <Route path="reports" element={<Guard perm="reports"><ReportsPage /></Guard>} />
      <Route path="users" element={<Guard perm="users"><UsersPage /></Guard>} />
      <Route path="settings" element={<Guard perm="settings"><SettingsPage /></Guard>} />
      <Route path="designer" element={<Guard perm="designer"><DesignerPage /></Guard>} />
      <Route path="website" element={<Guard perm="site.manage"><WebsitePage /></Guard>} />
      {/* Community modules (ADR-007): their records, drawn from the entity they declare. */}
      <Route path="x/:module/:entity" element={<CommunityEntityPage />} />
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
      <Route path="helpdesk" element={<Guard perm="helpdesk:view|helpdesk:work:view" module="helpdesk"><HelpdeskPage /></Guard>} />
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
