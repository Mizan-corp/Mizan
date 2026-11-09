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

export const usePlans = () =>
  useQuery({
    queryKey: ["plans"],
    queryFn: () => api.get<{ plans: Plan[]; online_payment: boolean }>("/account/plans"),
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
  changePassword: (v: { current_password: string; new_password: string }) =>
    api.post<{ ok: boolean; workspace_logins_updated: number }>("/account/password", v),
  tourDone: () => api.post<Owner>("/account/tour-done"),
  createWorkspace: (v: { name: string; sector: string; scale: string; demo_data: boolean }) =>
    api.post<Workspace>("/account/workspaces", v),
  open: (id: string) => api.post<{ access_token: string; slug: string | null; username: string }>(`/account/workspaces/${id}/open`),
  checkout: (v: { id: string; plan: string; cycle: "monthly" | "annual" }) =>
    api.post<{ invoice: Invoice; checkout_url: string }>(`/account/workspaces/${v.id}/checkout`, { plan: v.plan, cycle: v.cycle }),
  invoice: (ref: string) => api.get<Invoice>(`/account/invoices/${encodeURIComponent(ref)}`),
};
