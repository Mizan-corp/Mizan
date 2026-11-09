import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import { takeHandedOffSession } from "@/lib/handoff";
import { useAuth } from "@/stores/auth";
import App from "./App";
import "./owner.css";

// Signed in by the website right after signup: adopt that owner session.
const handedOff = takeHandedOffSession();
if (handedOff) {
  useAuth.getState().logout();
  useAuth.getState().setToken(handedOff);
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 20_000, refetchOnWindowFocus: true } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <App />
        <Toaster position="bottom-left" dir="rtl" toastOptions={{ style: { fontFamily: "var(--font-owner)" } }} />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
