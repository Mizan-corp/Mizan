import { useAuth } from "@/stores/auth";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

// ─── Types (mirror owner/backend/owner_api) ────────────────────────────────

export interface Owner {
  id: string;
  login: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  tour_done: boolean;
  created_at: string | null;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string | null;
  sector: string;
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
  updateWorkspace: (v: { id: string; name?: string; slug?: string }) =>
    api.patch<WorkspaceDetail>(`/account/workspaces/${v.id}`, { name: v.name, slug: v.slug }),
  deleteWorkspace: (v: { id: string; confirm: string }) =>
    api.del(`/account/workspaces/${v.id}?confirm=${encodeURIComponent(v.confirm)}`),
};
