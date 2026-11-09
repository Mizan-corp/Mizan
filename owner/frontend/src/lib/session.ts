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

export function signOut(): void {
  leaving = true;
  window.location.replace(appUrl("system", "/login"));
  useAuth.getState().logout();
}
