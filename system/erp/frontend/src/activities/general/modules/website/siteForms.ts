// Client for the Website tab's form-submissions inbox (/site/forms,
// app/platform/site/forms.py). Visitor messages sent through published form
// blocks are read here; the only mutation is marking a message read.
import { SiteApiError, siteRequestHeaders } from "@app/features/studio/sitePages";

export type SiteFormSubmission = {
  id: string;
  page_id: string;
  page_slug: string | null;
  block_id: string;
  payload: { name?: string; email?: string; phone?: string; message?: string };
  created_at: string | null;
  read_at: string | null;
};

export type SiteFormSubmissionsList = {
  submissions: SiteFormSubmission[];
};

async function request<T>(baseUrl: string, method: string, path: string): Promise<T> {
  const headers = siteRequestHeaders(
    baseUrl,
    method,
    false,
    typeof document === "undefined" ? "" : document.cookie,
  );
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const data: unknown = await response.json();
      if (data && typeof data === "object" && typeof (data as { detail?: unknown }).detail === "string") {
        detail = (data as { detail: string }).detail;
      }
    } catch { /* non-JSON error body: keep the generic message */ }
    throw new SiteApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export function createSiteFormsClient({ baseUrl }: { baseUrl: string }) {
  return {
    listSubmissions: (unreadOnly = false) =>
      request<SiteFormSubmissionsList>(
        baseUrl,
        "GET",
        `/site/forms/submissions${unreadOnly ? "?unread_only=true" : ""}`,
      ),
    markRead: (submissionId: string) =>
      request<SiteFormSubmission>(baseUrl, "POST", `/site/forms/submissions/${submissionId}/read`),
  };
}
