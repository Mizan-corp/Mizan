import { moduleDefinitions } from "@app/framework/registry";
import { lazy, Suspense } from "react";
const DashboardPage = lazy(() => import("@app/platform/core/screens/DashboardPage"));
const ProductsPage = lazy(() => import("@app/activities/general/modules/inventory/screens/ProductsPage"));
const CustomersPage = lazy(() => import("@app/activities/general/modules/contacts/screens/CustomersPage"));
const SettingsPage = lazy(() => import("@app/platform/core/screens/SettingsPage"));
const CommunityEntityPage = lazy(() => import("@app/platform/community/screens/EntityPage"));
const SuppliersPage = lazy(() => import("@app/activities/general/modules/purchases/screens/SuppliersPage"));
const UsersPage = lazy(() => import("@app/platform/core/screens/UsersPage"));
const ReportsPage = lazy(() => import("@app/activities/general/modules/reporting/screens/ReportsPage"));
const ArchivePage = lazy(() => import("@app/activities/general/modules/documents/screens/ArchivePage"));
const OperationsPage = lazy(() => import("@app/activities/general/modules/operations/screens/OperationsPage"));
const ModulesPage = lazy(() => import("@app/platform/marketplace/screens/ModulesPage"));
const HelpdeskPage = lazy(() => import("@app/activities/general/modules/helpdesk/screens/HelpdeskPage"));
const TenantScopeLayout = lazy(() => import("@app/platform/core/screens/TenantScopeLayout"));



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
import LoginPage from "@app/platform/core/screens/LoginPage";
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
      <Route path="products" element={<Guard perm="inventory"><ProductsPage /></Guard>} />
      <Route path="operations" element={<Guard perm="operations"><OperationsPage /></Guard>} />
      <Route path="customers" element={<Guard perm="customers"><CustomersPage /></Guard>} />
      <Route path="suppliers" element={<Guard perm="purchases|finance"><SuppliersPage /></Guard>} />
      <Route path="archive" element={<Guard perm="archive"><ArchivePage /></Guard>} />
      <Route path="reports" element={<Guard perm="reports"><ReportsPage /></Guard>} />
      <Route path="users" element={<Guard perm="users"><UsersPage /></Guard>} />
      <Route path="settings" element={<Guard perm="settings"><SettingsPage /></Guard>} />
      {/* Community modules (ADR-007): their records, drawn from the entity they declare. */}
      <Route path="x/:module/:entity" element={<CommunityEntityPage />} />
      <Route path="modules" element={<Guard perm=""><ModulesPage /></Guard>} />
      <Route path="helpdesk" element={<Guard perm="helpdesk:view|helpdesk:work:view" module="helpdesk"><HelpdeskPage /></Guard>} />
      <Route path="pricing" element={<Guard perm=""><PricingPage /></Guard>} />
      <Route path="login" element={<LoginPage />} />
      {/* Routes the modules declare in their index.ts (migration step 2). */}
      {moduleDefinitions.flatMap((m) => m.routes ?? []).map((r) => (
        <Route key={r.path} path={r.path} element={<Guard perm={r.perm} module={r.module}><r.component /></Guard>} />
      ))}
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
