import React, { type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ToastProvider } from "@/components/ui";
import { SiteEffects } from "@app/seo/SiteEffects";

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: 1, staleTime: 30_000, refetchOnWindowFocus: false },
    },
  });
}

/**
 * The website's tree, the same in the browser (main.tsx) and at build time (entry-server.tsx,
 * which pre-renders every public page, ADR-016); only the router differs.
 */
export function Root({ router: Router, queryClient }: { router: (p: { children: ReactNode }) => ReactNode; queryClient: QueryClient }) {
  return (
    <React.StrictMode>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <Router>
            <ToastProvider>
              <App />
              <SiteEffects />
            </ToastProvider>
          </Router>
        </QueryClientProvider>
      </ErrorBoundary>
    </React.StrictMode>
  );
}
