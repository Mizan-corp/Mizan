import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth, type User } from "@/stores/auth";
import Shell from "@app/Shell";
import SignIn from "@app/SignIn";
import { PageSkeleton } from "@app/ui";

const Overview = lazy(() => import("@app/pages/Overview"));
const Workspaces = lazy(() => import("@app/pages/Workspaces"));
const WorkspaceDetail = lazy(() => import("@app/pages/WorkspaceDetail"));
const Billing = lazy(() => import("@app/pages/Billing"));
const Owners = lazy(() => import("@app/pages/Owners"));
const Activity = lazy(() => import("@app/pages/Activity"));
const Marketplace = lazy(() => import("@app/pages/Marketplace"));
const Team = lazy(() => import("@app/pages/Team"));
const System = lazy(() => import("@app/pages/System"));

const isStaff = (u: User | null) => !!u && (u.is_superadmin || u.role === "superadmin");

export default function App() {
  const token = useAuth((s) => s.token);
  const user = useAuth((s) => s.user);

  // Re-check the session on load: access may have been removed since sign-in.
  const me = useQuery({
    queryKey: ["me", token],
    queryFn: () => api.get<User>("/auth/me"),
    enabled: !!token,
    retry: false,
    staleTime: Infinity,
  });

  const [notice, setNotice] = useState<string>();
  const denied = !!token && !me.isPending && (me.isError || !isStaff(me.data ?? null));
  useEffect(() => {
    if (!denied) return;
    setNotice(me.isError ? "Your session ended. Sign in again." : "This account no longer has access to the admin panel.");
    useAuth.getState().logout();
  }, [denied, me.isError]);

  if (denied || !token || !user) return <SignIn key={notice} notice={notice} />;
  if (me.isPending) return null;

  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Overview />} />
          <Route path="workspaces" element={<Workspaces />} />
          <Route path="workspaces/:id" element={<WorkspaceDetail />} />
          <Route path="owners" element={<Owners />} />
          <Route path="billing" element={<Billing />} />
          <Route path="activity" element={<Activity />} />
          <Route path="marketplace" element={<Marketplace />} />
          <Route path="team" element={<Team />} />
          <Route path="system" element={<System />} />
        </Route>
        {/* Old Admoon addresses */}
        <Route path="admoon/tenants/:id" element={<LegacyTenant />} />
        <Route path="admoon/*" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

function LegacyTenant() {
  const { id } = useParams();
  return <Navigate to={`/workspaces/${id}`} replace />;
}
