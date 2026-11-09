import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import LandingPage from "@app/features/marketing/LandingPage";
import SignupPage from "@app/features/marketing/SignupPage";
import OnboardingWizard from "@app/features/marketing/OnboardingWizard";
import { MarketingLayout } from "@app/features/marketing/MarketingLayout";
import { AdoptSession, SignOut } from "@app/features/session/SessionRoutes";
import PricingPage from "@/features/billing/PricingPage";
import { appUrl } from "@/lib/urls";

const ProductPage = lazy(() => import("@app/features/marketing/ProductPage"));
const FeaturesPage = lazy(() => import("@app/features/marketing/FeaturesPage"));
const FeatureDetailPage = lazy(() => import("@app/features/marketing/FeatureDetailPage"));
const IndustriesPage = lazy(() => import("@app/features/marketing/IndustriesPage"));
const AboutPage = lazy(() => import("@app/features/marketing/AboutPage"));
const ContactPage = lazy(() => import("@app/features/marketing/ContactPage"));
const BlogPage = lazy(() => import("@app/features/marketing/BlogPage"));
const BlogPostPage = lazy(() => import("@app/features/marketing/BlogPostPage"));
const DashboardShowcasePage = lazy(() => import("@app/features/marketing/DashboardShowcasePage"));
const DocsLayout = lazy(() => import("@app/features/docs/DocsLayout").then((m) => ({ default: m.DocsLayout })));
const DocsHomePage = lazy(() => import("@app/features/docs/DocsHomePage"));
const DocsArticlePage = lazy(() => import("@app/features/docs/DocsArticlePage"));

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

/** Owners sign in on the app's /login (it opens the owner panel); staff use their workspace's page. */
function ToSystemLogin() {
  window.location.replace(appUrl("system", "/login"));
  return null;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Page><LandingPage /></Page>} />
      <Route path="/product" element={<Page><ProductPage /></Page>} />
      <Route path="/features" element={<Page><FeaturesPage /></Page>} />
      <Route path="/features/details" element={<Page><FeatureDetailPage /></Page>} />
      <Route path="/features/:slug" element={<Page><FeatureDetailPage /></Page>} />
      <Route path="/industries" element={<Page><IndustriesPage /></Page>} />
      <Route path="/pricing" element={<Page><PricingPage layout={MarketingLayout} /></Page>} />
      <Route path="/about" element={<Page><AboutPage /></Page>} />
      <Route path="/contact" element={<Page><ContactPage /></Page>} />
      <Route path="/blog" element={<Page><BlogPage /></Page>} />
      <Route path="/blog/:slug" element={<Page><BlogPostPage /></Page>} />
      <Route path="/demo" element={<Page><DashboardShowcasePage /></Page>} />

      <Route path="/docs" element={<Page><DocsLayout><DocsHomePage /></DocsLayout></Page>} />
      <Route path="/docs/*" element={<Page><DocsLayout><DocsArticlePage /></DocsLayout></Page>} />

      <Route path="/signup" element={<SignupPage />} />
      <Route path="/onboarding" element={<OnboardingWizard />} />
      <Route path="/login" element={<ToSystemLogin />} />
      <Route path="/session" element={<AdoptSession />} />
      <Route path="/signout" element={<SignOut />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
