import { useSyncExternalStore } from "react";
import { GA4_ID, loadGa4, stopGa4 } from "./ga4";

/** The visitor's answer about Google Analytics, kept in this browser only. */
export type Consent = "granted" | "denied" | null;

const KEY = "mizan.analytics_consent";
const listeners = new Set<() => void>();
let reopened = false;

function read(): Consent {
  try {
    const v = localStorage.getItem(KEY);
    return v === "granted" || v === "denied" ? v : null;
  } catch {
    return null;
  }
}

export function setConsent(value: "granted" | "denied"): void {
  try {
    localStorage.setItem(KEY, value);
  } catch {
    /* private mode: the answer lasts for this page */
  }
  reopened = false;
  if (value === "granted") loadGa4();
  else stopGa4();
  listeners.forEach((l) => l());
}

/** "Privacy settings" in the footer: show the banner again. */
export function reopenConsent(): void {
  reopened = true;
  listeners.forEach((l) => l());
}

/** Applies a choice made on an earlier visit. */
export function startAnalyticsConsent(): void {
  if (GA4_ID && read() === "granted") loadGa4();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

/** Whether the banner should show: GA4 is configured and the visitor hasn't answered (or asked again). */
export function useConsentBanner(): { open: boolean; consent: Consent } {
  const consent = useSyncExternalStore(subscribe, read, () => "denied" as Consent);
  const open = useSyncExternalStore(subscribe, () => !!GA4_ID && (reopened || read() === null), () => false);
  return { open, consent };
}

export const ANALYTICS_CONFIGURABLE = !!GA4_ID;
