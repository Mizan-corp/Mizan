/// <reference types="vite/client" />

/** The year the site was built: the footer's copyright, the same in the pre-rendered HTML and the app. */
declare const __BUILD_YEAR__: number;

interface ImportMetaEnv {
  /** Google Analytics 4 measurement ID (G-…). Empty: GA4 is off and no consent banner shows (ADR-016). */
  readonly VITE_GA4_ID?: string;
}
