import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";

// ─── Types (mirror admin/backend/admin_api) ─────────────────────────────────

export interface ActivityItem {
  id: string;
  action: string;
  at: string;
  actor: string | null;
  tenant_id: string | null;
  tenant_name: string | null;
  details: Record<string, unknown>;
  ip: string | null;
}

export type AttentionItem =
  | { kind: "trial_expired" | "trial_ending" | "paid_ended" | "paid_ending"; tenant_id: string; tenant_name: string; days: number; at: string }
  | { kind: "invoice_pending"; tenant_id: string; tenant_name: string | null; ref: string; amount_egp: number; plan: string; at: string }
  | { kind: "activity_change"; tenant_id: string; tenant_name: string | null; change_id: string; from_activity: string; to_activity: string; from_name?: string | null; to_name?: string | null; at: string }
  | { kind: "marketplace_review"; tenant_id: string; tenant_name: null; version_id: string; item_id: string; version: string; item_kind: "community" | "theme" | "activity"; name: string | null; at: string }

/** An owner's request to change a workspace's activity (#107), with what it does today. */
export interface ActivityChange {
  id: string;
  tenant_id: string;
  tenant_name: string | null;
  from: { id: string; name: string };
  to: { id: string; name: string };
  data_mode: "keep" | "delete";
  status: "requested" | "applied" | "rejected" | "cancelled";
  note: string | null;
  decision_note: string | null;
  created_at: string;
  preview?: {
    leaving: { id: string; name: string; name_en: string }[];
    joining: { id: string; name: string; name_en: string }[];
    variants_changed: { id: string; name: string; name_en: string; from: string; to: string }[];
    data: { id: string; name: string; name_en: string; rows: number; kept_always: boolean }[];
    keep_days: number;
    theme: { from: string | null; to: string } | null;
    own_joining: OwnModule[];
    own_leaving: (OwnModule & { rows?: number })[];
    package: { developer: string; version: string; themes: { id: string; name: string }[] } | null;
  };
  preview_error?: string;
}

/** A developer's activity's own module (ADR-012). */
export interface OwnModule {
  id: string;
  name: string;
  name_en: string;
  entities: string[];
  scopes: { id: string; text: string; text_en: string }[];
  sends_to: string | null;
}

export const useActivityChange = (id: string, enabled = true) =>
  useQuery({ queryKey: ["activity-change", id], queryFn: () => api.get<ActivityChange>(`/admoon/activity-changes/${id}`), enabled });

/** A developer's package version sent to the marketplace (#105). */
export interface Submission {
  id: string;
  item_id: string;
  version: string;
  kind: "community" | "theme" | "activity";
  status: "in_review" | "approved" | "rejected" | "withdrawn";
  name: string | null;
  name_en: string | null;
  size: number;
  sha256: string;
  developer: string;
  submitted_at: string;
  reviewed_at: string | null;
  review_note: string | null;
}

export interface SubmissionDetail extends Submission {
  manifest: Record<string, unknown> & { description?: string; permissions?: { id: string; name: string; name_en: string }[] };
  files: { name: string; size: number }[];
  listed_version: string | null;
  verify_error?: string;
  summary?: {
    entities: { id: string; name: string; fields: number }[];
    scopes: { id: string; text: string; text_en: string; new?: boolean }[];
    sends_to: string | null;
  };
  theme?: { swatches: string[]; fonts: { body?: string; display?: string }; radius?: string; motion?: string };
  /** An activity package (ADR-012): what it brings, and how many workspaces run it now. */
  activity?: {
    family: string; home: string | null; theme: string | null;
    modules: { id: string; name: string }[]; optional: { id: string; name: string }[];
    own_modules: { id: string; name: string; entities: number; scopes: string[]; sends_to: string | null }[];
    variants: { module: string; fields: number; terms: number; settings: number }[];
    themes: { id: string; name: string }[]; positions: string[]; menu_groups: number; seed_records: number;
  };
  workspaces?: number;
}

/** A marketplace listing: its current approved version. */
export interface Listing {
  id: string;
  kind: "community" | "theme" | "activity";
  name: string;
  name_en: string | null;
  description: string | null;
  version: string;
  status: "listed" | "delisted";
  status_note: string | null;
  installs: number;
  developer: string | null;
  updated_at: string | null;
}

export const useSubmissions = (status: string) =>
  useQuery({ queryKey: ["marketplace-submissions", status], queryFn: () => api.get<{ items: Submission[] }>("/admoon/marketplace/submissions", { status }) });
export const useSubmission = (id: string, enabled = true) =>
  useQuery({ queryKey: ["marketplace-submission", id], queryFn: () => api.get<SubmissionDetail>(`/admoon/marketplace/submissions/${id}`), enabled });
export const useListings = () =>
  useQuery({ queryKey: ["marketplace-items"], queryFn: () => api.get<{ items: Listing[] }>("/admoon/marketplace/items") });

export interface Revenue {
  mrr_egp: number;
  paying: number;
  complimentary: number;
}

export interface Overview {
  counts: { workspaces: number; active: number; on_trial: number; paying: number; suspended: number; users: number };
  revenue: Revenue;
  signups: { week: string; count: number }[];
  signups_last_30_days: number;
  attention: AttentionItem[];
  newest: { id: string; name: string; sector: string; plan: string; created_at: string }[];
  activity: ActivityItem[];
}

export interface WorkspaceSummary {
  id: string;
  name: string;
  slug: string | null;
  sector: string;
  status: "active" | "suspended" | string;
  plan: string;
  monthly_price_egp: number;
  trial_ends_at: string | null;
  trial_days_left: number | null;
  created_at: string;
  deployment_mode: "cloud_saas" | "desktop" | "lan";
}

export interface WorkspaceRow extends WorkspaceSummary {
  users_count: number;
  sales_count: number;
  sales_volume_egp: number;
  last_sale_at: string | null;
}

export interface Invoice {
  ref: string;
  plan: string;
  cycle: string;
  amount_egp: number;
  status: string;
  method: string;
  /** Started as a Paymob checkout: it can be checked with Paymob (#67). */
  paymob?: boolean;
  created_at: string;
  paid_at: string | null;
  tenant_id?: string;
  tenant_name?: string | null;
}

export interface OwnerRow {
  id: string;
  login: string;
  full_name: string;
  email: string | null;
  /** Proved with a code (#72): reset codes, receipts and reminders go only to a verified address. */
  email_verified: boolean;
  phone: string | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  workspace_count: number;
  paid_egp: number;
}
export interface OwnerDetail extends OwnerRow {
  workspaces: { id: string; name: string; slug: string | null; plan: string; status: string; deployment_mode: string }[];
}

export interface WorkspaceDetail {
  workspace: WorkspaceSummary & { scale: string; active_modules: string[]; limits: Record<string, unknown>; system_path: string | null };
  owner: { id: string; username: string; full_name: string } | null;
  /** The owner account (#73): signs in to the owner panel and pays. */
  owner_account: Pick<OwnerRow, "id" | "login" | "full_name" | "email" | "phone" | "is_active" | "last_login_at"> | null;
  stats: { users: number; branches: number; products: number; sales: number; sales_volume_egp: number; last_sale_at: string | null };
  users: { id: string; username: string; full_name: string; role: string; is_active: boolean; created_at: string }[];
  branches: { id: string; name: string; is_active: boolean }[];
  invoices: Invoice[];
  activity: ActivityItem[];
  licence: { id: string; mode: string; status: "active" | "expired" | "revoked"; valid_until: string; revoked_at: string | null } | null;
  installations: {
    id: string;
    hostname: string | null;
    os: string | null;
    app_version: string | null;
    update_to?: string | null;
    licensed?: boolean;
    last_ip: string | null;
    first_seen_at: string | null;
    last_seen_at: string | null;
    last_backup_at: string | null;
  }[];
}

export interface Module {
  id: string;
  name: string;
  name_en: string;
  category: string;
}

export interface Billing {
  summary: Revenue & { pending_count: number; pending_egp: number; collected_this_month_egp: number };
  invoices: Invoice[];
}

export interface Person {
  id: string;
  username: string;
  full_name: string;
  is_active: boolean;
  workspace: string | null;
  created_at: string;
  last_action_at: string | null;
  is_staff: boolean;
}

export interface SystemHealth {
  database: {
    version: string;
    size_mb: number;
    connections: number;
    max_connections: number;
    latency_ms: number;
    tables: number;
    tenant_tables_without_rls: number;
  };
  migrations: { total: number; applied: number; pending: string[] };
  records: Record<string, number>;
  service: { environment: string; python: string; uptime_seconds: number; host: string };
}

// ─── Queries ───────────────────────────────────────────────────────────────

export const useOverview = () => useQuery({ queryKey: ["overview"], queryFn: () => api.get<Overview>("/admoon/overview") });

export const useWorkspaces = (filters: { q?: string; status?: string; sector?: string }) =>
  useQuery({
    queryKey: ["workspaces", filters],
    queryFn: () => api.get<{ items: WorkspaceRow[]; sectors: string[] }>("/admoon/tenants", filters),
    placeholderData: (prev) => prev,
  });

export const useWorkspace = (id: string) =>
  useQuery({ queryKey: ["workspace", id], queryFn: () => api.get<WorkspaceDetail>(`/admoon/tenants/${id}`) });

export const useModules = () =>
  useQuery({ queryKey: ["modules"], queryFn: () => api.get<{ items: Module[] }>("/admoon/modules"), staleTime: Infinity });

export const useBilling = (status?: string) =>
  useQuery({ queryKey: ["billing", status], queryFn: () => api.get<Billing>("/admoon/billing", { status }) });

export const useActivity = (filters: { action?: string; tenant_id?: string }) =>
  useQuery({
    queryKey: ["activity", filters],
    queryFn: () => api.get<{ items: ActivityItem[]; next_before: string | null }>("/admoon/activity", { limit: 100, ...filters }),
  });

export const useOwners = (filters: { q?: string; without_workspaces?: boolean }) =>
  useQuery({
    queryKey: ["owners", filters],
    queryFn: () => api.get<{ items: OwnerRow[] }>("/admoon/owners", { q: filters.q || undefined, without_workspaces: filters.without_workspaces ? "true" : undefined }),
  });

export const useOwner = (id: string | null) =>
  useQuery({ queryKey: ["owner", id], queryFn: () => api.get<OwnerDetail>(`/admoon/owners/${id}`), enabled: !!id });

export const useTeam = () => useQuery({ queryKey: ["team"], queryFn: () => api.get<{ items: Person[]; me: string }>("/admoon/team") });

export const useSystem = () =>
  useQuery({ queryKey: ["system"], queryFn: () => api.get<SystemHealth>("/admoon/system"), refetchInterval: 30_000 });

// ─── Mutations ─────────────────────────────────────────────────────────────

/**
 * A mutation that refreshes every admin query when it succeeds.
 *
 * Success messages belong here, not in `mutate(…, { onSuccess })`: refreshed
 * data often removes the row that started the action, and React Query skips
 * per-call callbacks once their component has unmounted.
 */
export function useAction<TVars, TResult = unknown>(
  fn: (vars: TVars) => Promise<TResult>,
  opts: {
    success?: (vars: TVars, result: TResult) => string;
    /** Runs before data refreshes, while the calling page is still mounted (e.g. to navigate away). */
    then?: (vars: TVars, result: TResult) => void;
  } = {},
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (result, vars) => {
      if (opts.success) toast.success(opts.success(vars, result));
      opts.then?.(vars, result);
      return qc.invalidateQueries();
    },
  });
}

export const actions = {
  approveSubmission: (v: { id: string; note?: string }) => api.post<Submission>(`/admoon/marketplace/submissions/${v.id}/approve`, { note: v.note }),
  rejectSubmission: (v: { id: string; note: string }) => api.post<Submission>(`/admoon/marketplace/submissions/${v.id}/reject`, { note: v.note }),
  setListed: (v: { id: string; listed: boolean; note?: string }) =>
    api.post<Listing>(`/admoon/marketplace/items/${encodeURIComponent(v.id)}/${v.listed ? "relist" : "delist"}`, { note: v.note }),
  approveActivityChange: (v: { id: string; note?: string }) => api.post<ActivityChange>(`/admoon/activity-changes/${v.id}/approve`, { note: v.note }),
  rejectActivityChange: (v: { id: string; note: string }) => api.post<ActivityChange>(`/admoon/activity-changes/${v.id}/reject`, { note: v.note }),
  resetOwnerPassword: (id: string) => api.post<{ password: string }>(`/admoon/owners/${id}/reset-password`),
  sendOwnerResetCode: (id: string) => api.post<{ sent_to: string }>(`/admoon/owners/${id}/send-reset-code`),
  setOwnerActive: (v: { id: string; active: boolean }) => api.post<OwnerRow>(`/admoon/owners/${v.id}/active`, { active: v.active }),
  moveWorkspace: (v: { owner_id: string; tenant_id: string }) =>
    api.post<OwnerDetail>(`/admoon/owners/${v.owner_id}/workspaces`, { tenant_id: v.tenant_id }),
  mergeOwner: (v: { id: string; into: string }) => api.post<OwnerDetail>(`/admoon/owners/${v.id}/merge`, { into: v.into }),
  deleteOwner: (id: string) => api.del(`/admoon/owners/${id}`),
  setStatus: (v: { id: string; status: "active" | "suspended"; reason?: string }) =>
    api.post(`/admoon/tenants/${v.id}/status`, { status: v.status, reason: v.reason }),
  setPlan: (v: { id: string; plan: string; reason?: string }) =>
    api.post(`/admoon/tenants/${v.id}/plan`, { plan: v.plan, reason: v.reason }),
  extendTrial: (v: { id: string; days: number }) => api.post(`/admoon/tenants/${v.id}/extend-trial`, { days: v.days }),
  setModules: (v: { id: string; modules: string[] }) =>
    api.put(`/admoon/tenants/${v.id}/modules`, { active_modules: v.modules }),
  update: (v: { id: string; name?: string; slug?: string }) =>
    api.patch(`/admoon/tenants/${v.id}`, { name: v.name, slug: v.slug }),
  remove: (v: { id: string; confirm: string }) =>
    api.del(`/admoon/tenants/${v.id}?confirm=${encodeURIComponent(v.confirm)}`),
  impersonate: (id: string) =>
    api.post<{ access_token: string; slug: string | null; as_user: string }>(`/admoon/tenants/${id}/impersonate`),
  create: (v: Record<string, unknown>) => api.post<{ id: string; slug: string }>("/admoon/tenants", v),
  checkPaymob: (ref: string) =>
    api.post<{ checked: boolean; transactions: number; applied: number; status: string }>(`/admoon/billing/invoices/${encodeURIComponent(ref)}/check-paymob`),
  markPaid: (v: { ref: string; reference?: string; note?: string }) =>
    api.post(`/admoon/billing/invoices/${encodeURIComponent(v.ref)}/mark-paid`, { reference: v.reference, note: v.note }),
  extendLicence: (v: { id: string; days: number; reason?: string }) =>
    api.post<{ valid_until: string }>(`/admoon/tenants/${v.id}/licence/extend`, { days: v.days, reason: v.reason }),
  revokeLicence: (v: { id: string; revoked: boolean; reason?: string }) =>
    api.post(`/admoon/tenants/${v.id}/licence/revoke`, { revoked: v.revoked, reason: v.reason }),
  licenceKey: (id: string) => api.post<{ licence_key: string; valid_until: string }>(`/admoon/tenants/${id}/licence/key`),
  grant: (userId: string) => api.post("/admoon/team", { user_id: userId }),
  revoke: (userId: string) => api.del(`/admoon/team/${userId}`),
};
