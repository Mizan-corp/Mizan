/**
 * Applying a workspace's theme pack (ADR-010 D3): its tokens become the CSS variables every
 * screen already uses, for light and dark; plus fonts, corner radius, shadows and motion.
 * Themes are validated on the server (app/framework/manifest.py theme_problems); values are
 * checked again here before they reach a stylesheet.
 */
import { MotionGlobalConfig } from "motion/react";

export interface ThemeFontFile { family: string; src: string; weight?: string; style?: "normal" | "italic" }
export interface ThemePack {
  id: string;
  name?: string;
  colors: { light: Record<string, string>; dark: Record<string, string> };
  fonts?: { body?: string; display?: string; mono?: string; files?: ThemeFontFile[] };
  radius?: string;
  shadows?: "flat" | "soft" | "raised";
  motion?: "full" | "reduced" | "none";
  density?: "comfortable" | "compact";
  assets_base?: string;
}

const STYLE_ID = "mizan-theme";
// Where this app's API serves theme font files (the same address lib/api uses).
const API = ((import.meta.env.VITE_API_URL as string | undefined) ?? "/api").replace(/\/+$/, "");
const SAFE_VALUE = /^[#a-zA-Z0-9().,%/ -]{1,80}$/;
const SAFE_TOKEN = /^[a-z0-9-]{1,40}$/;
const SAFE_FAMILY = /^[A-Za-z0-9 \u0600-\u06FF-]{1,64}$/;
const SAFE_SRC = /^assets\/[A-Za-z0-9_.-]+\.(woff2|woff|ttf|otf)$/;
// A workspace's own font picks borrow files another pack ships (themes/service.family_files);
// those arrive as absolute paths under the public assets route.
const SAFE_ABS_SRC = /^\/themes\/assets\/files\/[a-z][a-z0-9_]{0,47}\/assets\/[A-Za-z0-9_.-]+\.(woff2|woff|ttf|otf)$/;
const SHADOWS: Record<string, [string, string, string]> = {
  flat: ["none", "none", "none"],
  soft: ["0 1px 2px rgb(0 0 0 / 0.05)", "0 4px 12px -2px rgb(0 0 0 / 0.08)", "0 12px 32px -4px rgb(0 0 0 / 0.12)"],
  raised: ["0 1px 3px rgb(0 0 0 / 0.12)", "0 6px 18px -3px rgb(0 0 0 / 0.16)", "0 18px 40px -6px rgb(0 0 0 / 0.22)"],
};
const FALLBACK_SANS = `"IBM Plex Sans Arabic", ui-sans-serif, system-ui, sans-serif`;

function tokens(map: Record<string, string> | undefined): string {
  return Object.entries(map ?? {})
    .filter(([k, v]) => SAFE_TOKEN.test(k) && typeof v === "string" && SAFE_VALUE.test(v))
    .map(([k, v]) => `--${k}: ${v};`)
    .join(" ");
}

const family = (name?: string) => (name && SAFE_FAMILY.test(name) ? `"${name}"` : null);

/** The stylesheet for a theme (exported for tests). `apiBase` serves its font files. */
export function themeCss(theme: ThemePack, apiBase: string): string {
  const shadows = SHADOWS[theme.shadows ?? "soft"] ?? SHADOWS.soft;
  const extra = [
    theme.radius && /^(0|\d(\.\d{1,3})?rem|\d{1,2}px)$/.test(theme.radius) ? `--radius: ${theme.radius};` : "",
    `--shadow-sm: ${shadows[0]}; --shadow-md: ${shadows[1]}; --shadow-lg: ${shadows[2]};`,
    family(theme.fonts?.body) ? `--font-sans: ${family(theme.fonts?.body)}, ${FALLBACK_SANS};` : "",
  ].join(" ");
  const parts = [
    `html[data-theme="workspace"] { ${tokens(theme.colors?.light)} ${extra} }`,
    `html.dark[data-theme="workspace"] { color-scheme: dark; ${tokens(theme.colors?.dark)} }`,
  ];
  const display = family(theme.fonts?.display);
  if (display) parts.push(`html[data-theme="workspace"] .font-display { font-family: ${display}, Georgia, serif; }`);
  const mono = family(theme.fonts?.mono);
  if (mono) parts.push(`html[data-theme="workspace"] .font-mono, html[data-theme="workspace"] code { font-family: ${mono}, ui-monospace, monospace; }`);
  const base = theme.assets_base && /^\/themes\/assets\/[A-Za-z0-9._/-]+\/$/.test(theme.assets_base) ? apiBase + theme.assets_base : null;
  for (const f of theme.fonts?.files ?? []) {
    const fam = family(f.family);
    const absolute = SAFE_ABS_SRC.test(f.src);
    if (!fam || (!absolute && (!base || !SAFE_SRC.test(f.src)))) continue;
    const weight = /^[1-9]00( [1-9]00)?$/.test(f.weight ?? "400") ? f.weight ?? "400" : "400";
    const style = f.style === "italic" ? "italic" : "normal";
    parts.unshift(`@font-face { font-family: ${fam}; src: url("${absolute ? apiBase + f.src : base + f.src}"); font-weight: ${weight}; font-style: ${style}; font-display: swap; }`);
  }
  return parts.join("\n");
}

/** Make `theme` the look of this app (null: back to the built-in default). */
export function applyTheme(theme: ThemePack | null | undefined, apiBase = API): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  let style = document.getElementById(STYLE_ID) as HTMLStyleElement | null;
  if (!theme?.colors) {
    style?.remove();
    root.removeAttribute("data-motion");
    MotionGlobalConfig.skipAnimations = false;
    return;
  }
  if (!style) {
    style = document.createElement("style");
    style.id = STYLE_ID;
    document.head.appendChild(style);
  }
  style.textContent = themeCss(theme, apiBase.replace(/\/+$/, ""));
  root.setAttribute("data-theme", "workspace");
  root.setAttribute("data-motion", theme.motion ?? "full");
  MotionGlobalConfig.skipAnimations = theme.motion === "none";
  // A theme's density is only a default: a user's own choice on the device wins.
  if (theme.density && !localStorage.getItem("mizan.density")) root.setAttribute("data-density", theme.density);
}
