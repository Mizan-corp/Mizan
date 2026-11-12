import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { openWithSession, takeHandedOffSession } from "@/lib/handoff";
import { appUrl } from "@/lib/urls";
import { clearOwnerSession, saveOwnerSession } from "@app/lib/ownerSession";

const safePath = (raw: string | null) => (raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/");

// Read once at load: the handoff is consumed from the address bar on first read.
const handedOff = window.location.pathname === "/session" ? takeHandedOffSession() : null;

/** The app's /login passes the owner session through here on its way to the owner panel. */
export function AdoptSession() {
  const navigate = useNavigate();
  useEffect(() => {
    const token = handedOff;
    if (!token) {
      navigate("/", { replace: true });
      return;
    }
    saveOwnerSession(token);
    openWithSession("owner", safePath(new URLSearchParams(window.location.search).get("next")), token);
  }, [navigate]);
  return null;
}

/**
 * Sign the owner out of the website. `?to=login` comes from the owner panel's
 * sign-out (it has already cleared its own session) and ends on the app's /login.
 */
export function SignOut() {
  const navigate = useNavigate();
  useEffect(() => {
    clearOwnerSession();
    if (new URLSearchParams(window.location.search).get("to") === "login") {
      window.location.replace(appUrl("owner", "/login"));
    } else {
      navigate("/", { replace: true });
    }
  }, [navigate]);
  return null;
}

/** Sign out everywhere from the website: here, then the owner panel, which comes back to "/". */
export function signOutEverywhere(): void {
  clearOwnerSession();
  window.location.assign(appUrl("owner", "/signout"));
}
