import { create } from "zustand";

export type Role = "admin" | "manager" | "cashier" | "storekeeper" | "accountant" | "superadmin";

export interface User {
  id: string;
  username: string;
  full_name: string;
  role: Role;
  permissions: string[];
  is_manager: boolean;
  is_superadmin?: boolean;
  tenant_id?: string | null;
  default_warehouse_id: string | null;
}

export interface LoginConfig {
  company_name?: string;
  logo_url?: string;
  login_title?: string;
  login_subtitle?: string;
  cover_url?: string;
  support_contact?: string;
  primary_color?: string;
  show_powered_by?: boolean;
}

export interface TenantInfo {
  id: string;
  name: string;
  logo_url?: string;
  slug?: string | null;
  custom_domain?: string | null;
  sector: string;
  business_type?: string;
  primary_route?: string | null;
  scale: string;
  palette: { name?: string; hue?: number };
  features: string[];
  active_modules?: string[];
  plan: string;
  trial_ends_at: string | null;
  deployment_mode?: string;
  tech_stack?: Record<string, unknown>;
  limits?: Record<string, unknown>;
  login_config?: LoginConfig;
}

interface AuthState {
  token: string | null;
  user: User | null;
  tenant: TenantInfo | null;
  setTenant: (t: TenantInfo | null) => void;
  login: (token: string, user: User) => void;
  setToken: (token: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
  can: (perm: string) => boolean;
}

const KEY = "mizan.session";
const LEGACY_KEY = "vendora.session";
const TENANT_KEY = "mizan.tenant";
const LEGACY_TENANT_KEY = "vendora.tenant";
// Kept after sign-out, so a signed-out employee is sent back to their workspace's sign-in page
// rather than the owners' /login (#78).
const LAST_WORKSPACE_KEY = "mizan.last_workspace";

export function lastWorkspaceSlug(): string | null {
  try {
    return localStorage.getItem(LAST_WORKSPACE_KEY);
  } catch {
    return null;
  }
}

function persist(token: string | null, user: User | null, tenant: TenantInfo | null) {
  if (token) {
    localStorage.setItem(KEY, JSON.stringify({ token, user, tenant }));
  } else {
    localStorage.removeItem(KEY);
    localStorage.removeItem(LEGACY_KEY);
  }
}

/** Apply the tenant's chosen brand hue to the document (onboarding wizard option). */
export function applyBrandHue(hue?: number) {
  if (hue && Number.isFinite(hue)) {
    document.documentElement.style.setProperty("--brand-hue", String(Math.round(hue)));
  }
}

function load(): { token: string | null; user: User | null } {
  try {
    const raw = localStorage.getItem(KEY) ?? localStorage.getItem(LEGACY_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* corrupted session — start fresh */
  }
  return { token: null, user: null };
}

export const useAuth = create<AuthState>((set, get) => ({
  ...load(),
  tenant: null,
  setTenant: (tenant) => {
    set({ tenant });
    applyBrandHue(tenant?.palette?.hue);
    if (tenant) {
      localStorage.setItem(TENANT_KEY, JSON.stringify(tenant));
      if (tenant.slug && tenant.slug !== "undefined" && tenant.slug !== "null") {
        localStorage.setItem(LAST_WORKSPACE_KEY, tenant.slug);
      }
    } else {
      localStorage.removeItem(TENANT_KEY);
      localStorage.removeItem(LEGACY_TENANT_KEY);
    }
  },
  login: (token, user) => {
    persist(token, user, get().tenant);
    set({ token, user });
  },
  setToken: (token) => {
    persist(token, get().user, get().tenant);
    set({ token });
  },
  setUser: (user) => {
    const token = get().token;
    if (token) localStorage.setItem(KEY, JSON.stringify({ token, user }));
    set({ user });
  },
  logout: () => {
    localStorage.removeItem(KEY);
    localStorage.removeItem(LEGACY_KEY);
    localStorage.removeItem(TENANT_KEY);
    localStorage.removeItem(LEGACY_TENANT_KEY);
    set({ token: null, user: null, tenant: null });
  },
  /** Permissions decide, never role names. "a|b" means either one. */
  can: (perm) => {
    const u = get().user;
    if (!u) return false;
    if (u.is_superadmin) return true;
    if (!perm) return true;
    const perms = Array.isArray(u.permissions) ? u.permissions : [];
    return perms.includes("*") || perm.split("|").some((p) => perms.includes(p));
  },
}));
