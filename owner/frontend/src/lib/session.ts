import { useAuth } from "@/stores/auth";
import { appUrl } from "@/lib/urls";

/**
 * The owner panel has no sign-in page: owners sign in on the app's /login,
 * which hands the session back here. `next` returns them to this page.
 */
let leaving = false;

export function goToSignIn(): void {
  if (leaving) return;
  leaving = true;
  const { pathname, search } = window.location;
  const here = `${pathname}${search}`;
  const next = here === "/" ? "" : `?next=${encodeURIComponent(here)}`;
  window.location.replace(appUrl("system", `/login${next}`));
}

/** Sign out here, then on the website (it keeps its own copy), ending on the app's /login. */
export function signOut(): void {
  leaving = true;
  window.location.replace(appUrl("website", "/signout?to=login"));
  useAuth.getState().logout();
}

/** /signout: the website's "Sign out" sends the owner here to clear this side too. */
export function handleSignOutRoute(): boolean {
  if (window.location.pathname !== "/signout") return false;
  leaving = true;
  useAuth.getState().logout();
  window.location.replace(appUrl("website", "/"));
  return true;
}
