import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

const AdmoonLayout = lazy(() => import("@app/admoon/AdmoonLayout"));
const AdmoonDashboard = lazy(() => import("@app/admoon/pages/Dashboard"));
const AdmoonTenants = lazy(() => import("@app/admoon/pages/Tenants"));
const AdmoonTenantDetails = lazy(() => import("@app/admoon/pages/TenantDetails"));
const AdmoonTenantWizard = lazy(() => import("@app/admoon/pages/TenantWizard"));
const AdmoonHostingConfig = lazy(() => import("@app/admoon/pages/HostingConfig"));
const AdmoonDatabaseConfig = lazy(() => import("@app/admoon/pages/DatabaseConfig"));
const AdmoonStorageConfig = lazy(() => import("@app/admoon/pages/StorageConfig"));
const AdmoonInfrastructure = lazy(() => import("@app/admoon/pages/Infrastructure"));
const AdmoonProvisioningJobs = lazy(() => import("@app/admoon/pages/ProvisioningJobs"));
const AdmoonModuleCatalog = lazy(() => import("@app/admoon/pages/ModuleCatalog"));
const AdmoonSubscriptions = lazy(() => import("@app/admoon/pages/Subscriptions"));
const AdmoonBillingInvoices = lazy(() => import("@app/admoon/pages/BillingInvoices"));
const AdmoonBackups = lazy(() => import("@app/admoon/pages/Backups"));
const AdmoonMonitoringHealth = lazy(() => import("@app/admoon/pages/MonitoringHealth"));
const AdmoonAuditLogs = lazy(() => import("@app/admoon/pages/AuditLogs"));
const AdmoonPlatformUsers = lazy(() => import("@app/admoon/pages/PlatformUsers"));
const AdmoonSystemSettings = lazy(() => import("@app/admoon/pages/SystemSettings"));

function Page({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="grid place-items-center p-16">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-brand border-t-transparent" />
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

/** Admoon: the platform owner's control plane. AdmoonLayout gates on a super-admin session. */
export default function App() {
  return (
    <Routes>
      <Route
        path="/admoon"
        element={
          <Page>
            <AdmoonLayout />
          </Page>
        }
      >
        <Route index element={<AdmoonDashboard />} />
        <Route path="tenants" element={<AdmoonTenants />} />
        <Route path="tenants/:tenantId" element={<AdmoonTenantDetails />} />
        <Route path="wizard" element={<AdmoonTenantWizard />} />
        <Route path="hosting" element={<AdmoonHostingConfig />} />
        <Route path="databases" element={<AdmoonDatabaseConfig />} />
        <Route path="storage" element={<AdmoonStorageConfig />} />
        <Route path="infrastructure" element={<AdmoonInfrastructure />} />
        <Route path="jobs" element={<AdmoonProvisioningJobs />} />
        <Route path="modules" element={<AdmoonModuleCatalog />} />
        <Route path="subscriptions" element={<AdmoonSubscriptions />} />
        <Route path="billing" element={<AdmoonBillingInvoices />} />
        <Route path="billing-invoices" element={<AdmoonBillingInvoices />} />
        <Route path="backups" element={<AdmoonBackups />} />
        <Route path="monitoring" element={<AdmoonMonitoringHealth />} />
        <Route path="audit-logs" element={<AdmoonAuditLogs />} />
        <Route path="users" element={<AdmoonPlatformUsers />} />
        <Route path="settings" element={<AdmoonSystemSettings />} />
      </Route>

      <Route path="*" element={<Navigate to="/admoon" replace />} />
    </Routes>
  );
}
