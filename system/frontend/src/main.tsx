import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ToastProvider } from "@/components/ui";
import { Toaster } from "@/components/kit/sonner";
import { api } from "@/lib/api";
import { takeHandedOffSession } from "@/lib/handoff";
import { useAuth, type User } from "@/stores/auth";
import "@/styles.css";

document.documentElement.classList.toggle(
  "dark",
  (localStorage.getItem("mizan.theme") ?? localStorage.getItem("vendora.theme") ?? "light") === "dark",
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
  },
});

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}

/** Sign in with a session handed off by the website (onboarding) or admin (impersonation). */
async function adoptHandedOffSession(): Promise<void> {
  const token = takeHandedOffSession();
  if (!token) return;
  const auth = useAuth.getState();
  auth.logout();
  auth.setToken(token);
  try {
    auth.setUser(await api.get<User>("/auth/me"));
  } catch {
    auth.logout();
  }
}

void adoptHandedOffSession().finally(() => {
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter basename={import.meta.env.BASE_URL}>
            <ToastProvider>
              <App />
              <Toaster position="top-center" dir="rtl" />
            </ToastProvider>
          </BrowserRouter>
        </QueryClientProvider>
      </ErrorBoundary>
    </React.StrictMode>,
  );
});
