/**
 * The developer platform (ADR-007 D6): home, docs and the portal. At the root of
 * dev.allmizan.live, under /dev elsewhere (paths.ts).
 */
import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { DocsLayout } from "@app/features/docs/DocsLayout";
import { devPath } from "./paths";
import { DEV_DOC_SECTIONS } from "./devDocs";

const DevHome = lazy(() => import("./DevHome"));
const AuthPage = lazy(() => import("./AuthPage"));
const DevDocsHome = lazy(() => import("./DevDocsHome"));
const DocsArticlePage = lazy(() => import("@app/features/docs/DocsArticlePage"));
const PortalShell = lazy(() => import("./PortalShell"));
const TeamsPage = lazy(() => import("./TeamsPage"));
const TeamPage = lazy(() => import("./TeamPage"));
const TokensPage = lazy(() => import("./TokensPage"));
const AccountPage = lazy(() => import("./AccountPage"));

function Page({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<div className="grid place-items-center p-16"><span className="h-6 w-6 animate-spin rounded-full border-2 border-brand border-t-transparent" /></div>}>
      {children}
    </Suspense>
  );
}

function Docs({ children }: { children: ReactNode }) {
  return (
    <DocsLayout sections={DEV_DOC_SECTIONS} base={devPath("/docs")} home={devPath("/")} label={{ ar: "توثيق المطورين", en: "Developer docs" }}>
      {children}
    </DocsLayout>
  );
}

export default function DevRoutes() {
  return (
    <Routes>
      <Route index element={<Page><DevHome /></Page>} />
      <Route path="login" element={<Page><AuthPage mode="login" /></Page>} />
      <Route path="signup" element={<Page><AuthPage mode="signup" /></Page>} />
      <Route path="docs" element={<Page><Docs><DevDocsHome /></Docs></Page>} />
      <Route path="docs/*" element={<Page><Docs><DocsArticlePage sections={DEV_DOC_SECTIONS} base={devPath("/docs")} help={devPath("/portal")}
                                                                 helpText={{ title: "بوابة المطورين", hint: "فرقك ومفاتيح التوقيع ورموز سطر الأوامر" }} /></Docs></Page>} />
      <Route path="portal" element={<Page><PortalShell /></Page>}>
        <Route index element={<Page><TeamsPage /></Page>} />
        <Route path="teams/:handle" element={<Page><TeamPage /></Page>} />
        <Route path="tokens" element={<Page><TokensPage /></Page>} />
        <Route path="account" element={<Page><AccountPage /></Page>} />
      </Route>
      <Route path="*" element={<Navigate to={devPath("/")} replace />} />
    </Routes>
  );
}
