/**
 * The wizard's link to Mizan Setup (Rust). Outside Tauri (a normal browser, for
 * design work) a simulated install runs instead.
 */
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

export interface Licence {
  lid: string;
  mode: "desktop" | "lan";
  plan: string;
  valid_until: string;
  workspace: { id: string; name: string; slug: string | null; sector: string };
  owner: { login: string; full_name: string } | null;
}

export interface SetupInfo {
  version: string;
  platform: "windows" | "linux";
  is_admin: boolean;
  install_dir: string;
  found: { key: string; source: "stamp" | "file" | "downloads" | "clipboard"; file: string | null } | null;
  licence: Licence | null;
  installed: { mode: string; http_port: number; tls: boolean; data_dir: string } | null;
  has_payload: boolean;
}

export interface Progress {
  step: string;
  status: "running" | "progress" | "done" | "skipped" | "error";
  message?: string;
  done?: number;
  total?: number;
  [k: string]: unknown;
}

export interface Summary {
  url: string;
  mode: "desktop" | "lan";
  workspace: string;
  admin: string;
  addresses: string[];
  ca_certificate: string | null;
  data_dir: string;
}

export interface InstallOptions {
  licence: string;
  admin_password: string;
  admin_username?: string;
  install_dir: string;
  port?: number;
  demo: boolean;
  extra_args?: string[];
}

export const IN_TAURI = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

// ─── Simulation (browser only) ─────────────────────────────────────────────

const sample: Licence = {
  lid: "demo",
  mode: (new URLSearchParams(location.search).get("mode") as "lan") ?? "desktop",
  plan: "pro",
  valid_until: new Date(Date.now() + 360 * 86400_000).toISOString(),
  workspace: { id: "x", name: "صيدلية الأمل", slug: "al-amal", sector: "pharmacy" },
  owner: { login: "nour", full_name: "نور حسن" },
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function simulate(onProgress: (p: Progress) => void): Promise<Summary> {
  for (let i = 0; i <= 10; i++) {
    onProgress({ step: "extract", status: i === 0 ? "running" : "progress", done: i * 120, total: 1200 });
    await sleep(120);
  }
  onProgress({ step: "extract", status: "done" });
  for (const step of ["check", "prepare", "database", "workspace", "network", "service", "start"]) {
    onProgress({ step, status: "running" });
    await sleep(step === "workspace" ? 1400 : 500);
    onProgress({ step, status: sample.mode === "desktop" && step === "network" ? "skipped" : "done" });
  }
  const lan = sample.mode === "lan";
  return {
    url: lan ? "https://mizan.local" : "http://localhost:47800",
    mode: sample.mode,
    workspace: sample.workspace.name,
    admin: "nour",
    addresses: lan ? ["https://192.168.1.20", "https://mizan.local"] : [],
    ca_certificate: lan ? "C:\\ProgramData\\Mizan\\tls\\mizan-ca.crt" : null,
    data_dir: "C:\\ProgramData\\Mizan",
  };
}

// ─── API ───────────────────────────────────────────────────────────────────

export async function setupInfo(): Promise<SetupInfo> {
  if (!IN_TAURI) {
    const found = new URLSearchParams(location.search).get("nolicence") === null;
    return {
      version: "1.0.0",
      platform: "windows",
      is_admin: false,
      install_dir: "C:\\Program Files\\Mizan",
      found: found ? { key: "MZN1.demo.demo", source: "downloads", file: "Mizan-al-amal.mzn" } : null,
      licence: found ? sample : null,
      installed: null,
      has_payload: true,
    };
  }
  return invoke<SetupInfo>("setup_info");
}

export async function readLicence(input: { text?: string; path?: string }): Promise<{ key: string; licence: Licence }> {
  if (!IN_TAURI) {
    if (!input.text?.includes("MZN1.")) throw new Error("هذا ليس مفتاح ترخيص ميزان. انسخه من لوحة المالك (زر «تنزيل»).");
    return { key: input.text, licence: sample };
  }
  return invoke("read_licence", { text: input.text ?? null, path: input.path ?? null });
}

export async function runInstall(options: InstallOptions, onProgress: (p: Progress) => void): Promise<Summary> {
  if (!IN_TAURI) return simulate(onProgress);
  const unlisten = await listen<Progress>("install-progress", (e) => onProgress(e.payload));
  try {
    return await invoke<Summary>("run_install", { options });
  } finally {
    unlisten();
  }
}

export async function openMizan(url: string, desktop: boolean): Promise<void> {
  if (!IN_TAURI) {
    window.open(url, "_blank");
    return;
  }
  await invoke("open_mizan", { url, desktop });
}

export async function openPath(path: string): Promise<void> {
  if (IN_TAURI) await invoke("open_path", { path });
}

export async function pickLicenceFile(): Promise<string | null> {
  if (!IN_TAURI) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const picked = await open({ multiple: false, filters: [{ name: "Mizan licence", extensions: ["mzn", "txt"] }] });
  return typeof picked === "string" ? picked : null;
}
