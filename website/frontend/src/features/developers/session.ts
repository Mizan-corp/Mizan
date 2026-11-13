/**
 * The developer's portal session (ADR-007 D5), kept apart from the owner's: a developer account
 * is separate from an owner account, and one person may have both.
 */
import { useSyncExternalStore } from "react";
import { useQuery } from "@tanstack/react-query";
import { devIsArabic } from "./i18n";

const KEY = "mizan.developer_session";
const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? "/api").replace(/\/+$/, "");
const listeners = new Set<() => void>();

export function saveDeveloperSession(token: string): void {
  localStorage.setItem(KEY, token);
  listeners.forEach((l) => l());
}

export function clearDeveloperSession(): void {
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

export function useDeveloperToken(): string | null {
  return useSyncExternalStore(subscribe, read, () => null);
}

export class PortalError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** A call to the developer API (/developers…) with the portal session. A Blob body (a package) is sent as is. */
export async function portal<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = read();
  const ar = devIsArabic();
  const raw = body instanceof Blob;
  const headers: Record<string, string> = { Accept: "application/json", "Accept-Language": ar ? "ar" : "en" };
  if (body !== undefined) headers["Content-Type"] = raw ? "application/octet-stream" : "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${BASE}/developers${path}`, {
      method, headers, body: body === undefined ? undefined : raw ? body : JSON.stringify(body),
    });
  } catch {
    throw new PortalError(0, ar ? "تعذر الاتصال بالخادم، تحقق من الإنترنت" : "Couldn't reach Mizan; check your connection");
  }
  if (res.status === 401 && token && !path.startsWith("/login")) clearDeveloperSession();
  if (!res.ok) {
    let detail = ar ? "حدث خطأ غير متوقع" : "Something went wrong";
    try {
      const j = await res.json();
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail)) detail = ar ? "تحقق من البيانات المدخلة" : "Check what you entered";
    } catch {
      /* not JSON */
    }
    throw new PortalError(res.status, detail);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export interface Team { id: string; handle: string; name: string; role: "owner" | "member"; created_at: string | null }
export interface Me { id: string; email: string; full_name: string; teams: Team[] }

/** The signed-in developer; undefined while loading, null when signed out. */
export function useDeveloper() {
  const token = useDeveloperToken();
  const q = useQuery({
    queryKey: ["developer-me", token],
    enabled: !!token,
    retry: false,
    queryFn: () => portal<Me>("GET", "/me"),
  });
  return { token, me: token ? q.data : null, query: q };
}

export async function signOutDeveloper(): Promise<void> {
  try {
    await portal("POST", "/logout");
  } catch {
    /* already gone */
  }
  clearDeveloperSession();
}
