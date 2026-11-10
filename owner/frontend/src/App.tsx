import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/stores/auth";
import { useMe } from "@app/lib/data";
import Shell from "@app/Shell";
import { goToSignIn } from "@app/lib/session";
import { PageSkeleton } from "@app/ui";

const Workspaces = lazy(() => import("@app/pages/Workspaces"));
const Workspace = lazy(() => import("@app/pages/Workspace"));
const Invoices = lazy(() => import("@app/pages/Invoices"));
const Account = lazy(() => import("@app/pages/Account"));
const Payment = lazy(() => import("@app/pages/Payment"));
const PaymentReturn = lazy(() => import("@app/pages/Payment").then((m) => ({ default: m.PaymentReturn })));

export default function App() {
  const token = useAuth((s) => s.token);
  const me = useMe(!!token);
  const expired = !!token && me.isError && me.error instanceof ApiError && me.error.status === 401;
  const signedOut = !token || expired;

  useEffect(() => {
    if (!signedOut) return;
    useAuth.getState().logout();
    goToSignIn();
  }, [signedOut]);

  if (signedOut || me.isPending) return null;

  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Workspaces />} />
          <Route path="workspaces/:id" element={<Workspace />} />
          <Route path="invoices" element={<Invoices />} />
          <Route path="account" element={<Account />} />
          <Route path="payment" element={<PaymentReturn />} />
          <Route path="payment/:ref" element={<Payment />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
