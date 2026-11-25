import { useAuth } from "@/stores/auth";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ─── Types (mirror owner/backend/owner_api) ────────────────────────────────

export interface Owner {
  id: string;
  login: string;
  full_name: string;
  email: string | null;
  /** The address was proved with a code (#72); receipts, reminders and password reset use it. */
  email_verified: boolean;
  /** Whether this server can send email at all. */
  email_service: boolean;
  phone: string | null;
  tour_done: boolean;
  created_at: string | null;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string | null;
  sector: string;
  /** A developer's activity's name (ADR-012); Mizan's activities are named by sectorLabel. */
  sector_name?: string | null;
  status: "active" | "suspended" | string;
  plan: string;
  monthly_price_egp: number;
  trial_ends_at: string | null;
  trial_days_left: number | null;
  paid_until: string | null;
  users_count: number;
  last_sale_at: string | null;
  created_at: string | null;
  deployment_mode: DeploymentMode;
  licence: LicenceSummary | null;
  /** The workspace's branding: {name: theme id, hue, palette?: independent palette id, fonts?: {body, display}}. */
  palette?: { name?: string; palette?: string; fonts?: { body?: string; display?: string } };
}

export interface BrandingProfile {
  id: string;
  name: string;
  theme: string;
  palette: string | null;
  fonts: { body?: string; display?: string };
}

export type DeploymentMode = "cloud_saas" | "desktop" | "lan";

export interface LicenceSummary {
  status: "active" | "expired" | "revoked" | "none";
  valid_until: string | null;
  installations: number;
  last_seen_at: string | null;
}

export interface Installation {
  id: string;
  mode: string;
  hostname: string | null;
  os: string | null;
  app_version: string | null;
  /** A newer release for this computer's system (#89). */
  update_to?: string | null;
  /** The computer the licence runs on (#92). */
  licensed?: boolean;
  first_seen_at: string | null;
  last_seen_at: string | null;
  last_backup_at: string | null;
}

export interface Download {
  licence_key: string;
  valid_until: string;
  status: LicenceSummary["status"];
  mode: DeploymentMode;
  installers: { platform: "windows" | "linux"; url: string; version: string | null; size_mb: number | null }[];
}

export interface Quota {
  used: number;
  max: number;
  percentage: number;
}

export interface Invoice {
  ref: string;
  workspace_id: string;
  workspace_name: string | null;
  plan: string;
  cycle: "monthly" | "annual" | string;
  amount_egp: number;
  method: string;
  status: string;
  period_start: string | null;
  period_end: string | null;
  paid_at: string | null;
  created_at: string | null;
}

export interface WorkspaceDetail {
  workspace: Workspace;
  quotas: { users: Quota; branches: Quota; monthly_sales: Quota };
  installations: Installation[];
  is_read_only: boolean;
  invoices: Invoice[];
}

export interface Plan {
  id: string;
  name: string;
  name_en: string;
  price_monthly_egp: number;
  price_annual_egp: number;
  max_users: number;
  max_branches: number;
  max_monthly_sales: number;
  popular: boolean;
  features: string[];
}

// ─── Queries ───────────────────────────────────────────────────────────────

export const useMe = (enabled = true) =>
  useQuery({ queryKey: ["me"], queryFn: () => api.get<Owner>("/account/me"), enabled, retry: false, staleTime: 60_000 });

export const useWorkspaces = () =>
  useQuery({ queryKey: ["workspaces"], queryFn: () => api.get<{ items: Workspace[] }>("/account/workspaces") });

export const useWorkspace = (id: string) =>
  useQuery({ queryKey: ["workspace", id], queryFn: () => api.get<WorkspaceDetail>(`/account/workspaces/${id}`) });

/** A workspace's storage against its plan, analysed by module (ADR-006 D3). */
export interface StorageUsage {
  used_bytes: number;
  limit_bytes: number;
  percent: number;
  state: "ok" | "warn" | "full";
  measured_at: string;
  by_module: { module: string; name: string; bytes: number; rows: number; kept: boolean }[];
}

export const useStorage = (id: string, refresh = false) =>
  useQuery({
    queryKey: ["storage", id, refresh],
    queryFn: () => api.get<StorageUsage>(`/account/workspaces/${id}/storage`, refresh ? { refresh: "true" } : undefined),
  });

/** card / wallet: chosen in the panel; "any": Paymob's page offers every method. */
export type PaymentMethod = "card" | "wallet" | "any";

export interface PlansResponse {
  plans: Plan[];
  online_payment: boolean;
  payment_methods: PaymentMethod[];
  /** Production running against Paymob's test mode (only listed owners can pay). */
  test_mode: boolean;
}

export const usePlans = () =>
  useQuery({
    queryKey: ["plans"],
    queryFn: () => api.get<PlansResponse>("/account/plans"),
    staleTime: Infinity,
  });

export const useInvoices = () => useQuery({ queryKey: ["invoices"], queryFn: () => api.get<{ items: Invoice[] }>("/account/invoices") });
export const useBrandingProfiles = () =>
  useQuery({ queryKey: ["branding-profiles"], queryFn: () => api.get<{ items: BrandingProfile[] }>("/account/branding-profiles") });

/** What paying for a plan now costs and when it runs (#68): shown before sending the owner to Paymob. */
export interface CheckoutQuote {
  /** new: starts now · renewal/downgrade: starts when the paid time ends · upgrade: starts now, unused paid time as extra days */
  kind: "new" | "renewal" | "upgrade" | "downgrade";
  plan: string;
  cycle: "monthly" | "annual";
  amount_egp: number;
  period_start: string;
  period_end: string;
  credit_egp: number;
  credit_days: number;
  current_plan: string;
  current_paid_until: string | null;
}

/** Changing a workspace's activity (#107): asked here, decided by the Mizan team. */
export interface ActivityChange {
  id: string;
  from: { id: string; name: string };
  to: { id: string; name: string };
  data_mode: "keep" | "delete";
  status: "requested" | "applied" | "rejected" | "cancelled";
  note: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
}

interface ModuleRef {
  id: string;
  name: string;
}

export interface ActivityPreview {
  from: { id: string; name: string };
  to: { id: string; name: string };
  leaving: ModuleRef[];
  joining: ModuleRef[];
  staying: ModuleRef[];
  variants_changed: (ModuleRef & { from: string; to: string })[];
  /** Leaving modules that hold records; core ERP data (kept_always) is never deleted. */
  data: (ModuleRef & { rows: number; kept_always: boolean })[];
  keep_days: number;
  theme: { from: string | null; to: string } | null;
  /** A developer's activity (ADR-012): its own modules, what they may access, its themes. */
  own_joining: OwnModule[];
  own_leaving: (OwnModule & { rows?: number })[];
  package: { developer: string; version: string; themes: { id: string; name: string }[] } | null;
}

export interface OwnModule {
  id: string;
  name: string;
  entities: string[];
  scopes: { id: string; text: string }[];
  sends_to: string | null;
}

/** A developer's activity a workspace can change to (ADR-012). */
export interface DeveloperActivity {
  id: string;
  name: string;
  name_en: string;
  description: string | null;
  family: string;
  developer: string;
  version: string;
}

export const useDeveloperActivities = (enabled: boolean) =>
  useQuery({
    queryKey: ["developer-activities"],
    queryFn: () => api.get<{ items: DeveloperActivity[] }>("/account/activities/developers"),
    enabled,
    staleTime: 60_000,
  });

export const useActivityChange = (id: string) =>
  useQuery({
    queryKey: ["activity-change", id],
    queryFn: () => api.get<{ change: ActivityChange | null }>(`/account/workspaces/${id}/activity-change`),
  });

export const useActivityPreview = (id: string, to: string) =>
  useQuery({
    queryKey: ["activity-preview", id, to],
    queryFn: () => api.get<ActivityPreview>(`/account/workspaces/${id}/activity-change/preview`, { to }),
    enabled: !!to,
    retry: false,
  });

export const useCheckoutQuote = (id: string, plan: string, cycle: "monthly" | "annual") =>
  useQuery({
    queryKey: ["quote", id, plan, cycle],
    queryFn: () => api.get<CheckoutQuote>(`/account/workspaces/${id}/checkout/quote`, { plan, cycle }),
    staleTime: 0,
  });

// ─── Mutations ─────────────────────────────────────────────────────────────

/** A mutation that refreshes the panel's data when it succeeds. */
export function useAction<TVars, TResult = unknown>(fn: (vars: TVars) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries() });
}

export const actions = {
  updateMe: (v: { full_name?: string; email?: string; phone?: string }) => api.patch<Owner>("/account/me", v),
  // Ends every other session (#77); this one continues with the fresh token, stored before the
  // queries refetch.
  changePassword: async (v: { current_password: string; new_password: string }) => {
    const r = await api.post<{ ok: boolean; workspace_logins_updated: number; access_token?: string }>("/account/password", v);
    if (r.access_token) useAuth.getState().setToken(r.access_token);
    return r;
  },
  tourDone: () => api.post<Owner>("/account/tour-done"),
  sendEmailCode: () => api.post<{ ok: boolean; to?: string; already?: boolean }>("/account/email/send-code"),
  verifyEmail: (code: string) => api.post<Owner>("/account/email/verify", { code }),
  createWorkspace: (v: { name: string; sector: string; scale: string; demo_data: boolean; mode: DeploymentMode }) =>
    api.post<Workspace>("/account/workspaces", v),
  download: (id: string) => api.get<Download>(`/account/workspaces/${id}/download`),
  open: (id: string) => api.post<{ access_token: string; slug: string | null; username: string }>(`/account/workspaces/${id}/open`),
  checkout: (v: { id: string; plan: string; cycle: "monthly" | "annual"; method?: "card" | "wallet"; wallet_number?: string }) =>
    api.post<{ invoice: Invoice; checkout_url: string }>(`/account/workspaces/${v.id}/checkout`, {
      plan: v.plan,
      cycle: v.cycle,
      method: v.method,
      wallet_number: v.wallet_number,
    }),
  invoice: (ref: string) => api.get<Invoice>(`/account/invoices/${encodeURIComponent(ref)}`),
  askActivityChange: (v: { id: string; to: string; data_mode: "keep" | "delete"; note?: string }) =>
    api.post<{ change: ActivityChange }>(`/account/workspaces/${v.id}/activity-change`, { to: v.to, data_mode: v.data_mode, note: v.note }),
  cancelActivityChange: (id: string) => api.del(`/account/workspaces/${id}/activity-change`),
  updateWorkspace: (v: { id: string; name?: string; slug?: string }) =>
    api.patch<WorkspaceDetail>(`/account/workspaces/${v.id}`, { name: v.name, slug: v.slug }),
  moveLicence: (v: { id: string; installation: string }) =>
    api.post<WorkspaceDetail>(`/account/workspaces/${v.id}/installations/${v.installation}/licence`),
  deleteWorkspace: (v: { id: string, confirm: string }) =>
    api.del(`/account/workspaces/${v.id}?confirm=${encodeURIComponent(v.confirm)}`),
  saveBrandingProfile: (v: { name: string; theme: string; palette?: string | null; fonts?: { body?: string; display?: string } }) =>
    api.post<BrandingProfile>("/account/branding-profiles", v),
  applyBrandingProfile: (v: { profile: string; workspace: string }) =>
    api.post<{ profile: BrandingProfile }>(`/account/branding-profiles/${v.profile}/apply/${v.workspace}`),
  deleteBrandingProfile: (id: string) => api.del(`/account/branding-profiles/${id}`),
};
