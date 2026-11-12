import { signOutSession } from "@/lib/api";
import { appUrl } from "@/lib/urls";

/**
 * Owners sign in on this panel's /login (ADR-008); `next` returns them to the page they were on.
 * Paths here are inside the panel (its base, /owner/ on the one domain, is added by the router).
 */
let leaving = false;
const BASE = import.meta.env.BASE_URL.replace(/\/+$/, "");
const inPanel = (path: string) => path.startsWith(BASE) ? path.slice(BASE.length) || "/" : path;

export function goToSignIn(): void {
  if (leaving) return;
  leaving = true;
  const { pathname, search } = window.location;
  const here = `${inPanel(pathname)}${search}`;
  const next = here === "/" ? "" : `?next=${encodeURIComponent(here)}`;
  window.location.replace(appUrl("owner", `/login${next}`));
}

/** Sign out here, then on the website (it keeps its own copy), ending on the sign-in page. */
export function signOut(): void {
  leaving = true;
  signOutSession("/account/logout"); // ends the token on the server, so the website's copy too (#77)
  window.location.replace(appUrl("website", "/signout?to=login"));
}

/** /signout: the website's "Sign out" sends the owner here to clear this side too. */
export function handleSignOutRoute(): boolean {
  if (inPanel(window.location.pathname) !== "/signout") return false;
  leaving = true;
  signOutSession("/account/logout");
  window.location.replace(appUrl("website", "/"));
  return true;
}
