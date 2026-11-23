import { lazy, Suspense, type ReactNode } from "react";
import { Route, Routes } from "react-router-dom";
import { AdoptSession, SignOut } from "@app/features/session/SessionRoutes";
import { appUrl } from "@/lib/urls";
import { DEV_HOST } from "@app/features/developers/paths";
import { LangScope } from "@app/seo/LocaleLink";
import type { Lang } from "@app/seo/paths";

// Every page is its own chunk: a visitor downloads the page they open (the pre-rendered HTML
// preloads it, ADR-016), not the whole site.
const LandingPage = lazy(() => import("@app/features/marketing/LandingPage"));
const ProductPage = lazy(() => import("@app/features/marketing/ProductPage"));
const FeaturesPage = lazy(() => import("@app/features/marketing/FeaturesPage"));
const FeatureDetailPage = lazy(() => import("@app/features/marketing/FeatureDetailPage"));
const IndustriesPage = lazy(() => import("@app/features/marketing/IndustriesPage"));
const PricingRoute = lazy(() => import("@app/features/marketing/PricingRoute"));
const AboutPage = lazy(() => import("@app/features/marketing/AboutPage"));
const ContactPage = lazy(() => import("@app/features/marketing/ContactPage"));
const BlogPage = lazy(() => import("@app/features/marketing/BlogPage"));
const BlogPostPage = lazy(() => import("@app/features/marketing/BlogPostPage"));
const DashboardShowcasePage = lazy(() => import("@app/features/marketing/DashboardShowcasePage"));
const NotFoundPage = lazy(() => import("@app/features/marketing/NotFoundPage"));
const SignupPage = lazy(() => import("@app/features/marketing/SignupPage"));
const OnboardingWizard = lazy(() => import("@app/features/marketing/OnboardingWizard"));
const LegalPage = lazy(() => import("@app/features/legal/LegalPage"));
const DocsHomeRoute = lazy(() => import("@app/features/docs/DocsRoutes").then((m) => ({ default: m.DocsHomeRoute })));
const DocsArticleRoute = lazy(() => import("@app/features/docs/DocsRoutes").then((m) => ({ default: m.DocsArticleRoute })));
const DevRoutes = lazy(() => import("@app/features/developers/DevRoutes"));

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

/** Owners sign in on the owner panel (ADR-008); staff use their workspace's page. */
function ToOwnerLogin() {
  window.location.replace(appUrl("owner", "/login"));
  return null;
}

/**
 * The public site in one language: Arabic at "/…", English under "/en/…" (ADR-016). English has
 * the key pages only (src/seo/paths.ts EN_PAGES); any other English address is a 404.
 */
function Site({ lang }: { lang: Lang }) {
  const ar = lang === "ar";
  return (
    <LangScope lang={lang}>
      <Routes>
        <Route index element={<Page><LandingPage /></Page>} />
        <Route path="product" element={<Page><ProductPage /></Page>} />
        <Route path="features" element={<Page><FeaturesPage /></Page>} />
        <Route path="features/inventory" element={<Page><FeatureDetailPage /></Page>} />
        <Route path="industries" element={<Page><IndustriesPage /></Page>} />
        <Route path="pricing" element={<Page><PricingRoute /></Page>} />
        <Route path="about" element={<Page><AboutPage /></Page>} />
        <Route path="contact" element={<Page><ContactPage /></Page>} />
        <Route path="demo" element={<Page><DashboardShowcasePage /></Page>} />
        <Route path="terms" element={<Page><LegalPage slug="terms" /></Page>} />
        <Route path="privacy" element={<Page><LegalPage slug="privacy" /></Page>} />
        <Route path="refund-policy" element={<Page><LegalPage slug="refund-policy" /></Page>} />
        <Route path="signup" element={<Page><SignupPage /></Page>} />
        {ar && (
          <>
            <Route path="blog" element={<Page><BlogPage /></Page>} />
            <Route path="blog/:slug" element={<Page><BlogPostPage /></Page>} />
            <Route path="docs" element={<Page><DocsHomeRoute /></Page>} />
            <Route path="docs/*" element={<Page><DocsArticleRoute /></Page>} />
            <Route path="onboarding" element={<Page><OnboardingWizard /></Page>} />
            <Route path="login" element={<ToOwnerLogin />} />
            <Route path="session" element={<AdoptSession />} />
            <Route path="signout" element={<SignOut />} />
          </>
        )}
        <Route path="*" element={<Page><NotFoundPage /></Page>} />
      </Routes>
    </LangScope>
  );
}

export default function App() {
  // dev.allmizan.live is the developer platform (ADR-007 D6); elsewhere it lives under /dev.
  if (DEV_HOST) {
    return (
      <Routes>
        <Route path="/*" element={<Page><DevRoutes /></Page>} />
      </Routes>
    );
  }
  return (
    <Routes>
      <Route path="/dev/*" element={<Page><DevRoutes /></Page>} />
      <Route path="/en/*" element={<Site lang="en" />} />
      <Route path="/*" element={<Site lang="ar" />} />
    </Routes>
  );
}
