import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import App from "./App";
import "./admin.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 20_000, refetchOnWindowFocus: true },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={import.meta.env.BASE_URL}>
        <App />
        <Toaster position="bottom-right" toastOptions={{ style: { fontFamily: "var(--font-admin)" } }} />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
