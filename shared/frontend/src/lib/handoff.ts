/**
 * Session handoff between Mizan apps on different domains.
 *
 * The website (after onboarding) and the admin panel (impersonation) open the
 * system app already signed in by passing the access token in the URL fragment.
 * Fragments are never sent to servers or logged in access logs, and the system
 * app strips it from the address bar immediately on load.
 */
import { appUrl, type AppKind } from "@/lib/urls";

const KEY = "session";

export function openWithSession(app: AppKind, path: string, token: string): void {
  window.location.assign(`${appUrl(app, path)}#${KEY}=${encodeURIComponent(token)}`);
}

/** Read and remove a handed-off token from the current URL, if present. */
export function takeHandedOffSession(): string | null {
  const hash = window.location.hash.replace(/^#/, "");
  if (!hash) return null;
  const params = new URLSearchParams(hash);
  const token = params.get(KEY);
  if (!token) return null;
  params.delete(KEY);
  const rest = params.toString();
  const { pathname, search } = window.location;
  window.history.replaceState(window.history.state, "", `${pathname}${search}${rest ? `#${rest}` : ""}`);
  return token;
}
