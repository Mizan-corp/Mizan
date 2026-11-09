/**
 * The owner's session, as the website knows it.
 *
 * The website, the app and the owner panel live on separate domains, so the
 * website keeps its own copy of the owner token: it gets it at signup, and from
 * the app's /login, which passes through /session on its way to the panel.
 * Signing out on either side clears both (see /signout here and in the panel).
 */
import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { OWNER_API_URL } from "@/lib/urls";

const KEY = "mizan.owner_session";
const listeners = new Set<() => void>();

export function saveOwnerSession(token: string): void {
  localStorage.setItem(KEY, token);
  listeners.forEach((l) => l());
}

export function clearOwnerSession(): void {
  localStorage.removeItem(KEY);
  listeners.forEach((l) => l());
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
};
const read = () => localStorage.getItem(KEY);

export function useOwnerToken(): string | null {
  return useSyncExternalStore(subscribe, read, () => null);
}

/** The signed-in owner, checked with the owner API; null when signed out or expired. */
export function useOwner(): { token: string; fullName: string } | null {
  const token = useOwnerToken();
  const q = useQuery({
    queryKey: ["owner-session", token],
    enabled: !!token,
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const res = await fetch(`${OWNER_API_URL}/account/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.status === 401) {
        clearOwnerSession();
        return null;
      }
      if (!res.ok) throw new Error(String(res.status));
      return (await res.json()) as { full_name: string };
    },
  });
  return token && q.data ? { token, fullName: q.data.full_name } : null;
}
