import { useParams } from "react-router-dom";
import NotFoundPage from "@app/features/marketing/NotFoundPage";
import { DocsLayout } from "./DocsLayout";
import DocsHomePage from "./DocsHomePage";
import DocsArticlePage from "./DocsArticlePage";
import { getDocArticle } from "./docsData";

/** The user docs at /docs (Arabic). The developer docs reuse the components (developers/DevRoutes). */
export function DocsHomeRoute() {
  return (
    <DocsLayout>
      <DocsHomePage />
    </DocsLayout>
  );
}

/** An unknown article is a "page not found" (nginx answers it with status 404). */
export function DocsArticleRoute() {
  const slug = useParams()["*"] ?? "";
  if (!getDocArticle(slug)) return <NotFoundPage />;
  return (
    <DocsLayout>
      <DocsArticlePage />
    </DocsLayout>
  );
}
